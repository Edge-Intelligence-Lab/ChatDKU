# ChatDKU Agent-Only Complete Deployment Guide

This guide provides detailed deployment instructions for the Agent-Only version, including environment configuration, troubleshooting, and performance optimization.

---

## System Architecture

The Agent-Only version includes the following components:

```
┌─────────────────────────────────────────┐
│         ChatDKU Agent (CLI)             │
│  - DSPy Agent Logic                     │
│  - Query Rewriting and Judging          │
│  - Answer Synthesis                     │
└─────────────────────────────────────────┘
           ↓                    ↓
    ┌──────────┐          ┌──────────┐
    │  Redis   │          │ ChromaDB │
    │(Keyword) │          │ (Vector) │
    └──────────┘          └──────────┘
           ↓                    ↓
    ┌─────────────────────────────────┐
    │   External Services (Deploy     │
    │   Separately)                   │
    │  - LLM (sglang/vLLM)            │
    │  - TEI (Embedding)              │
    └─────────────────────────────────┘
```

---

## Detailed Deployment Steps

### 1. Environment Preparation

#### 1.1 Install Docker

Ubuntu/Debian:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

#### 1.2 GPU Support (Optional, for LLM)

```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Deploy External Services

#### 2.1 Deploy LLM Service (sglang)

```bash
docker run -d --name sglang \
  --gpus all \
  -p 18085:18085 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  lmsysorg/sglang:latest \
  python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-4B \
  --host 0.0.0.0 \
  --port 18085 \
  --tp 1
```

Verify service:
```bash
curl http://localhost:18085/v1/models
```

#### 2.2 Deploy TEI Embedding Service

```bash
docker run -d --name tei \
  -p 8080:8080 \
  -v ~/.cache/huggingface:/data \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3 \
  --port 8080
```

Verify service:
```bash
curl http://localhost:8080/health
```

### 3. Deploy ChatDKU Agent

#### 3.1 Clone Code

```bash
git clone https://github.com/Edge-Intelligence-Lab/ChatDKU.git
cd ChatDKU
```

#### 3.2 Configure Environment Variables

```bash
cp .env.agent .env
vim .env  # or use another editor
```

Key configuration items:

```bash
# LLM Configuration
LLM_API_KEY=your_key_here
LLM_BASE_URL=http://localhost:18085/v1
LLM_MODEL=Qwen/Qwen3.5-4B
LLM_TEMPERATURE=0.7
LLM_CONTEXT_WINDOW=32000

# Embedding Configuration
EMBEDDING_MODEL=BAAI/bge-m3
TEI_URL=http://localhost:8080

# Redis Configuration
REDIS_HOST=redis
REDIS_PASSWORD=  # Leave empty for no password

# ChromaDB Configuration
CHROMA_HOST=chromadb
CHROMA_DB_PORT=8010
CHROMA_COLLECTION=chatdku_docs
```

#### 3.3 Prepare Data

Place documents in the `data/` directory:

```bash
mkdir -p data
cp /path/to/your/documents/* ./data/
```

Start Redis and ChromaDB:

```bash
docker compose -f docker-compose.agent.yml up redis chromadb -d
```

Run data initialization:

```bash
bash scripts/setup_agent_data.sh
```

#### 3.4 Start Agent

```bash
docker compose -f docker-compose.agent.yml up -d
```

View logs:

```bash
docker compose -f docker-compose.agent.yml logs -f agent
```

#### 3.5 Enter Agent CLI

```bash
docker compose -f docker-compose.agent.yml exec agent python -m chatdku.core.agent
```

---

## Environment Variables Explained

### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | LLM API key | - |
| `LLM_BASE_URL` | LLM service address | `http://localhost:18085/v1` |
| `LLM_MODEL` | Model name | `Qwen/Qwen3.5-4B` |
| `LLM_TEMPERATURE` | Temperature parameter | `0.7` |
| `LLM_CONTEXT_WINDOW` | Context window size | `32000` |

### Embedding Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TEI_URL` | TEI service address | `http://localhost:8080` |
| `EMBEDDING_MODEL` | Embedding model | `BAAI/bge-m3` |
| `TOKENIZER_PATH` | Tokenizer path | `Qwen/Qwen3.5-4B` |

### Storage Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis host | `redis` |
| `REDIS_PASSWORD` | Redis password | Empty |
| `CHROMA_HOST` | ChromaDB host | `chromadb` |
| `CHROMA_DB_PORT` | ChromaDB port | `8010` |

---

## Troubleshooting

### Issue 1: Agent Cannot Connect to LLM

**Symptoms**:
```
Connection refused to http://host.docker.internal:18085
```

**Solutions**:
1. Check if LLM service is running: `docker ps | grep sglang`
2. Test connection: `curl http://localhost:18085/v1/models`
3. Verify `LLM_BASE_URL` in `.env` is configured correctly

### Issue 2: Data Loading Failed

**Symptoms**:
```
Failed to connect to ChromaDB
```

**Solutions**:
1. Confirm Redis and ChromaDB are started
2. Check if ports are occupied: `netstat -tuln | grep 6379`
3. View container logs: `docker compose -f docker-compose.agent.yml logs chromadb`

### Issue 3: Out of Memory

**Symptoms**:
```
OOMKilled
```

**Solutions**:
1. Increase Docker memory limit
2. Use a smaller model
3. Reduce `LLM_CONTEXT_WINDOW`

---

## Performance Optimization

### 1. Use Faster Embedding Model

```bash
# Use a smaller model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### 2. Adjust Retrieval Parameters

Edit retrieval parameters in `chatdku/core/agent.py`:
- `similarity_top_k`: Reduce retrieval count
- `max_iterations`: Reduce maximum iterations

### 3. Enable Phoenix Observability (Optional)

```bash
# Add to .env
PHOENIX_HOST=localhost
PHOENIX_PORT=6006
```

Start Phoenix:
```bash
docker run -d -p 6006:6006 arizephoenix/phoenix:latest
```

---

## Next Steps

- Learn how to customize Agent behavior
- Check [Full Version](./Full-Deployment-Guide_EN.md) for Web interface
- Integrate into your application
