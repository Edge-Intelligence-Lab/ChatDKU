# ChatDKU Ubuntu 22.04 全功能部署教程（Docker 为主）

本教程适用于 Ubuntu 22.04，默认使用 Docker + Compose，覆盖：
前端、Django 后端、PostgreSQL、Redis、Chroma、Celery 异步任务、可选语音 STT、Phoenix 观测，
以及在服务器上自建 LLM/Embedding（OpenAI 兼容 + TEI）。

---

## 0. 前置说明

- 需要一台 Ubuntu 22.04 服务器（建议 8C16G+）。
- 若要自建 LLM/Embedding，建议具备 NVIDIA GPU。
- 本仓库不包含任何生产数据或密钥，请使用 `.env`/`.env.local` 自行配置。
- **不需要域名**：可以直接使用服务器 IP 地址访问，域名仅用于生产环境的 HTTPS 证书和友好访问。

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

如果有网络问题，可以通过镜像安装：
```bash
# Add Docker's GPG key via Aliyun mirror
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add the repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
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

**注意**：如果使用 Nginx 统一端口管理（推荐），仅需开放 80 和 443 端口：
```bash
sudo ufw allow 80
sudo ufw allow 443
```

---

## 2. 获取代码与环境文件

```bash
git clone https://github.com/Edge-Intelligence-Lab/ChatDKU.git
cd ChatDKU
cp .env.example .env
```

如需私密参数，请使用 `.env.local`（不会被提交）：
```bash
cp .env.example .env.local
```

### 2.1 配置 .env 文件

编辑 `.env` 文件，配置以下关键变量：

**服务器地址统一配置（推荐）：**
- `SERVER_HOST`: 服务器 IP 地址或域名（默认 `localhost`）
  - 本地开发：`SERVER_HOST=localhost`
  - 服务器部署：`SERVER_HOST=<your-server-ip>`（如 `175.27.225.52`）
  - 所有使用 localhost 的配置项会自动引用此变量，避免重复修改

**必需配置（核心功能）：**
- `LLM_BASE_URL`: LLM 服务地址（已自动使用 `${SERVER_HOST}`）
- `LLM_MODEL`: 使用的模型名称（需与下载的模型匹配）
- `TEI_URL`: Embedding 服务地址（已自动使用 `${SERVER_HOST}`）
- `CORS_ALLOWED_ORIGINS`: 前端访问地址（已自动使用 `${SERVER_HOST}`）
- `NEXT_PUBLIC_API_BASE_URL`: 前端 API 地址（已自动使用 `${SERVER_HOST}`）

**可选配置：**
- `LLM_API_KEY`: LLM API 密钥（本地 sglang 部署可留空）
- `REDIS_PASSWORD`: Redis 密码（建议生产环境设置）
- `RERANKER_BASE_URL`: Reranker 服务（可选，提升检索质量）
- `WHISPER_MODEL_URI`: 语音识别服务（仅需语音功能时配置）
- `STT_ENABLED`: 是否启用语音转文字功能（默认 false）
- `DJANGO_*`: Django 后端配置（数据库、密钥等）

**配置方式 1：使用 Nginx 统一端口（推荐）**

只需修改 `SERVER_HOST` 为你的服务器 IP，其他配置会自动引用：

```bash
# 设置服务器地址（唯一需要修改的地方）
SERVER_HOST=<your-server-ip>

# 其他配置已自动使用 ${SERVER_HOST}，无需修改
LLM_BASE_URL=http://${SERVER_HOST}:18085/v1
LLM_MODEL=Qwen/Qwen3.5-4B
TEI_URL=http://${SERVER_HOST}:8080
CORS_ALLOWED_ORIGINS=http://${SERVER_HOST}:8003
NEXT_PUBLIC_API_BASE_URL=http://${SERVER_HOST}:8003
NEXT_PUBLIC_DICTATION_WS_URL=ws://${SERVER_HOST}:8007
DJANGO_ALLOWED_HOSTS=${SERVER_HOST},127.0.0.1
```

**配置方式 2：直接端口访问（开发/调试）**

同样只需修改 `SERVER_HOST`：

```bash
# 设置服务器地址
SERVER_HOST=<your-server-ip>

# 其他配置已自动使用 ${SERVER_HOST}
LLM_BASE_URL=http://${SERVER_HOST}:18085/v1
TEI_URL=http://${SERVER_HOST}:8080
CORS_ALLOWED_ORIGINS=http://${SERVER_HOST}:8003
NEXT_PUBLIC_API_BASE_URL=http://${SERVER_HOST}:8003
```

---

## 3. 在服务器上运行 LLM（OpenAI 兼容，SGLang）

先安装 sglang 并下载模型到本地目录（示例）：
```bash
pip install uv
uv pip install "sglang" --prerelease=allow

```bash
# 下载 Qwen3.5-4B 模型（推荐，显存需求低，适合大多数场景）
export HF_ENDPOINT=https://hf-mirror.com

huggingface-cli download Qwen/Qwen3.5-4B \
  --local-dir /home/ubuntu/ChatDKU/models/Qwen3.5-4B
```


使用 sglang 运行模型（示例使用 Qwen3.5-4B）：
```bash
nohup python -m sglang.launch_server \
  --model-path /home/ubuntu/ChatDKU/models/Qwen3.5-4B \
  --host 0.0.0.0 \
  --port 18085 \
  --mem-fraction-static 0.6 \
  --context-length 32000 \
  --allow-auto-truncate > /home/ubuntu/ChatDKU/logs/sglang_qwen.log 2>&1 &


pkill -f sglang.launch_server

```

**注意**：.env 中的 LLM_MODEL 应与实际下载的模型匹配。例如：
- 如果下载了 Qwen3.5-4B，设置 `LLM_MODEL=Qwen/Qwen3.5-4B`
- 如果下载了其他模型，设置对应的模型名称

### 3.1 切换到其他模型（可选）

如需使用更大的模型（如 Qwen3.5-14B），按以下步骤操作：

**步骤 1：下载新模型**
```bash
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download Qwen/Qwen3.5-14B \
  --local-dir /home/ubuntu/ChatDKU/models/Qwen3.5-14B
```

**步骤 2：停止当前 sglang 服务**
```bash
pkill -f sglang.launch_server
```

**步骤 3：启动新模型**
```bash
nohup python -m sglang.launch_server \
  --model-path /home/ubuntu/ChatDKU/models/Qwen3.5-14B \
  --host 0.0.0.0 \
  --port 18085 \
  --mem-fraction-static 0.7 \
  --context-length 32000 \
  --allow-auto-truncate > /home/ubuntu/ChatDKU/logs/sglang_qwen.log 2>&1 &
```

**步骤 4：更新 .env 配置**
```bash
LLM_MODEL=Qwen/Qwen3.5-14B
LLM_CONTEXT_WINDOW=32000
```

**步骤 5：重启服务**
```bash
docker compose restart backend frontend
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

**注意**：上述 sglang 启动命令未启用 API key 验证。如需启用，添加 `--api-key your_key` 参数，并在 `.env` 中设置对应的 `LLM_API_KEY`。

---

## 4. 在服务器上运行 Embedding（TEI）

### GPU（推荐）
```bash
# 方式1：直接从 HuggingFace 下载
docker run -d --gpus all -p 8080:80 \
  --name bge-m3 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3

# 方式2：使用本地已下载的模型
docker run -d --gpus all -p 8080:80 \
  -v /home/ubuntu/ChatDKU/models/bge-m3:/data \
  --name bge-m3 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id /data
```

### CPU（无 GPU）
```bash
docker run -d -p 8080:80 \
  --name bge-m3 \
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

curl http://localhost:8080/embed \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"inputs": "Hello, how are you?"}'
```

---

## 5. 启动 ChatDKU 核心服务（Docker Compose）

```bash
docker compose up --build -d
```

访问：
- 前端：`http://<server-ip>:8003`

说明：Chroma 默认仅容器内访问，如需外网访问可在 `docker-compose.yml` 中为 `chromadb` 添加端口映射（例如 `8010:8010`）。

验证服务启动：
```bash
# 1. 验证容器状态（所有服务应显示 Up）
docker compose ps

# 2. 验证前端访问（应返回 200 OK）
curl -I http://localhost:8003

# 3. 验证后端服务启动
curl http://localhost:8007/api/get_session

# 4. 查看后端日志（可选）
docker compose logs backend --tail=20
```

**说明**：
- 此时仅验证服务是否正常启动，使用 `localhost` 在服务器本地测试
- 如需从外部访问，需在云服务器安全组中开放 3005 和 9015 端口
- 完整的 RAG 功能验证需要在数据摄取后进行（见第 6 章节）

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
python update_data.py --data_dir /app/chatdku/chatdku/django/chatdku_django/data --user_id Chat_DKU -v True
python load_chroma.py --nodes_path /app/chatdku/chatdku/django/chatdku_django/data/nodes.json --collection_name chatdku_docs
python -m chatdku.ingestion.load_redis --nodes_path /app/chatdku/chatdku/django/chatdku_django/data/nodes.json --index_name chatdku
```

**说明**：`/app/chatdku/chatdku/django/chatdku_django/data` 是容器内路径，对应宿主机的 `./data` 目录（相对于项目根目录）。

验证 RAG 功能：
```bash
# 数据摄取完成后，验证完整的 RAG 检索和回答功能
curl -X POST http://localhost:8007/chat \
  -H 'Content-Type: application/json' \
  -H 'UID: test_user' \
  -d '{"mode":"default","chatHistoryId":"692f1234-5678-90ab-cdef-1234567890ab","messages":[{"content":"DKU 是什么？"}]}'
```

**说明**：此命令会触发完整的 RAG 流程（查询重写 → 检索 → 判断 → 合成），返回基于向量数据库中数据的回答。必需参数：`UID` header（用户标识）、`mode`（默认 "default"）、`chatHistoryId`（UUID 格式）、`messages` 数组。

---

## 7. 使用 Celery 异步任务（可选）

如需启用 Celery 进行文件上传后台处理等异步任务：

```bash
docker compose --profile django up --build -d
```

运行数据库迁移和创建管理员：
```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

访问：
- Django Admin：`http://<server-ip>:8007/admin`
- OpenAPI 文档：`http://<server-ip>:8007/doc/schema/view`

---

## 8. 语音功能（Whisper + STT WebSocket，可选）

### 8.1 启动 Whisper 服务
```bash
# 需要单独运行 Whisper 模型服务
python chatdku/chatdku/whisper_model.py
```

### 8.2 启动 Socket.IO STT 服务

在 `.env` 中启用 STT：
```
STT_ENABLED=true
WHISPER_MODEL_URI=http://<server-ip>:5000
NEXT_PUBLIC_DICTATION_WS_URL=ws://<server-ip>:18420
STT_HOST=0.0.0.0
STT_PORT=18420
```

启动独立的 Socket.IO 服务器：
```bash
cd chatdku/chatdku/django/chatdku_django
python run_socketio.py
```

**说明**：
- STT 功能需要单独运行 Socket.IO 服务器
- 默认端口为 18420（避免与主后端 8007 冲突）
- 如需在 Docker 中运行，需要在 docker-compose.yml 中添加独立的 stt 服务

HTTPS 场景配置：
```
NEXT_PUBLIC_DICTATION_WS_URL=wss://<domain>:18420
```
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

## 10. Nginx 统一端口管理（推荐）

### 10.1 方案说明

使用 Nginx 作为统一反向代理，所有服务通过 80/443 端口访问，简化端口管理和提升安全性。

**优势：**
- 仅需开放 2 个端口（80/443）
- 数据库端口不对外暴露
- 统一 HTTPS 配置
- 便于添加新服务

**架构：**
```
Internet (80/443) → Nginx → 各服务（frontend:8003, backend:8007, etc.）
```

### 10.2 启动 Nginx 服务

```bash
# 启动包含 Nginx 的完整服务
docker compose up --build -d
```

Nginx 会自动代理以下路由：
- `/` → 前端
- `/api/*`, `/user/*`, `/chat`, `/feedback`, `/upload` → 后端 API
- `/socket.io/*` → STT WebSocket
- `/admin/*` → Django 管理后台

**使用 IP 地址访问（无需域名）：**

配置 `.env` 文件（假设服务器 IP 是 <your-server-ip>）：
```bash
# 前端通过 Nginx 访问（80 端口）
NEXT_PUBLIC_API_BASE_URL=http://<your-server-ip>
NEXT_PUBLIC_DICTATION_WS_URL=ws://<your-server-ip>/socket.io

# CORS 配置
CORS_ALLOWED_ORIGINS=http://<your-server-ip>

# Django（如果使用）
DJANGO_CORS_ORIGINS=http://<your-server-ip>
DJANGO_CSRF_TRUSTED_ORIGINS=http://<your-server-ip>
DJANGO_ALLOWED_HOSTS=<your-server-ip>,localhost,127.0.0.1
```

访问方式：
- 前端：`http://<your-server-ip>/`
- 后端 API：`http://<your-server-ip>/api/`
- Django 管理：`http://<your-server-ip>/admin/`

### 10.3 配置 HTTPS（可选）

**使用 IP 地址 + 自签名证书（开发环境）：**
```bash
bash scripts/generate-ssl.sh
```

在 `.env` 中启用 SSL：
```bash
NGINX_ENABLE_SSL=true
```

重启 Nginx：
```bash
docker compose restart nginx
```

访问：`https://<your-server-ip>`（浏览器会提示证书不受信任，点击"继续访问"即可）

**使用域名 + Let's Encrypt（生产环境）：**

注意：Let's Encrypt 需要域名，不支持 IP 地址。

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/
```

在 `.env` 中启用 SSL：
```bash
NGINX_ENABLE_SSL=true
```

重启 Nginx：
```bash
docker compose restart nginx
```

### 10.4 验证配置

```bash
# 检查 Nginx 配置
docker compose exec nginx nginx -t

# 查看日志
docker compose logs nginx -f

# 测试访问
curl http://your-server-ip/
curl http://your-server-ip/api/
```

### 10.5 故障排查

**502 Bad Gateway：**
- 检查后端服务是否启动：`docker compose ps`
- 检查网络连通性：`docker compose exec nginx curl http://backend:8007/`

**WebSocket 连接失败：**
- 确认浏览器开发者工具中 WebSocket 连接状态
- 检查 Nginx 日志：`docker compose logs nginx`

**CORS 错误：**
- 确保 `.env` 中 `CORS_ALLOWED_ORIGINS` 包含正确的域名

---

## 11. 反向代理与 HTTPS（传统方式，可选）

```nginx
server {
    listen 80;
    server_name <your-domain>;

    location / {
        proxy_pass http://127.0.0.1:8003;
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

**使用 Nginx 统一端口（推荐）：**

假设服务器 IP 是 <your-server-ip>

1. 前端：`http://<your-server-ip>/`
2. 后端 API：`curl http://<your-server-ip>/api/`
3. LLM API：`curl http://<your-server-ip>:18085/v1/models`
4. TEI：`curl http://<your-server-ip>:8080/health`
5. Django admin（如启用）：`http://<your-server-ip>/admin/`

**直接端口访问（开发/调试）：**

1. 前端：`http://<your-server-ip>:8003`
2. 后端 API：`curl http://<your-server-ip>:8007/chat -X POST -H 'Content-Type: application/json' -d '{"chatHistoryId":"test","messages":[{"role":"user","content":"hello"}]}'`
3. LLM API：`curl http://<your-server-ip>:18085/v1/models`
4. TEI：`curl http://<your-server-ip>:8080/health`
5. Django admin（如启用）：`http://<your-server-ip>:8001/admin`
