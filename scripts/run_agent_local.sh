#!/bin/bash
set -e

echo "=== ChatDKU Agent 本地运行 ==="

# 启动 Redis 和 ChromaDB
echo "启动 Redis 和 ChromaDB..."
docker compose -f docker-compose.agent.yml up redis chromadb -d

# 等待服务就绪
echo "等待服务启动..."
sleep 3

# 设置环境变量
export REDIS_HOST=localhost
export CHROMA_HOST=localhost
export LLM_BASE_URL=${LLM_BASE_URL:-http://localhost:18085/v1}
export TEI_URL=${TEI_URL:-http://localhost:8080}

echo "环境变量已设置"
echo "LLM_BASE_URL: $LLM_BASE_URL"
echo "TEI_URL: $TEI_URL"

# 运行 Agent
echo "启动 Agent..."
cd chatdku
python -m chatdku.core.agent
