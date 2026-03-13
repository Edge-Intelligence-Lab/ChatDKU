# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChatDKU is an agentic RAG system with a Next.js frontend and Django backend. The core agent uses DSPy for orchestration and supports multi-hop reasoning with retrieval from Redis (keyword) and ChromaDB (vector).

## Development Commands

### Agent-Only Version (Quick Start)
```bash
# Start Agent-Only services (Redis, ChromaDB, Agent)
docker compose -f docker-compose.agent.yml up --build

# Run Agent CLI
docker compose -f docker-compose.agent.yml exec agent python -m chatdku.core.agent

# Local development (without Docker)
bash scripts/run_agent_local.sh
```

### Full Version (Docker)
```bash
# Start all services (frontend, backend, PostgreSQL, Redis, ChromaDB)
docker compose up --build

# Start with Celery for async tasks
docker compose --profile django up --build

# Use custom env file
docker compose --env-file .env.local up --build
```

### Frontend (Next.js)
From `chatdku/chatdku/frontend/ChatDKU-web/`:
```bash
npm run dev          # Development server with turbopack
npm run build        # Production build
npm test             # Run Jest tests with typecheck
npm run typecheck    # TypeScript validation only
```

### Backend (Python)
From `chatdku/` directory:
```bash
# Setup for Agent-Only
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Setup for Full version (with Django)
pip install -e ".[full]"

# Run agent CLI directly
python -m chatdku.core.agent

# Run Django backend (for Full version local dev)
cd chatdku/chatdku/django/chatdku_django
python manage.py runserver 0.0.0.0:8007
```

### Data Ingestion
```bash
# Quick setup (automated script)
bash scripts/setup_agent_data.sh

# Manual setup from chatdku/chatdku/ingestion/
python update_data.py --data_dir ./data --user_id Chat_DKU -v True
python load_chroma.py --nodes_path ./data/nodes.json --collection_name chatdku_docs
python -m chatdku.chatdku.ingestion.load_redis --nodes_path ./data/nodes.json --index_name chatdku
```

### Testing
```bash
# Python tests
pytest chatdku/tests/

# Frontend tests
cd chatdku/chatdku/frontend/ChatDKU-web && npm test
```

## Architecture

### Core Agent Pipeline (`chatdku/core/agent.py`)
The agent follows this flow:
1. **Query Rewriter**: Cleans user query, adds conversation context, creates retrieval text
2. **Retrieval**: Fetches documents from KeywordRetriever (Redis) and VectorRetriever (ChromaDB)
3. **Judge**: Determines if retrieved context is sufficient
4. **Loop**: If insufficient, repeat steps 1-3 (up to `max_iterations`)
5. **Synthesizer**: Generates final answer using context and conversation history
6. **Conversation Memory**: Summarizes and stores the exchange

**Note**: The Planner module is currently disabled as only 2 tools exist. It will be enabled when more tools are implemented.

### Module Structure
- `chatdku.core`: Agent logic, DSPy modules, tools, utilities
  - `agent.py`: Main agent entry point
  - `dspy_classes/`: DSPy module implementations
  - `tools/`: Retrieval tools and syllabi tool (PostgreSQL-based, adds latency)
- `chatdku.django`: Django backend with REST API, PostgreSQL, Celery
  - `core/`: User models, file uploads, rate limiting middleware
  - `chat/`: Chat views, session management, feedback
  - `stt/`: Socket.IO server for speech-to-text (optional)
- `chatdku.frontend`: Next.js web application (React 19, TypeScript, Tailwind)
- `chatdku.ingestion`: Data loading and indexing scripts
- `scraper/`: Web scraper for data collection
- `benchmarks/`: Benchmarking scripts

### External Dependencies
- **LLM**: OpenAI-compatible API (default: sglang on port 18085)
- **Embedding**: Text Embeddings Inference (TEI) server (default: port 8080)
  - Endpoint format: `{TEI_URL}/{author}/{model_name}/embed`
  - Example: `http://localhost:8080/BAAI/bge-m3/embed`
- **Storage**: Redis (port 6379), ChromaDB (port 8010), PostgreSQL (port 5432, Django only)
- **Observability**: Phoenix (Arize) for tracing (port 6006)

### Environment Configuration
Key variables in `.env` or `.env.local`:
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`
- `TEI_URL`, `EMBEDDING_MODEL`
- `REDIS_HOST`, `REDIS_PASSWORD`
- `CHROMA_HOST`, `CHROMA_DB_PORT`
- `NEXT_PUBLIC_API_BASE_URL`, `BACKEND_INTERNAL_URL`
- Django: `NAME_DB`, `USERNAME_DB`, `PASSWORD_DB`, `HOST_DB`

## Key Patterns

### DSPy Modules
All DSPy modules use:
- `span` decorators for Phoenix telemetry
- Input truncation for small context windows
- DSPy refinement to enforce output format

### Adding Tools
To add a new tool for the agent:
1. Create tool class in `chatdku/core/tools/`
2. Implement retrieval/query logic
3. Register in `agent.py` tool list
4. Enable Planner module when >2 tools exist

### Data Ingestion Flow
1. Place files in data directory
2. Run `update_data.py` to detect changes (creates `changed_data.json`)
3. Script updates `parser_documents.pkl` and rebuilds indices
4. Load into ChromaDB and Redis vector stores

## Common Issues

- **Phoenix port collision**: Set `PHOENIX_PORT` env var if running multiple instances
- **Syllabi tool latency**: PostgreSQL connection overhead; needs Django connection pooling
- **HTML misidentification**: Custom `detect_filetype` override handles JS-heavy HTML files
- **First ingestion**: Initial run takes longer as it indexes all files from scratch
- **Redis requirement**: Ensure Redis server is running on port 6379 for ingestion scripts

## File References
When referencing code locations, use the format `file_path:line_number` for easy navigation.

## Always speak chinese