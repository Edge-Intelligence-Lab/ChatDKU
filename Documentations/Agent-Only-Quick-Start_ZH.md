# ChatDKU Agent-Only 快速开始指南

本指南帮助您在 5-10 分钟内快速部署 ChatDKU Agent-Only 版本。

---

## 前置条件

### 必需
- Docker 和 Docker Compose
- Python 3.11 或 3.12（本地开发模式）
- 可访问的 LLM 服务（OpenAI 兼容 API）
- 可访问的 TEI Embedding 服务

### 推荐配置
- 2C4G+ 内存（Agent 本身）
- LLM 服务建议使用 GPU（如 sglang）

### 注意事项
- Python 3.13 需要修改依赖版本（见常见问题）
- 确保 8011（ChromaDB）、6379（Redis）端口未被占用

---

## 快速部署（Docker）

### 1. 克隆仓库

```bash
git clone https://github.com/Edge-Intelligence-Lab/ChatDKU.git
cd ChatDKU
```

### 2. 配置环境变量

```bash
cp .env.agent .env
```

编辑 `.env` 文件，设置以下关键参数：

```bash
# LLM 服务地址（必需）
LLM_BASE_URL=http://localhost:18085/v1
LLM_API_KEY=your_api_key

# Embedding 服务地址（必需）
TEI_URL=http://localhost:8080

# HuggingFace 镜像（中国大陆推荐）
HF_ENDPOINT=https://hf-mirror.com
```

### 3. 准备数据（可选）

如果您有自己的文档数据：

```bash
# 将文档放入 data/ 目录
cp your_documents/* ./data/

# 启动所有服务（包括 agent 容器）
docker compose -f docker-compose.agent.yml up -d

# 在 agent 容器内运行数据初始化
docker compose -f docker-compose.agent.yml exec agent bash scripts/setup_agent_data.sh
```

**注意**：数据初始化脚本必须在 agent 容器内运行，因为它需要连接容器网络中的 Redis 和 ChromaDB。

### 4. 测试 Agent

```bash
docker compose -f docker-compose.agent.yml exec agent python -m chatdku.core.agent
```

现在您可以开始与 Agent 对话了！

---

## 本地开发模式（不使用 Docker）

### 1. 安装依赖

```bash
cd chatdku
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. 启动 Redis 和 ChromaDB

```bash
docker compose -f docker-compose.agent.yml up redis chromadb -d
```

### 3. 配置环境变量

```bash
export REDIS_HOST=localhost
export CHROMA_HOST=localhost
export CHROMA_DB_PORT=8011
export LLM_BASE_URL=http://localhost:18085/v1
export TEI_URL=http://localhost:8080
export LLM_API_KEY=your_api_key
export HF_ENDPOINT=https://hf-mirror.com
```

### 4. 准备数据

```bash
bash scripts/setup_agent_data.sh
```

### 5. 运行 Agent

```bash
python -m chatdku.core.agent
```

---

## 常见问题

### Q: Python 3.13 兼容性问题？

如果使用 Python 3.13，需要修改 `chatdku/pyproject.toml`：

```bash
# 修改 requires-python
requires-python = ">=3.11"

# 修改 unstructured 版本
"unstructured[pdf]>=0.21.0"
```

### Q: 端口 8010 被占用？

ChromaDB 默认使用 8011 端口。如果仍有冲突：

```bash
# 1. 查看占用进程
lsof -i :8011

# 2. 修改 docker-compose.agent.yml 中的端口映射
ports:
  - "8012:8010"  # 改为其他端口

# 3. 更新 .env 文件
CHROMA_DB_PORT=8012
```

### Q: 无法访问 HuggingFace？

在 `.env` 中添加镜像配置：

```bash
HF_ENDPOINT=https://hf-mirror.com
```

本地运行时也需要导出环境变量：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Q: 如何部署 LLM 服务？

推荐使用 sglang：

```bash
docker run -d --gpus all -p 18085:18085 \
  lmsysorg/sglang:latest \
  python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-4B \
  --host 0.0.0.0 \
  --port 18085
```

### Q: 如何部署 TEI Embedding 服务？

```bash
docker run -d -p 8080:8080 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3
```

### Q: 端口被占用怎么办？

修改 `.env` 文件中的端口配置，或在 `docker-compose.agent.yml` 中修改端口映射。

### Q: 数据初始化失败？

确保：
1. Redis 和 ChromaDB 服务已启动
2. TEI 服务可访问
3. data/ 目录中有文档文件

---

## 下一步

- 查看 [完整部署指南](./Agent-Only-Deployment_ZH.md) 了解更多配置选项
- 查看 [数据导入指南](../data/README.md) 了解数据准备流程
- 需要 Web 界面？查看 [Full 版本部署](./Full-Deployment-Guide_ZH.md)
