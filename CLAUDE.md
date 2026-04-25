# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChatDKU is an agentic RAG campus assistant for Duke Kunshan University. It answers questions about DKU policies, courses, requirements, faculty, and academic resources by combining document retrieval with structured database queries.

## Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync
uv sync --extra backend  # adds Django for the backend API

# Run the agent
python -m chatdku.core.agent                          # interactive REPL
python -m chatdku.core.agent "your question here"     # one-shot

# Run the Django backend
python manage.py runserver

# Tests — note that several test files currently have stale imports and
# fail at collection time. About 81 tests do collect and run; target
# individual files to avoid the noisy collection errors:
pytest tests/test_<name>.py
pytest tests/test_<name>.py::test_function -v

# Lint — flake8 does not read pyproject.toml without the Flake8-pyproject
# plugin, so the project's intended limits must be passed on the CLI.
# Without these flags, flake8 silently falls back to its 79-char default
# and reports hundreds of false positives.
flake8 --max-line-length=120 --extend-ignore=E203,W503 chatdku/

# Format
black chatdku/

# Sync to the dev server and run remotely (data files live there at
# /datapool/chatdku_external_data/, so most tools need this to exercise).
./devsync.sh                              # runs `python -m chatdku.core.agent`
./devsync.sh path/to/file.py              # runs that file
./devsync.sh chatdku.module.name          # runs `python -m <module>`
./devsync.sh "natural language query"     # runs the agent with that query
# Quoting gotchas: apostrophes break shell quoting, and any prompt
# containing a slash (e.g. "AP/IB") is misread as a file path. Rephrase
# to avoid both before invoking.
```

## Architecture

The agent is a DSPy module pipeline (`chatdku/core/agent.py`) with three stages. The **Planner** (`chatdku/core/dspy_classes/plan.py`) reads the user message plus conversation history and either responds directly, asks for clarification, or produces a free-form plan and names the most relevant skill. The **Executor** (`chatdku/core/dspy_classes/executor.py`) iteratively picks tool calls against that plan, optionally extending the agenda when tool results reveal new investigation areas, then distills the trajectory into a relevant-context block. The **Synthesizer** (`chatdku/core/dspy_classes/synthesizer.py`) generates the final cited response from that block. Conversation memory is compressed and managed by `conversation_memory.py`; system prompts live in `prompt_settings.py`.

Both the Planner and the Executor receive the same tool list, so anything added to `agent.py`'s registry becomes visible to both. The Planner's selection is advisory — its plan can name a tool, but the Executor decides which tool to actually invoke each iteration.

### Skills

Skills live under `chatdku/skills/<category>/<Skill-Name>/SKILL.md` (currently the only category is `advising`). Each `SKILL.md` has YAML frontmatter (`name`, `description`, optional `metadata.tags`/`metadata.category`) and a Markdown body of task-specific instructions. The Planner sees a name+description summary of every skill via `skills_list` and may set `relevant_skill_name` on its output; the Executor then loads the full body via the auto-injected `skill_view` tool. Both `skills_list` and `skill_view` are also available for the Executor to call at any time to discover or re-load skills. Skill loading injects *instructions*, not tools — a skill cannot make a new callable available, only direct the agent toward existing ones.

### Tools

Tool implementations live in `chatdku/core/tools/`. The retrieval primitives are `VectorQuery` (ChromaDB) and `KeywordQuery` (Redis BM25), both in `llama_index_tools.py`. The structured lookups are `MajorRequirementsLookup` (full requirement lists per major/track), `SyllabusLookup` (LLM-generated SQL against the PostgreSQL syllabus database, schema in `syllabi/`), `CourseScheduleLookup` (cleaned class-schedule CSV), and `PrerequisiteLookup` (prereq CSV). The aggregator is `BuildSemesterPlan` (`course_recommender.py`), which joins major requirements + offerings + prereqs and enumerates time-conflict-free schedule combinations — preferred over manually chaining the three single-purpose lookups for any "what should I take" question.

### Configuration

`chatdku/config.py` exposes a singleton `Config` object loaded from environment variables; import as `from chatdku.config import config` and access fields by attribute (`config.llm`, `config.psql_uri`, etc.). `chatdku/setup.py` initializes the embedding model, tokenizer, Phoenix tracing, and DB connections. A `.env` file (copy from `.env.example`) is required locally for LLM endpoints, database URIs, Redis, and ChromaDB; on the dev server the same values come from a shared profile script (`/datapool/secrets/chatdku_env.sh`) so no `.env` is needed there.

### Infrastructure

The agent framework is DSPy (≥3.1) with LlamaIndex for document retrieval, ChromaDB for vector search, Redis BM25 for keyword search, and PostgreSQL (via SQLAlchemy) for the course/syllabus database. The optional backend lives under `chatdku/backend/` (FastAPI) and `chatdku/django/` (Django). Observability is Arize Phoenix over OpenTelemetry. Targeted Python is 3.11–3.12.

### Key patterns

All DSPy sub-modules use OpenTelemetry spans (`span_ctx_start` from `chatdku/core/utils.py`) for Phoenix tracing; tests mock this at all import sites (see `tests/conftest.py`) so no real tracer is needed. `LITELLM_LOCAL_MODEL_COST_MAP=True` is set before importing dspy to avoid a ~40s cold-start penalty. The syllabi tool generates SQL against a PostgreSQL schema described in `chatdku/core/tools/syllabi/`, and the JSON schema file (`classes_schema.json`) must stay in sync with the live DB schema. Phoenix data is reported under the project name `ChatDKU_student_release`.

### Document ingestion

The pipeline lives in `chatdku/ingestion/`. `update_data.py` parses and chunks documents, then `load_chroma.py` loads vectors into ChromaDB, `load_redis.py` builds the BM25 index, and `load_postgres.py` / `local_ingest.py` load structured rows into PostgreSQL.

## Git workflow

`main` is protected — work on a feature branch and open a PR. Link commits/PRs to the corresponding GitHub Issue.
