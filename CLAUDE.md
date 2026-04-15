# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChatDKU is an agentic RAG (Retrieval-Augmented Generation) system for Duke Kunshan University. It answers student questions about courses, policies, requirements, and campus resources using a three-stage DSPy pipeline: **Planner** -> **Executor** (assess-act-distill loop) -> **Synthesizer**.

## Commands

```bash
# Install dependencies
uv sync

# Run the agent CLI
python -m chatdku.core.agent

# Run Django backend
python manage.py runserver

# Run tests
python -m pytest tests/
python -m pytest tests/test_retriever.py          # single file

# Lint (CI runs these on changed .py files in PRs)
black --check <files>
flake8 --ignore=E203,W503 --max-line-length 120 <files>

# Format
black <files>

# Sync and run on dev server
./devsync.sh                                      # runs the agent remotely
./devsync.sh chatdku/core/tools/your_file.py      # runs a specific file
```

## Architecture

### Agent Pipeline (`chatdku/core/`)

The agent is three DSPy modules in sequence per user message:

1. **Planner** (`dspy_classes/plan.py`) — Decides whether to answer directly (`send_message`), ask clarifying questions, or produce a plan for what information to gather.
2. **Executor** (`dspy_classes/executor.py`) — Runs an Assess-Act loop guided by the plan, calling tools to gather information. A Distill step extracts only relevant context from the trajectory.
3. **Synthesizer** (`dspy_classes/synthesizer.py`) — Generates the final cited response from distilled context.
4. **ConversationMemory** (`dspy_classes/conversation_memory.py`) — Compresses/maintains chat history across turns.

Entry point: `chatdku/core/agent.py`

### Tools (`chatdku/core/tools/`)

Tools available to the executor: `VectorQuery` (ChromaDB semantic search), `KeywordQuery` (Redis BM25), `MajorRequirementsLookup`, `QueryCurriculum` (PostgreSQL course/syllabus DB), `PrerequisiteLookup`, and others (calculator, campus service, email, search, GraphRAG).

### Document Ingestion (`chatdku/ingestion/`)

Parses, chunks, and loads documents into vector/keyword stores:
- `update_data.py` — Parse and chunk documents
- `load_chroma.py` — Load into ChromaDB
- `load_redis.py` — Load into Redis (BM25 index)
- `load_postgres.py` — Load course data into PostgreSQL
- `clean_classdata.py` — Clean class schedule CSV data

### Configuration (`chatdku/config.py`)

Singleton `Config` class loaded from environment variables (`.env`). Access via `from chatdku.config import config`. Supports attribute access (`config.llm_temperature`), `.set()`, `.update()`, and a read-only `.view()`. All paths, model names, DB connections, and tuning parameters live here.

### Backend (`chatdku/backend/`)

Legacy Flask backend and Django backend (`chatdku/django/`). Django app uses `manage.py` at repo root.

### Infrastructure

- **LLM**: OpenAI-compatible endpoint (vLLM/SGLang with Qwen models)
- **Embeddings**: TEI with `BAAI/bge-m3`
- **Vector DB**: ChromaDB
- **Keyword Index**: Redis
- **Course DB**: PostgreSQL
- **Observability**: Arize Phoenix
- **Framework**: DSPy for agent logic, LlamaIndex for document ingestion

## Code Style

- **Formatter**: Black (pre-commit hook, CI)
- **Linter**: Flake8 — `max-line-length=120`, ignores `E203,W503`
- **Python**: 3.11 (pinned in `.python-version`); `pyproject.toml` requires `>=3.11, <3.13`
- **Docstrings**: NumPy format preferred (per GUIDE.md)

## Key Environment Variables

`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `TEI_URL`, `EMBEDDING_MODEL`, `CHROMA_HOST`, `CHROMA_DB_PORT`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`. See `.env.example` or `chatdku/config.py` for the full set.

## Git Workflow

- `main` branch is protected — never push directly; always use PRs with review.
- Create a GitHub issue before starting work.
- Use `devsync.sh` to iterate on the shared dev server (rsyncs code, runs `uv sync`, starts a live session).
