# ChatDKU Agent-Only 完整部署指南

本指南提供 Agent-Only 版本的详细部署说明，包括环境配置、故障排查和性能优化。

---

## 系统架构

Agent-Only 版本包含以下组件：

```
┌─────────────────────────────────────────┐
│         ChatDKU Agent (CLI)             │
│  - DSPy Agent 逻辑                       │
│  - 查询重写和判断                         │
│  - 答案合成                              │
└─────────────────────────────────────────┘
           ↓                    ↓
    ┌──────────┐          ┌──────────┐
    │  Redis   │          │ ChromaDB │
    │ (关键词)  │          │  (向量)   │
    └──────────┘          └──────────┘
           ↓                    ↓
    ┌─────────────────────────────────┐
    │   外部服务（需单独部署）          │
    │  - LLM (sglang/vLLM)            │
    │  - TEI (Embedding)              │
    └─────────────────────────────────┘
```

---

## 详细部署步骤

### 1. 环境准备

#### 1.1 安装 Docker

Ubuntu/Debian:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

#### 1.2 GPU 支持（可选，用于 LLM）

```bash
# 安装 NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. 部署外部服务

#### 2.1 部署 LLM 服务（sglang）

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

验证服务：
```bash
curl http://localhost:18085/v1/models
```

#### 2.2 部署 TEI Embedding 服务

```bash
docker run -d --name tei \
  -p 8080:8080 \
  -v ~/.cache/huggingface:/data \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3 \
  --port 8080
```

验证服务：
```bash
curl http://localhost:8080/health
```

### 3. 部署 ChatDKU Agent

#### 3.1 克隆代码

```bash
git clone https://github.com/Edge-Intelligence-Lab/ChatDKU.git
cd ChatDKU
```

#### 3.2 配置环境变量

```bash
cp .env.agent .env
vim .env  # 或使用其他编辑器
```

关键配置项：

```bash
# LLM 配置
LLM_API_KEY=your_key_here
LLM_BASE_URL=http://localhost:18085/v1
LLM_MODEL=Qwen/Qwen3.5-4B
LLM_TEMPERATURE=0.7
LLM_CONTEXT_WINDOW=32000

# Embedding 配置
EMBEDDING_MODEL=BAAI/bge-m3
TEI_URL=http://localhost:8080

# Redis 配置
REDIS_HOST=redis
REDIS_PASSWORD=  # 留空表示无密码

# ChromaDB 配置
CHROMA_HOST=chromadb
CHROMA_DB_PORT=8010
CHROMA_COLLECTION=chatdku_docs
```

#### 3.3 准备数据

将文档放入 `data/` 目录：

```bash
mkdir -p data
cp /path/to/your/documents/* ./data/
```

启动 Redis 和 ChromaDB：

```bash
docker compose -f docker-compose.agent.yml up redis chromadb -d
```

运行数据初始化：

```bash
bash scripts/setup_agent_data.sh
```

#### 3.4 启动 Agent

```bash
docker compose -f docker-compose.agent.yml up -d
```

查看日志：

```bash
docker compose -f docker-compose.agent.yml logs -f agent
```

#### 3.5 进入 Agent CLI

```bash
docker compose -f docker-compose.agent.yml exec agent python -m chatdku.core.agent
```

---

## 环境变量详解

### LLM 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM API 密钥 | - |
| `LLM_BASE_URL` | LLM 服务地址 | `http://localhost:18085/v1` |
| `LLM_MODEL` | 模型名称 | `Qwen/Qwen3.5-4B` |
| `LLM_TEMPERATURE` | 温度参数 | `0.7` |
| `LLM_CONTEXT_WINDOW` | 上下文窗口大小 | `32000` |

### Embedding 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TEI_URL` | TEI 服务地址 | `http://localhost:8080` |
| `EMBEDDING_MODEL` | Embedding 模型 | `BAAI/bge-m3` |
| `TOKENIZER_PATH` | Tokenizer 路径 | `Qwen/Qwen3.5-4B` |

### 存储配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `REDIS_HOST` | Redis 主机 | `redis` |
| `REDIS_PASSWORD` | Redis 密码 | 空 |
| `CHROMA_HOST` | ChromaDB 主机 | `chromadb` |
| `CHROMA_DB_PORT` | ChromaDB 端口 | `8010` |

---

## 故障排查

### 问题 1: Agent 无法连接 LLM

**症状**：
```
Connection refused to http://host.docker.internal:18085
```

**解决方案**：
1. 检查 LLM 服务是否运行：`docker ps | grep sglang`
2. 测试连接：`curl http://localhost:18085/v1/models`
3. 确认 `.env` 中 `LLM_BASE_URL` 配置正确

### 问题 2: 数据加载失败

**症状**：
```
Failed to connect to ChromaDB
```

**解决方案**：
1. 确认 Redis 和 ChromaDB 已启动
2. 检查端口是否被占用：`netstat -tuln | grep 6379`
3. 查看容器日志：`docker compose -f docker-compose.agent.yml logs chromadb`

### 问题 3: 内存不足

**症状**：
```
OOMKilled
```

**解决方案**：
1. 增加 Docker 内存限制
2. 使用更小的模型
3. 减少 `LLM_CONTEXT_WINDOW`

---

## 性能优化

### 1. 使用更快的 Embedding 模型

```bash
# 使用更小的模型
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### 2. 调整检索参数

编辑 `chatdku/core/agent.py` 中的检索参数：
- `similarity_top_k`: 减少检索数量
- `max_iterations`: 减少最大迭代次数

### 3. 启用 Phoenix 观测（可选）

```bash
# 在 .env 中添加
PHOENIX_HOST=localhost
PHOENIX_PORT=6006
```

启动 Phoenix：
```bash
docker run -d -p 6006:6006 arizephoenix/phoenix:latest
```

---

## 下一步

- 了解如何自定义 Agent 行为
- 查看 [Full 版本](./Full-Deployment-Guide_ZH.md) 获取 Web 界面
- 集成到您的应用中
