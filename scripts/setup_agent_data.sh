#!/bin/bash
set -e

echo "=== ChatDKU Agent-Only 数据初始化 ==="

# 检查数据目录
if [ ! -d "./data" ]; then
    echo "创建数据目录..."
    mkdir -p ./data
fi

# 生成 nodes.json
if [ ! -f "./data/nodes.json" ]; then
    echo "处理文档并生成 nodes.json..."
    python -m chatdku.ingestion.update_data \
        --data_dir ./data \
        --user_id Chat_DKU \
        -v True
else
    echo "nodes.json 已存在，跳过文档处理"
fi

# 加载到 ChromaDB
echo "加载数据到 ChromaDB..."
python -m chatdku.ingestion.load_chroma \
    --nodes_path ./data/nodes.json \
    --collection_name chatdku_docs

# 加载到 Redis
echo "加载数据到 Redis..."
python -m chatdku.ingestion.load_redis \
    --nodes_path ./data/nodes.json \
    --index_name chatdku

echo "=== 数据初始化完成 ==="
