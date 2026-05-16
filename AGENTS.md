# AGENTS.md

This file provides guidance to AI Coding Agents (such as Claude Code or Codex) when working with code in this repository.

## Project Overview

ChatDKU is an agentic RAG campus assistant for Duke Kunshan University. It answers questions about DKU policies, courses, requirements, faculty, and academic resources using document retrieval and database queries.

## Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync

# Install with backend (Django) extras
uv sync --extra backend

# Run the agent CLI
python -m chatdku.core.agent

# Run the agent CLI in dev mode (extra debug prints)
python -m chatdku.core.agent --dev

# Run Django backend
python manage.py runserver

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_course_schedule.py

# Run a single test
pytest tests/test_course_schedule.py::test_function_name -v

# Lint
flake8 chatdku/

# Format
black chatdku/

# Sync code to dev server and run remotely
./devsync.sh
./devsync.sh chatdku/core/tools/your_file.py  # run a specific file
```

## Architecture

The agent is a DSPy module pipeline (`chatdku/core/agent.py`) with three stages:

1. **Planner** (`chatdku/core/dspy_classes/plan.py`) — Decides whether to respond directly (casual/simple), ask for clarification, or produce a retrieval plan.
2. **Executor** (`chatdku/core/dspy_classes/executor.py`) — Runs an Assess→Act loop calling tools per the plan, then distills relevant context from the trajectory.
3. **Synthesizer** (`chatdku/core/dspy_classes/synthesizer.py`) — Generates the final cited response from distilled context.

Supporting modules:

- `chatdku/core/dspy_classes/conversation_memory.py` — Compresses and maintains conversation history.
- `chatdku/core/dspy_classes/prompt_settings.py` — System prompts and prompt configuration.

### Tools (in `chatdku/core/tools/`)

Each tool is a callable that the Planner/Executor can invoke:

| File                    | Tool                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------ |
| `llama_index_tools.py`  | `VectorQuery` (ChromaDB) and `KeywordQuery` (Redis BM25)                             |
| `major_requirements.py` | `MajorRequirementsLookup` — full major/track requirement lists                       |
| `syllabi/`              | `SyllabusLookup` — queries PostgreSQL course/syllabus database via LLM-generated SQL |
| `course_schedule.py`    | `CourseScheduleLookup` — searches cleaned class schedule CSV                         |
| `get_prerequisites.py`  | `PrerequisiteLookup` — prerequisite checks from CSV                                  |
| `course_recommender.py` | `CourseRecommender` — agentic course recommendation with policy-aware planning       |

### Configuration

- `chatdku/config.py` — Singleton `Config` object (import as `from chatdku.config import config`). Loads from env vars, supports attribute access (`config.llm`, `config.psql_uri`).
- `chatdku/setup.py` — Initializes embedding model, tokenizer, Phoenix tracing, and DB connections.
- `.env` — Required for LLM endpoints, database URIs, Redis, ChromaDB. Copy from `.env.example`.

### Infrastructure

| Component          | Technology                                           |
| ------------------ | ---------------------------------------------------- |
| Agent framework    | DSPy (v3.1+)                                         |
| Document retrieval | LlamaIndex                                           |
| Vector database    | ChromaDB                                             |
| Keyword index      | Redis (BM25)                                         |
| Course database    | PostgreSQL (via SQLAlchemy)                          |
| Backend API        | Django (in `chatdku/backend/` and `chatdku/django/`) |
| Observability      | Arize Phoenix (OpenTelemetry traces)                 |
| Python             | 3.11–3.12                                            |

### Key Patterns

- All DSPy sub-modules use OpenTelemetry spans (`span_ctx_start` from `chatdku/core/utils.py`) for Phoenix tracing.
- `LITELLM_LOCAL_MODEL_COST_MAP=True` is set before importing dspy to avoid a ~40s cold-start penalty.
- Tests mock `span_ctx_start` at all import sites (see `tests/conftest.py`) so no real tracer is needed.
- The syllabi tool generates SQL against a PostgreSQL schema defined in `chatdku/core/tools/syllabi/`. The JSON schema file (`classes_schema.json`) must stay in sync with the actual DB schema.
- Flake8 config: max line length 120, ignores E203 and W503 (configured in `pyproject.toml`).

### Document Ingestion (`chatdku/ingestion/`)

Pipeline for parsing documents and loading into retrieval backends:

1. `update_data.py` — Parse and chunk documents
2. `load_chroma.py` — Load into ChromaDB
3. `load_redis.py` — Load into Redis BM25 index
4. `load_postgres.py` / `local_ingest.py` — Load structured data into PostgreSQL

## Git Workflow

- `main` branch is protected — always create a feature branch and PR.
- Link commits/PRs to GitHub Issues.
