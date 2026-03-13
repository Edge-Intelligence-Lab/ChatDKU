# ChatDKU Agent-Only Quick Start Guide

This guide helps you deploy the ChatDKU Agent-Only version in 5-10 minutes.

---

## Prerequisites

### Required
- Docker and Docker Compose
- Python 3.11 or 3.12 (for local development mode)
- Accessible LLM service (OpenAI-compatible API)
- Accessible TEI Embedding service

### Recommended Configuration
- 2C4G+ memory (for Agent itself)
- GPU recommended for LLM service (e.g., sglang)

### Notes
- Python 3.13 requires dependency version modifications (see FAQ)
- Ensure ports 8011 (ChromaDB) and 6379 (Redis) are not occupied

---

## Quick Deployment (Docker)

### 1. Clone Repository

```bash
git clone https://github.com/Edge-Intelligence-Lab/ChatDKU.git
cd ChatDKU
```

### 2. Configure Environment Variables

```bash
cp .env.agent .env
```

Edit the `.env` file and set the following key parameters:

```bash
# LLM service address (required)
LLM_BASE_URL=http://localhost:18085/v1
LLM_API_KEY=your_api_key

# Embedding service address (required)
TEI_URL=http://localhost:8080

# HuggingFace mirror (recommended for China mainland)
HF_ENDPOINT=https://hf-mirror.com
```

### 3. Prepare Data (Optional)

If you have your own document data:

```bash
# Place documents in data/ directory
cp your_documents/* ./data/

# Start all services (including agent container)
docker compose -f docker-compose.agent.yml up -d

# Run data initialization inside agent container
docker compose -f docker-compose.agent.yml exec agent bash scripts/setup_agent_data.sh
```

**Note**: The data initialization script must run inside the agent container because it needs to connect to Redis and ChromaDB in the container network.

### 4. Test Agent

```bash
docker compose -f docker-compose.agent.yml exec agent python -m chatdku.core.agent
```

Now you can start chatting with the Agent!

---

## Local Development Mode (Without Docker)

### 1. Install Dependencies

```bash
cd chatdku
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Start Redis and ChromaDB

```bash
docker compose -f docker-compose.agent.yml up redis chromadb -d
```

### 3. Configure Environment Variables

```bash
export REDIS_HOST=localhost
export CHROMA_HOST=localhost
export CHROMA_DB_PORT=8011
export LLM_BASE_URL=http://localhost:18085/v1
export TEI_URL=http://localhost:8080
export LLM_API_KEY=your_api_key
export HF_ENDPOINT=https://hf-mirror.com
```

### 4. Prepare Data

```bash
bash scripts/setup_agent_data.sh
```

### 5. Run Agent

```bash
python -m chatdku.core.agent
```

---

## FAQ

### Q: Python 3.13 compatibility issues?

If using Python 3.13, modify `chatdku/pyproject.toml`:

```bash
# Modify requires-python
requires-python = ">=3.11"

# Modify unstructured version
"unstructured[pdf]>=0.21.0"
```

### Q: Port 8010 occupied?

ChromaDB uses port 8011 by default. If there's still a conflict:

```bash
# 1. Check process using the port
lsof -i :8011

# 2. Modify port mapping in docker-compose.agent.yml
ports:
  - "8012:8010"  # Change to another port

# 3. Update .env file
CHROMA_DB_PORT=8012
```

### Q: Cannot access HuggingFace?

Add mirror configuration in `.env`:

```bash
HF_ENDPOINT=https://hf-mirror.com
```

For local runs, also export the environment variable:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Q: How to deploy LLM service?

Recommended using sglang:

```bash
docker run -d --gpus all -p 18085:18085 \
  lmsysorg/sglang:latest \
  python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-4B \
  --host 0.0.0.0 \
  --port 18085
```

### Q: How to deploy TEI Embedding service?

```bash
docker run -d -p 8080:8080 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3
```

### Q: Port occupied?

Modify port configuration in `.env` file, or modify port mapping in `docker-compose.agent.yml`.

### Q: Data initialization failed?

Ensure:
1. Redis and ChromaDB services are running
2. TEI service is accessible
3. Document files exist in data/ directory

---

## Next Steps

- Check [Full Deployment Guide](./Agent-Only-Deployment_EN.md) for more configuration options
- Check [Data Import Guide](../data/README.md) for data preparation process
- Need Web interface? Check [Full Version Deployment](./Full-Deployment-Guide_EN.md)
