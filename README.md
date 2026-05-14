# ChatDKU

**Agentic RAG system for Duke Kunshan University**

[![Watch Demo Video](https://img.shields.io/badge/Watch-Demo_Video-red?style=flat-square)](https://youtu.be/SdItulvqdLo)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

![ChatDKU Banner](/images/ChatDKU_Banner.png)

ChatDKU is a campus assistant that answers questions about DKU policies, courses, requirements, faculty, and academic resources. It retrieves information from DKU documents and databases, then generates accurate, answers with citations.

---

## Architecture

The agent is composed of three DSPy modules that run in sequence for each user message:

```
User message
    │
    ▼
Planner  ──── send_message ────► response (skip executor/synthesizer)
    │
   plan
    │
    ▼
Executor  (Assess-Act loop — calls tools guided by the plan)
    │
 relevant_context (distilled)
    │
    ▼
Synthesizer  ──► final response
```

**Planner** — Decides what to do with the user's message. If the question can be answered from conversation history or is a casual exchange, it responds directly (`send_message`). If information is missing (e.g. asking to build a schedule without providing a major), it asks the user. Otherwise it produces a free-form plan describing what information needs to be gathered.

**Executor** — Receives the plan and runs a two-phase loop per iteration: (1) **Assess** what has been gathered vs. what's still needed, then decide to continue or finish; (2) **Act** by picking a tool based on the gap analysis. After the loop, a **Distill** step extracts only the relevant information from the trajectory, discarding executor reasoning and failed calls.

**Synthesizer** — Receives the distilled context from the executor and generates the final response with citations.

**ConversationMemory** — Compresses and maintains conversation history across turns.

### Tools

| Tool | Purpose |
|------|---------|
| `VectorQuery` | Semantic search over DKU documents (ChromaDB) |
| `KeywordQuery` | BM25 keyword search over DKU documents (Redis) |
| `MajorRequirementsLookup` | Retrieves full major/track requirement lists |
| `QueryCurriculum` | Queries course schedule and syllabus database (PostgreSQL) |
| `PrerequisiteLookup` | Checks prerequisites for a given course |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Agent framework | DSPy |
| Document retrieval | LlamaIndex |
| Vector database | ChromaDB |
| Keyword index | Redis (BM25) |
| Course database | PostgreSQL |
| Backend API | Django |
| Frontend | Next.js |
| Observability | Arize Phoenix |

---

## Setup

### Prerequisites

- Python 3.11+
- Running ChromaDB, Redis, and PostgreSQL instances
- An OpenAI-compatible LLM endpoint (e.g. vLLM, SGLang)
- A text embedding endpoint (e.g. TEI with `BAAI/bge-m3`)

### Install

```bash
git clone https://github.com/Edge-Intelligence-Lab/ChatDKU.git
cd ChatDKU
uv sync
```

### Configure

Copy `.env.example` to `.env` and fill in the required values:

```bash
# LLM
LLM_BASE_URL=http://your-llm-server/v1
LLM_API_KEY=your_api_key
LLM_MODEL=your-model-name

# Embedding
TEI_URL=http://your-tei-server:8080
EMBEDDING_MODEL=BAAI/bge-m3

# Vector database
CHROMA_HOST=localhost
CHROMA_DB_PORT=8010

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Agent
MAX_ITERATIONS=5
CONTEXT_WINDOW=8192
LLM_TEMPERATURE=0.1
```

### Ingest documents

```bash
cd chatdku/ingestion

# Parse and chunk documents
python update_data.py --data_dir ./data --user_id Chat_DKU

# Load into ChromaDB
python load_chroma.py --nodes_path ./data/nodes.json --collection_name chatdku_docs

# Load into Redis (BM25)
python -m chatdku.ingestion.load_redis --nodes_path ./data/nodes.json --index_name chatdku
```

### Run

```bash
# CLI
python -m chatdku.core.agent

# Django backend
python manage.py runserver
```

---

## Development

See [chatdku/core/README.md](./chatdku/core/README.md) for a deeper explanation of the agent modules.

---

## Contact

- Email: te100@duke.edu
- Issues: [GitHub Issues](https://github.com/Edge-Intelligence-Lab/ChatDKU/issues)
