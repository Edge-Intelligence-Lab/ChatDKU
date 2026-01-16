
<h1 align="center">ChatDKU</h1>

<p align="center">
  <strong>🎓 The First Open-Source Agentic RAG System Designed for Campus Scenarios</strong>
</p>

<p align="center">
  <a href="./README.md">English</a> | <a href="./README_CN.md">中文</a>
</p>

<p align="center">
  <a href="https://github.com/xxx/ChatDKU/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License">
  </a>
  <a href="https://github.com/xxx/ChatDKU/stargazers">
    <img src="https://img.shields.io/github/stars/xxx/ChatDKU" alt="Stars">
  </a>
  <a href="https://github.com/xxx/ChatDKU/issues">
    <img src="https://img.shields.io/github/issues/xxx/ChatDKU" alt="Issues">
  </a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Next.js-15-black.svg" alt="Next.js">
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-data-ingestion">Data Ingestion</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## ✨ Features

ChatDKU is a **DSPy-based Agentic RAG system** specifically designed for university campus scenarios, providing intelligent Q&A services.

### 🤖 Agentic RAG Core

Unlike traditional RAG systems, ChatDKU adopts an **Agentic RAG** architecture where the Agent can:

- **Autonomous Planning**: Automatically decide retrieval strategies based on user queries
- **Quality Assessment**: Judge module evaluates retrieval results and decides if additional retrieval is needed
- **Iterative Retrieval**: Supports multi-round retrieval until sufficient context is obtained
- **Tool Calling**: Extensible tools including SQL queries, API calls, etc.

```
User Query → Query Rewrite → Retrieval → Judge Assessment → Need More Info? 
                                ↑                              ↓ Yes
                                └──────────────────────────────┘
                                         ↓ No
                                Synthesizer → Response
```

### 🔍 Hybrid Retrieval System

ChatDKU employs a **Vector + Keyword** hybrid retrieval architecture:

| Retrieval Type | Tech Stack | Characteristics |
|----------------|------------|-----------------|
| **Vector Search** | ChromaDB + HuggingFace Embeddings | Semantic similarity matching, understands synonyms and context |
| **Keyword Search** | Redis + BM25 | Exact matching, handles proper nouns and abbreviations |
| **Result Fusion** | Re-ranking | Combined ranking for improved retrieval accuracy |

### 🎓 Campus-Specific Tools

- **Course Syllabus Query**: SQL Agent-based course database queries
- **Campus Document Q&A**: Supports PDF, Word, PPT, Excel and more
- **User Document Upload**: Users can upload private documents for Q&A
- **Voice Input**: Integrated Whisper model for speech-to-text

### 📊 Observability

- **Phoenix Integration**: Complete LLM call tracing
- **OpenTelemetry**: Standardized monitoring metrics
- **Performance Analysis**: Token usage, latency analysis, cost statistics

---

## 🏗 Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ChatDKU System Architecture                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        Frontend (Next.js)                        │   │
│  │  • Responsive Chat UI      • Markdown Render    • Voice Input    │   │
│  │  • File Upload             • Dark/Light Theme   • Mobile Ready   │   │
│  └───────────────────────────────┬─────────────────────────────────┘   │
│                                  │ REST API                             │
│                                  ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     Backend (Django + Flask)                     │   │
│  │  • User Auth              • Session Mgmt       • File Processing │   │
│  │  • API Routing            • Streaming          • STT (Whisper)   │   │
│  └───────────────────────────────┬─────────────────────────────────┘   │
│                                  │                                      │
│                                  ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      DSPy Agent Core                             │   │
│  │                                                                   │   │
│  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │   │
│  │   │Query Rewriter│───▶│   Planner    │───▶│    Judge     │      │   │
│  │   │              │    │              │    │              │      │   │
│  │   └──────────────┘    └──────────────┘    └──────┬───────┘      │   │
│  │                                                   │              │   │
│  │         ┌─────────────────────────────────────────┤              │   │
│  │         │                                         │              │   │
│  │         ▼                                         ▼              │   │
│  │   ┌──────────────┐                         ┌──────────────┐      │   │
│  │   │   Tools      │                         │ Synthesizer  │      │   │
│  │   │ • RAG        │                         │              │      │   │
│  │   │ • SQL Query  │                         └──────────────┘      │   │
│  │   │ • API Call   │                                               │   │
│  │   └──────────────┘                                               │   │
│  │                                                                   │   │
│  └───────────────────────────────┬─────────────────────────────────┘   │
│                                  │                                      │
│          ┌───────────────────────┼───────────────────────┐             │
│          ▼                       ▼                       ▼             │
│    ┌──────────┐           ┌──────────┐           ┌──────────┐         │
│    │ ChromaDB │           │  Redis   │           │ Postgres │         │
│    │ Vectors  │           │ BM25 Idx │           │ Courses  │         │
│    └──────────┘           └──────────┘           └──────────┘         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Observability (Phoenix)                       │   │
│  │             LLM Tracing • Token Stats • Latency Analysis         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Agent Workflow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Agent Processing Flow                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. User Input                                                           │
│     │                                                                    │
│     ▼                                                                    │
│  2. Load Conversation History (Conversation Memory)                      │
│     │                                                                    │
│     ▼                                                                    │
│  3. Query Rewriting (Query Rewriter)                                     │
│     • Fix spelling errors                                                │
│     • Add conversation context                                           │
│     • Generate retrieval-optimized query                                 │
│     │                                                                    │
│     ▼                                                                    │
│  4. Parallel Retrieval                                                   │
│     ├─── KeywordRetriever (Redis BM25) ───┐                             │
│     │                                      ├──▶ Fusion + Re-rank        │
│     └─── VectorRetriever (ChromaDB) ──────┘                             │
│     │                                                                    │
│     ▼                                                                    │
│  5. Quality Assessment (Judge)                                           │
│     │                                                                    │
│     ├─── Context Sufficient ──▶ Go to Step 6                            │
│     │                                                                    │
│     └─── Context Insufficient ──▶ Back to Step 3                        │
│          (use internal_memory to avoid duplicate retrieval)              │
│          (max iterations: max_iterations)                                │
│     │                                                                    │
│     ▼                                                                    │
│  6. Answer Generation (Synthesizer)                                      │
│     • Combine retrieved context                                          │
│     • Reference conversation history                                     │
│     • Generate structured response                                       │
│     │                                                                    │
│     ▼                                                                    │
│  7. Conversation Memory Update                                           │
│     • Summarize current conversation                                     │
│     • Store to conversation_history                                      │
│     │                                                                    │
│     ▼                                                                    │
│  8. Return Response to User                                              │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Function | Implementation |
|-----------|----------|----------------|
| **Query Rewriter** | Fix spelling, add conversation context | DSPy Module |
| **Planner** | Plan tool calling strategy (multi-tool) | DSPy Module |
| **Judge** | Evaluate retrieval quality, decide continuation | DSPy Refine |
| **VectorRetriever** | Semantic similarity search | ChromaDB + BGE-M3 |
| **KeywordRetriever** | BM25 keyword search | Redis RediSearch |
| **Synthesizer** | Generate final answer based on context | DSPy Module |
| **Syllabi Tool** | SQL Agent for course database queries | Postgres + DSPy |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (LTS)
- Redis 7+
- Docker & Docker Compose (recommended)

### Option 1: Docker Deployment (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/xxx/ChatDKU.git
cd ChatDKU

# 2. Copy and edit configuration
cp docker/.env.example docker/.env
vim docker/.env  # Set LLM API Key, etc.

# 3. Start all services
docker-compose -f docker/docker-compose.yml up -d

# 4. Check service status
docker-compose -f docker/docker-compose.yml ps

# 5. Access the application
# Frontend: http://localhost:3000
# Phoenix: http://localhost:6006
```

### Option 2: Local Development

```bash
# 1. Clone the repository
git clone https://github.com/xxx/ChatDKU.git
cd ChatDKU

# 2. Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install Python dependencies
cd chatdku
pip install -e ".[dev]"

# 4. Start Redis
redis-server

# 5. Start backend service
python chatdku/core/agent.py

# 6. Start frontend (new terminal)
cd chatdku/frontend
npm install
npm run dev

# 7. Visit http://localhost:3000
```

### Configuration

Main environment variables (configure in `.env` file):

```bash
# ===== LLM Configuration =====
LLM_PROVIDER=openai              # openai / vllm / ollama
LLM_MODEL=gpt-4o                 # Model name
LLM_URL=https://api.openai.com   # API endpoint
LLM_API_KEY=sk-xxx               # API Key

# ===== Embedding Configuration =====
EMBEDDING_MODEL=BAAI/bge-m3      # Embedding model
TEI_URL=http://localhost:8080    # TEI service URL (optional)

# ===== Database Configuration =====
REDIS_HOST=localhost
REDIS_PORT=6379
CHROMA_HOST=localhost
CHROMA_PORT=8001

# ===== Observability =====
PHOENIX_PORT=6006
```

---

## 📥 Data Ingestion

ChatDKU's data ingestion pipeline consists of three stages: Data Collection → Data Processing → Vector Indexing.

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Data Ingestion Pipeline                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │   Scraper   │     │  Ingestion  │     │   Loading   │               │
│  │             │────▶│             │────▶│             │               │
│  └─────────────┘     └─────────────┘     └─────────────┘               │
│                                                                         │
│   • Website Crawler   • File Parsing      • ChromaDB                   │
│   • Document Collect  • Text Chunking     • Redis BM25                 │
│   • PDF/HTML/...      • Node Generation   • Course DB                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. Data Collection (Scraper)

Use async crawler to collect campus website content:

```bash
cd scraper

# Install dependencies
pip install -e .

# Run scraper (default: dukekunshan.edu.cn)
python scraper.py

# View scraping report
python report.py -s progress.pkl
```

Output directory structure:
```
./dku_website/
├── domain/
│   └── path/
│       ├── index.html
│       └── ...
└── progress.pkl  # Scraping progress record
```

### 2. Data Processing (Ingestion)

Convert raw files to searchable text nodes:

```bash
cd chatdku/chatdku/ingestion

# Incremental update (auto-detect added/deleted files)
python update_data.py \
    --data_dir /path/to/data \
    --user_id Chat_DKU \
    -v True
```

**Supported file formats**: PDF, HTML, CSV, XLSX, DOCX, TXT, Markdown

**Output files**:
- `nodes.json` - All parsed text nodes
- `log.json` - Record of processed files

### 3. Vector Indexing (Loading)

Load processed nodes into vector databases:

**Load to ChromaDB**:
```bash
# Production (will reset existing data)
python load_chroma.py

# Testing (recommended)
python load_chroma.py \
    --nodes_path /path/to/test/nodes.json \
    --collection_name test_collection
```

**Load to Redis**:
```bash
# Production
python -m chatdku.chatdku.ingestion.load_redis

# Testing (recommended)
python -m chatdku.chatdku.ingestion.load_redis \
    --nodes_path /path/to/nodes.json \
    --index_name test_index \
    --reset False
```

### 4. Course Data Import

Course syllabus data is stored in PostgreSQL:

```bash
# 1. Create database tables
psql -U chatdku_user -d chatdku_db -f create_table.sql

# 2. Import syllabi from PDF/DOCX
python local_ingest.py --input_dir /path/to/syllabi
```

---

## 🌐 Frontend & Backend

### Frontend

**Tech Stack**: Next.js 15 + TailwindCSS + shadcn/ui

```bash
cd chatdku/frontend

# Development mode
npm install
npm run dev          # http://localhost:3000

# Production build
npm run build        # Output to out/ directory

# Deployment
sudo rsync -av --delete out/ /var/www/chatdku/
```

**Main Features**:
- Responsive chat interface for desktop and mobile
- Markdown rendering with code highlighting
- Voice input (calls Whisper service)
- File upload (user private documents)
- Dark/Light theme toggle

### Backend

**Tech Stack**: Django REST Framework + Flask

**Django Service** (Main API):
```bash
cd chatdku/django

# Start development server
python manage.py runserver 0.0.0.0:8000

# API Documentation
# http://localhost:8000/api/docs/  (drf-spectacular)
```

**Flask Service** (Agent + STT):
```bash
cd chatdku/backend

# Start Agent service
python agent_app_parellel.py

# Start Speech-to-Text service
python stt_app.py
```

**API Endpoints Example**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/` | POST | Send chat message |
| `/api/chat/stream/` | POST | Streaming chat response |
| `/api/upload/` | POST | Upload user document |
| `/api/stt/` | POST | Speech to text |
| `/api/sessions/` | GET | Get session list |

---

## 📁 Project Structure

```
ChatDKU/
├── chatdku/                      # Core Python package
│   ├── chatdku/
│   │   ├── core/                 # Agent core
│   │   │   ├── agent.py          # Main Agent entry
│   │   │   ├── dspy_classes/     # DSPy components
│   │   │   │   ├── query_rewriter.py
│   │   │   │   ├── judge.py
│   │   │   │   ├── synthesizer.py
│   │   │   │   └── ...
│   │   │   └── tools/            # Agent tools
│   │   │       ├── rag_tool.py
│   │   │       └── syllabi_tool/
│   │   ├── ingestion/            # Data ingestion
│   │   │   ├── update_data.py    # Incremental update
│   │   │   ├── load_chroma.py    # ChromaDB loader
│   │   │   └── load_redis.py     # Redis loader
│   │   ├── backend/              # Flask backend
│   │   │   ├── agent_app_parellel.py
│   │   │   └── stt_app.py
│   │   ├── django/               # Django API
│   │   │   └── chatdku_django/
│   │   └── frontend/             # Next.js frontend
│   │       ├── app/
│   │       ├── components/
│   │       └── public/
│   └── pyproject.toml
├── scraper/                      # Website scraper
├── utils/                        # Utility scripts
├── benchmarks/                   # Performance benchmarks
├── docker/                       # Docker configuration
│   ├── docker-compose.yml
│   └── .env.example
├── docs/                         # Documentation
├── LICENSE
├── README.md
└── CONTRIBUTING.md
```

---

## 🧪 Development Guide

### Setup

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run linting
ruff check .
ruff format .

# Type checking
mypy chatdku/

# Run tests
pytest tests/ -v
```

### Adding New Tools

See [Issue #122](https://github.com/xxx/ChatDKU/issues/122) for how to add new tools to the Agent.

Basic steps:
1. Create tool module in `chatdku/core/tools/`
2. Implement tool function returning retrieval results
3. Register tool in `agent.py`
4. Update Planner tool descriptions

---

## 📊 Benchmarks

| Metric | Value | Test Conditions |
|--------|-------|-----------------|
| Time to First Token | ~1.5s | vLLM backend, A100 GPU |
| Retrieval Accuracy | 85%+ | DKU Q&A dataset |
| Context Relevance | 0.82 | RAGAS evaluation |
| End-to-End Latency | ~3s | Average query |

See [benchmarks/](benchmarks/) directory for details.

---

## 🤝 Contributing

We welcome all forms of contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

### Ways to Contribute

- 🐛 **Report Bugs**: Submit Issues describing problems
- 💡 **Feature Suggestions**: Submit Feature Requests
- 📝 **Improve Documentation**: Help improve docs
- 🔧 **Submit Code**: Submit Pull Requests

### Commit Convention

```
feat: New feature
fix: Bug fix
docs: Documentation update
refactor: Code refactoring
test: Test related
chore: Build/tooling related
```

---

## 📜 License

This project is licensed under the [Apache License 2.0](LICENSE).

---

## 🙏 Acknowledgements

- [DSPy](https://github.com/stanfordnlp/dspy) - Agent framework
- [LlamaIndex](https://github.com/run-llama/llama_index) - RAG tooling
- [ChromaDB](https://github.com/chroma-core/chroma) - Vector database
- [Phoenix](https://github.com/Arize-ai/phoenix) - LLM observability
- [shadcn/ui](https://ui.shadcn.com/) - UI component library

---

## 📬 Contact

- **GitHub Issues**: [Submit Issue](https://github.com/xxx/ChatDKU/issues)
- **Email**: contact@chatdku.edu
- **Discord**: [ChatDKU Community](https://discord.gg/xxx)

---

<p align="center">
  Made with ❤️ at Duke Kunshan University
</p>
