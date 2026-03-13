# ChatDKU Ubuntu 22.04 Full Deployment Guide (Docker-based)

This guide is for Ubuntu 22.04, using Docker + Compose by default, covering:
Frontend, Django backend, PostgreSQL, Redis, Chroma, Celery async tasks, optional STT, Phoenix observability,
and self-hosted LLM/Embedding on server (OpenAI-compatible + TEI).

---

## 0. Prerequisites

- Ubuntu 22.04 server required (recommended 8C16G+)
- NVIDIA GPU recommended for self-hosted LLM/Embedding
- This repository does not include production data or keys, configure using `.env`/`.env.local`
- **Domain not required**: Can access directly using server IP address, domain only needed for production HTTPS certificates and friendly access

---

## 1. Server Preparation

### 1.1 Install Basic Tools
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates
```

### 1.2 Install Docker and Compose Plugin
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

If network issues, install via mirror:
```bash
# Add Docker's GPG key via Aliyun mirror
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add the repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 1.3 Optional: GPU Support

1. Install NVIDIA driver (follow official docs)
2. Install `nvidia-container-toolkit`:
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
3. Verify:
```bash
nvidia-smi
```

### 1.4 Firewall Port Configuration (Example)
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

**Note**: If using Nginx for unified port management (recommended), only open ports 80 and 443:
```bash
sudo ufw allow 80
sudo ufw allow 443
```

---

## 2. Get Code and Environment Files

```bash
git clone https://github.com/Edge-Intelligence-Lab/ChatDKU.git
cd ChatDKU
cp .env.example .env
```

For private parameters, use `.env.local` (not committed):
```bash
cp .env.example .env.local
```

### 2.1 Configure .env File

Edit `.env` file and configure the following key variables:

**Unified Server Address Configuration (Recommended):**
- `SERVER_HOST`: Server IP address or domain (default `localhost`)
  - Local development: `SERVER_HOST=localhost`
  - Server deployment: `SERVER_HOST=<your-server-ip>` (e.g., `175.27.225.52`)
  - All localhost configurations will automatically reference this variable, avoiding repetitive modifications

**Required Configuration (Core Features):**
- `LLM_BASE_URL`: LLM service address (automatically uses `${SERVER_HOST}`)
- `LLM_MODEL`: Model name to use (must match downloaded model)
- `TEI_URL`: Embedding service address (automatically uses `${SERVER_HOST}`)
- `CORS_ALLOWED_ORIGINS`: Frontend access address (automatically uses `${SERVER_HOST}`)
- `NEXT_PUBLIC_API_BASE_URL`: Frontend API address (automatically uses `${SERVER_HOST}`)

**Optional Configuration:**
- `LLM_API_KEY`: LLM API key (can be empty for local sglang deployment)
- `REDIS_PASSWORD`: Redis password (recommended for production)
- `RERANKER_BASE_URL`: Reranker service (optional, improves retrieval quality)
- `WHISPER_MODEL_URI`: Speech recognition service (only needed for voice features)
- `STT_ENABLED`: Enable speech-to-text (default false)
- `DJANGO_*`: Django backend configuration (database, keys, etc.)

**Configuration Method 1: Using Nginx Unified Port (Recommended)**

Only modify `SERVER_HOST` to your server IP, other configurations will automatically reference it:

```bash
# Set server address (only place to modify)
SERVER_HOST=<your-server-ip>

# Other configurations automatically use ${SERVER_HOST}, no modification needed
LLM_BASE_URL=http://${SERVER_HOST}:18085/v1
LLM_MODEL=Qwen/Qwen3.5-4B
TEI_URL=http://${SERVER_HOST}:8080
CORS_ALLOWED_ORIGINS=http://${SERVER_HOST}:8003
NEXT_PUBLIC_API_BASE_URL=http://${SERVER_HOST}:8003
NEXT_PUBLIC_DICTATION_WS_URL=ws://${SERVER_HOST}:8007
DJANGO_ALLOWED_HOSTS=${SERVER_HOST},127.0.0.1
```

**Configuration Method 2: Direct Port Access (Development/Debug)**

Similarly, only modify `SERVER_HOST`:

```bash
# Set server address
SERVER_HOST=<your-server-ip>

# Other configurations automatically use ${SERVER_HOST}
LLM_BASE_URL=http://${SERVER_HOST}:18085/v1
TEI_URL=http://${SERVER_HOST}:8080
CORS_ALLOWED_ORIGINS=http://${SERVER_HOST}:8003
NEXT_PUBLIC_API_BASE_URL=http://${SERVER_HOST}:8003
```

---

## 3. Run LLM on Server (OpenAI-compatible, SGLang)

First install sglang and download model to local directory (example):
```bash
pip install uv
uv pip install "sglang" --prerelease=allow
```

```bash
# Download Qwen3.5-4B model (recommended, low VRAM requirement, suitable for most scenarios)
export HF_ENDPOINT=https://hf-mirror.com

huggingface-cli download Qwen/Qwen3.5-4B \
  --local-dir /home/ubuntu/ChatDKU/models/Qwen3.5-4B
```

Run model using sglang (example using Qwen3.5-4B):
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

**Note**: LLM_MODEL in .env should match the actually downloaded model. For example:
- If downloaded Qwen3.5-4B, set `LLM_MODEL=Qwen/Qwen3.5-4B`
- If downloaded other models, set corresponding model name

### 3.1 Switch to Other Models (Optional)

To use larger models (e.g., Qwen3.5-14B), follow these steps:

**Step 1: Download new model**
```bash
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download Qwen/Qwen3.5-14B \
  --local-dir /home/ubuntu/ChatDKU/models/Qwen3.5-14B
```

**Step 2: Stop current sglang service**
```bash
pkill -f sglang.launch_server
```

**Step 3: Start new model**
```bash
nohup python -m sglang.launch_server \
  --model-path /home/ubuntu/ChatDKU/models/Qwen3.5-14B \
  --host 0.0.0.0 \
  --port 18085 \
  --mem-fraction-static 0.7 \
  --context-length 32000 \
  --allow-auto-truncate > /home/ubuntu/ChatDKU/logs/sglang_qwen.log 2>&1 &
```

**Step 4: Update .env configuration**
```bash
LLM_MODEL=Qwen/Qwen3.5-14B
LLM_CONTEXT_WINDOW=32000
```

**Step 5: Restart services**
```bash
docker compose restart backend frontend
```

Note: If port or model path differs, synchronize modifications to `LLM_BASE_URL` and startup parameters.

Verify:
```bash
curl http://localhost:18085/v1/models
```

Configure in `.env`:
```
LLM_API_KEY=<your_key>
LLM_BASE_URL=http://<server-ip>:18085/v1
```

**Note**: The above sglang startup command does not enable API key verification. To enable, add `--api-key your_key` parameter and set corresponding `LLM_API_KEY` in `.env`.

---

## 4. Run Embedding on Server (TEI)

### GPU (Recommended)
```bash
# Method 1: Download directly from HuggingFace
docker run -d --gpus all -p 8080:80 \
  --name bge-m3 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3

# Method 2: Use locally downloaded model
docker run -d --gpus all -p 8080:80 \
  -v /home/ubuntu/ChatDKU/models/bge-m3:/data \
  --name bge-m3 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id /data
```

### CPU (No GPU)
```bash
docker run -d -p 8080:80 \
  --name bge-m3 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3 --device cpu
```

Configure in `.env`:
```
TEI_URL=http://<server-ip>:8080
```

Verify:
```bash
curl http://localhost:8080/health

curl http://localhost:8080/embed \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"inputs": "Hello, how are you?"}'
```

---

## 5. Start ChatDKU Core Services (Docker Compose)

```bash
docker compose up --build -d
```

Access:
- Frontend: `http://<server-ip>:8003`

Note: Chroma defaults to container-internal access only. For external access, add port mapping in `docker-compose.yml` for `chromadb` (e.g., `8010:8010`).

Verify service startup:
```bash
# 1. Verify container status (all services should show Up)
docker compose ps

# 2. Verify frontend access (should return 200 OK)
curl -I http://localhost:8003

# 3. Verify backend service startup
curl http://localhost:8007/api/get_session

# 4. View backend logs (optional)
docker compose logs backend --tail=20
```

**Note**:
- This only verifies if services started normally, using `localhost` for local server testing
- For external access, open ports 3005 and 9015 in cloud server security groups
- Complete RAG functionality verification requires data ingestion (see Chapter 6)

---

## 6. Data Ingestion

Prepare data directory:
```bash
mkdir -p ./data
```
This directory will be mounted to containers via Docker volume (for persisting ingestion results).

Enter backend container and run:
```bash
docker compose exec backend bash
cd /app/chatdku/chatdku/ingestion
python update_data.py --data_dir /app/chatdku/chatdku/django/chatdku_django/data --user_id Chat_DKU -v True
python load_chroma.py --nodes_path /app/chatdku/chatdku/django/chatdku_django/data/nodes.json --collection_name chatdku_docs
python -m chatdku.ingestion.load_redis --nodes_path /app/chatdku/chatdku/django/chatdku_django/data/nodes.json --index_name chatdku
```

**Note**: `/app/chatdku/chatdku/django/chatdku_django/data` is the container path, corresponding to host's `./data` directory (relative to project root).

Verify RAG functionality:
```bash
# After data ingestion, verify complete RAG retrieval and response functionality
curl -X POST http://localhost:8007/chat \
  -H 'Content-Type: application/json' \
  -H 'UID: test_user' \
  -d '{"mode":"default","chatHistoryId":"692f1234-5678-90ab-cdef-1234567890ab","messages":[{"content":"What is DKU?"}]}'
```

**Note**: This command triggers complete RAG flow (query rewriting → retrieval → judging → synthesis), returning answers based on vector database data. Required parameters: `UID` header (user ID), `mode` (default "default"), `chatHistoryId` (UUID format), `messages` array.

---

## 7. Using Celery Async Tasks (Optional)

To enable Celery for background processing of file uploads and other async tasks:

```bash
docker compose --profile django up --build -d
```

Run database migrations and create admin user:
```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

Access:
- Django Admin: `http://<server-ip>:8007/admin`
- OpenAPI Documentation: `http://<server-ip>:8007/doc/schema/view`

---

## 8. Voice Features (Whisper + STT WebSocket, Optional)

### 8.1 Start Whisper Service
```bash
# Need to run Whisper model service separately
python chatdku/chatdku/whisper_model.py
```

### 8.2 Start Socket.IO STT Service

Enable STT in `.env`:
```
STT_ENABLED=true
WHISPER_MODEL_URI=http://<server-ip>:5000
NEXT_PUBLIC_DICTATION_WS_URL=ws://<server-ip>:18420
STT_HOST=0.0.0.0
STT_PORT=18420
```

Start standalone Socket.IO server:
```bash
cd chatdku/chatdku/django/chatdku_django
python run_socketio.py
```

**Note**:
- STT feature requires running Socket.IO server separately
- Default port is 18420 (avoiding conflict with main backend 8007)
- To run in Docker, add standalone stt service in docker-compose.yml

HTTPS scenario configuration:
```
NEXT_PUBLIC_DICTATION_WS_URL=wss://<domain>:18420
```

---

## 9. Phoenix Observability (Optional)

```bash
docker compose --profile phoenix up -d
```

Set in `.env.local`:
```
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <token>
```

Access: `http://<server-ip>:6006`

---

## 10. Nginx Unified Port Management (Recommended)

### 10.1 Solution Overview

Use Nginx as unified reverse proxy, all services accessible through ports 80/443, simplifying port management and improving security.

**Advantages:**
- Only need to open 2 ports (80/443)
- Database ports not exposed externally
- Unified HTTPS configuration
- Easy to add new services

**Architecture:**
```
Internet (80/443) → Nginx → Services (frontend:8003, backend:8007, etc.)
```

### 10.2 Start Nginx Service

```bash
# Start complete services including Nginx
docker compose up --build -d
```

Nginx automatically proxies the following routes:
- `/` → Frontend
- `/api/*`, `/user/*`, `/chat`, `/feedback`, `/upload` → Backend API
- `/socket.io/*` → STT WebSocket
- `/admin/*` → Django admin backend

**Access using IP address (no domain required):**

Configure `.env` file (assuming server IP is <your-server-ip>):
```bash
# Frontend access through Nginx (port 80)
NEXT_PUBLIC_API_BASE_URL=http://<your-server-ip>
NEXT_PUBLIC_DICTATION_WS_URL=ws://<your-server-ip>/socket.io

# CORS configuration
CORS_ALLOWED_ORIGINS=http://<your-server-ip>

# Django (if using)
DJANGO_CORS_ORIGINS=http://<your-server-ip>
DJANGO_CSRF_TRUSTED_ORIGINS=http://<your-server-ip>
DJANGO_ALLOWED_HOSTS=<your-server-ip>,localhost,127.0.0.1
```

Access methods:
- Frontend: `http://<your-server-ip>/`
- Backend API: `http://<your-server-ip>/api/`
- Django admin: `http://<your-server-ip>/admin/`

### 10.3 Configure HTTPS (Optional)

**Using IP address + self-signed certificate (development):**
```bash
bash scripts/generate-ssl.sh
```

Enable SSL in `.env`:
```bash
NGINX_ENABLE_SSL=true
```

Restart Nginx:
```bash
docker compose restart nginx
```

Access: `https://<your-server-ip>` (browser will show certificate warning, click "Continue" to proceed)

**Using domain + Let's Encrypt (production):**

Note: Let's Encrypt requires domain, does not support IP addresses.

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/
```

Enable SSL in `.env`:
```bash
NGINX_ENABLE_SSL=true
```

Restart Nginx:
```bash
docker compose restart nginx
```

### 10.4 Verify Configuration

```bash
# Check Nginx configuration
docker compose exec nginx nginx -t

# View logs
docker compose logs nginx -f

# Test access
curl http://your-server-ip/
curl http://your-server-ip/api/
```

### 10.5 Troubleshooting

**502 Bad Gateway:**
- Check if backend services are running: `docker compose ps`
- Check network connectivity: `docker compose exec nginx curl http://backend:8007/`

**WebSocket connection failed:**
- Confirm WebSocket connection status in browser developer tools
- Check Nginx logs: `docker compose logs nginx`

**CORS errors:**
- Ensure `CORS_ALLOWED_ORIGINS` in `.env` includes correct domain

---

## 11. Reverse Proxy and HTTPS (Traditional Method, Optional)

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

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/chatdku /etc/nginx/sites-enabled/chatdku
sudo nginx -t
sudo systemctl reload nginx
```

---

## 12. Common Troubleshooting

- **LLM/TEI inaccessible**
  - Check if `LLM_BASE_URL` and `TEI_URL` correctly point to server IP/port
- **`host.docker.internal` not available on Linux**
  - Use server IP directly, or add `extra_hosts` in `docker-compose.yml`
- **CORS errors**
  - `CORS_ALLOWED_ORIGINS` and `NEXT_PUBLIC_API_BASE_URL` must match
- **Redis/Chroma connection failed**
  - Confirm container status, port access, `REDIS_HOST`/`CHROMA_HOST` configuration
- **Redis authentication failed (AUTH error)**
  - If `REDIS_PASSWORD` is set, ensure redis in compose has requirepass enabled (automatically enabled by environment variable by default)

---

## Testing and Acceptance

**Using Nginx unified port (recommended):**

Assuming server IP is <your-server-ip>

1. Frontend: `http://<your-server-ip>/`
2. Backend API: `curl http://<your-server-ip>/api/`
3. LLM API: `curl http://<your-server-ip>:18085/v1/models`
4. TEI: `curl http://<your-server-ip>:8080/health`
5. Django admin (if enabled): `http://<your-server-ip>/admin/`

**Direct port access (development/debug):**

1. Frontend: `http://<your-server-ip>:8003`
2. Backend API: `curl http://<your-server-ip>:8007/chat -X POST -H 'Content-Type: application/json' -d '{"chatHistoryId":"test","messages":[{"role":"user","content":"hello"}]}'`
3. LLM API: `curl http://<your-server-ip>:18085/v1/models`
4. TEI: `curl http://<your-server-ip>:8080/health`
5. Django admin (if enabled): `http://<your-server-ip>:8001/admin`
