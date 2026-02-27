# ChatDKU Ubuntu 22.04 全功能部署教程（Docker 为主）

本教程适用于 Ubuntu 22.04，默认使用 Docker + Compose，覆盖：
前端、Flask 后端、Redis、Chroma、可选 Django/Postgres/Celery、语音 STT、Phoenix 观测，
以及在服务器上自建 LLM/Embedding（OpenAI 兼容 + TEI）。

---

## 0. 前置说明

- 需要一台 Ubuntu 22.04 服务器（建议 8C16G+）。
- 若要自建 LLM/Embedding，建议具备 NVIDIA GPU。
- 本仓库不包含任何生产数据或密钥，请使用 `.env`/`.env.local` 自行配置。

---

## 1. 服务器准备

### 1.1 安装基础工具
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates
```

### 1.2 安装 Docker 与 Compose 插件
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

### 1.3 可选：GPU 支持

1. 安装 NVIDIA 驱动（按官方文档）。
2. 安装 `nvidia-container-toolkit`：
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```
3. 验证：
```bash
nvidia-smi
```

### 1.4 防火墙端口放行（示例）
```bash
sudo ufw allow 3005
sudo ufw allow 9015
sudo ufw allow 18085
sudo ufw allow 8001
sudo ufw allow 6379
sudo ufw allow 5432
sudo ufw allow 8007
sudo ufw allow 8080
sudo ufw allow 6006
```

---

## 2. 获取代码与环境文件

```bash
git clone <your-repo-url>
cd ChatDKU_2_23
cp .env.example .env
```

如需私密参数，请使用 `.env.local`（不会被提交）：
```bash
cp .env.example .env.local
```

---

## 3. 在服务器上运行 LLM（OpenAI 兼容，SGLang）

使用 sglang 运行 `Qwen3-30B-A3B-Instruct-2507`，并开启 API key：
```bash
nohup python -m sglang.launch_server \
  --model-path /path/to/models/Qwen3-30B-A3B-Instruct-2507 \
  --port 18085 \
  --mem-fraction-static 0.9 \
  --context-length 40000 \
  --allow-auto-truncate \
  --api-key <your_key> > /var/log/sglang_qwen.log 2>&1 &
```

说明：如端口或模型路径不同，请同步修改 `LLM_BASE_URL` 与启动参数。

验证：
```bash
curl http://localhost:18085/v1/models
```

`.env` 中配置：
```
LLM_API_KEY=<your_key>
LLM_BASE_URL=http://<server-ip>:18085/v1
```

---

## 4. 在服务器上运行 Embedding（TEI）

### GPU（推荐）
```bash
docker run --gpus all -p 8080:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3
```

### CPU（无 GPU）
```bash
docker run -p 8080:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3 --device cpu
```

`.env` 中配置：
```
TEI_URL=http://<server-ip>:8080
```

验证：
```bash
curl http://localhost:8080/health
```

---

## 5. 启动 ChatDKU 核心服务（Docker Compose）

```bash
docker compose up --build -d
```

访问：
- 前端：`http://<server-ip>:3005`

说明：Chroma 默认仅容器内访问，如需外网访问可在 `docker-compose.yml` 中为 `chromadb` 添加端口映射（例如 `8010:8010`）。

验证后端（POST /chat）：
```bash
curl -X POST http://<server-ip>:9015/chat \
  -H 'Content-Type: application/json' \
  -d '{"chatHistoryId":"test","messages":[{"role":"user","content":"hello"}]}'
```

---

## 6. 数据摄取（Ingestion）

准备数据目录：
```bash
mkdir -p ./data
```
该目录会通过 Docker 卷挂载到容器内（用于持久化 ingestion 结果）。

进入 backend 容器运行：
```bash
docker compose exec backend bash
cd /app/chatdku/chatdku/ingestion
python update_data.py --data_dir /app/chatdku/chatdku/backend/data --user_id Chat_DKU -v True
python load_chroma.py --nodes_path /app/chatdku/chatdku/backend/data/nodes.json --collection_name chatdku_docs
python -m chatdku.chatdku.ingestion.load_redis --nodes_path /app/chatdku/chatdku/backend/data/nodes.json --index_name chatdku
```

---

## 7. 全功能模式：Django + Postgres + Celery

启动 profile：
```bash
docker compose --profile django up --build -d
```

迁移与管理员：
```bash
docker compose exec django python manage.py migrate
docker compose exec django python manage.py createsuperuser
```

访问：
- 管理后台：`http://<server-ip>:8001/admin`
- OpenAPI 文档：`http://<server-ip>:8001/doc/schema/view`
说明：Docker Compose 下 Django 监听容器内 `8020`，宿主机暴露为 `8001`。

---

## 8. 语音功能（Whisper + STT WebSocket）

### 8.1 启动 Whisper
```bash
python chatdku/chatdku/backend/whisper_model.py
```

### 8.2 启动 STT WebSocket
```bash
python chatdku/chatdku/backend/stt_app.py
```

`.env` 配置：
```
WHISPER_MODEL_URI=http://<server-ip>:5000
NEXT_PUBLIC_DICTATION_WS_URL=ws://<server-ip>:8007
```

HTTPS 场景：
```
SSL_CERT_FILE=/path/to/fullchain.pem
SSL_KEY_FILE=/path/to/privkey.pem
NEXT_PUBLIC_DICTATION_WS_URL=wss://<domain>:8007
```

---

## 9. Phoenix 观测（可选）

```bash
docker compose --profile phoenix up -d
```

`.env.local` 中设置：
```
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <token>
```

访问：`http://<server-ip>:6006`

---

## 10. 反向代理与 HTTPS（可选 Nginx 示例）

```nginx
server {
    listen 80;
    server_name <your-domain>;

    location / {
        proxy_pass http://127.0.0.1:3005;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /socket.io/ {
        proxy_pass http://127.0.0.1:8007;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

启用：
```bash
sudo ln -s /etc/nginx/sites-available/chatdku /etc/nginx/sites-enabled/chatdku
sudo nginx -t
sudo systemctl reload nginx
```

---

## 11. 常见问题排查

- **LLM/TEI 无法访问**
  - 检查 `LLM_BASE_URL`、`TEI_URL` 是否正确指向服务器 IP/端口。
- **Linux 下 `host.docker.internal` 不可用**
  - 直接写服务器 IP，或在 `docker-compose.yml` 增加 `extra_hosts`。
- **CORS 报错**
  - `CORS_ALLOWED_ORIGINS` 与 `NEXT_PUBLIC_API_BASE_URL` 必须一致。
- **Redis/Chroma 连接失败**
  - 确认容器状态、端口放行、`REDIS_HOST`/`CHROMA_HOST` 配置。
- **Redis 认证失败（AUTH 错误）**
  - 若设置了 `REDIS_PASSWORD`，确保 compose 中的 redis 已启用 requirepass（默认已按环境变量自动启用）。

---

## 测试与验收

1. 前端：`http://<server-ip>:3005`
2. LLM API：`curl http://<server-ip>:18085/v1/models`
3. TEI：`curl http://<server-ip>:8080/health`
4. 后端 `/chat` 响应正常（示例见第 5 节）
5. ingestion 后可检索到数据
6. Django admin 登录成功（如启用）：`http://<server-ip>:8001/admin`
