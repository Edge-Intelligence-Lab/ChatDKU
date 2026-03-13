# ChatDKU System Architecture and Port Documentation

This document explains all services, ports, and their purposes in the ChatDKU system.

---

## 📊 System Architecture Overview

```
User Browser
    ↓
[Nginx :80/:443] (Optional)
    ↓
[Frontend :8003] ← Next.js Frontend
    ↓
[Backend :8007] ← Django Backend (Main Service)
    ↓
├─ [PostgreSQL :5432] ← User data, sessions, feedback
├─ [Redis :6379] ← Cache, rate limiting, keyword retrieval
├─ [ChromaDB :8010] ← Vector database
├─ [LLM :18085] ← Large Language Model (sglang)
└─ [TEI :8080] ← Text Embedding Service
```

---

## 🐳 Docker Container List

### ChatDKU Core Services

| Container Name | Image | Port Mapping | Status | Description |
|----------------|-------|--------------|--------|-------------|
| `chatdku-frontend-1` | chatdku-frontend | 8003:8003 | ✅ Running | Next.js frontend application |
| `chatdku-backend-1` | chatdku-backend | 8007:8007 | ✅ Running | Django backend (Flask removed) |
| `chatdku-django-1` | chatdku-django | 8001:8020 | ⚠️ Legacy | **To be removed**: Old Django service |
| `chatdku-postgres-1` | postgres:16 | 5432:5432 | ✅ Running | PostgreSQL database |
| `chatdku-redis-1` | redis-stack-server | 6379:6379 | ✅ Running | Redis cache and vector storage |
| `chatdku-chromadb-1` | chromadb/chroma | Internal 8000 | ✅ Running | ChromaDB vector database |

### External Dependency Services

| Container Name | Image | Port Mapping | Description |
|----------------|-------|--------------|-------------|
| `bge-m3` | text-embeddings-inference | 8080:80 | Text embedding model service (TEI) |
| `mihomo` | metacubex/mihomo | 7890-7891, 9090 | Proxy service (optional) |
| `subconverter` | tindy2013/subconverter | 25500 | Subscription converter (optional) |

---

## 🔌 Port Details

### Frontend Services

#### **8003 - Next.js Frontend**
- **Service**: ChatDKU Web Interface
- **Container**: `chatdku-frontend-1`
- **Access**: `http://<server-ip>:8003`
- **Purpose**:
  - User interaction interface
  - Chat conversations
  - File uploads
  - Session management

#### **3000 - Development Server** (Non-Docker)
- **Service**: Next.js development mode
- **Purpose**: Used for local development with hot reload

---

### Backend Services

#### **8007 - Django Backend (Main Service)**
- **Service**: ChatDKU main backend API
- **Container**: `chatdku-backend-1`
- **Access**: `http://<server-ip>:8007`
- **Purpose**:
  - RESTful API endpoints
  - Chat streaming responses (`/api/chat`)
  - User authentication and session management
  - File upload processing (`/user/upload`)
  - Feedback collection (`/api/feedback`)
  - Rate limiting and security middleware
  - OpenAPI documentation (`/doc/schema/view/`)
  - Django Admin (`/admin/`)
  - Prometheus monitoring (`/metrics`)

#### **8001 - Legacy Django Service** ⚠️
- **Service**: Old Django instance
- **Container**: `chatdku-django-1`
- **Status**: **Should be stopped and removed**
- **Note**: This is the legacy service before migration, now replaced by port 8007

---

### Database Services

#### **5432 - PostgreSQL**
- **Service**: Relational database
- **Container**: `chatdku-postgres-1`
- **Purpose**:
  - Store user information (UserModel)
  - Store chat sessions (UserSession)
  - Store chat messages (ChatMessages)
  - Store uploaded file metadata (UploadedFile)
  - Store user feedback (Feedback)
  - Course syllabus data (Syllabi Tool)

#### **6379 - Redis**
- **Service**: In-memory database
- **Container**: `chatdku-redis-1`
- **Purpose**:
  - Session cache
  - Rate limiting counters
  - Celery task queue
  - Keyword retrieval index (BM25)
  - Vector storage (Redis Vector)

#### **8010 - ChromaDB** (Internal Port)
- **Service**: Vector database
- **Container**: `chatdku-chromadb-1`
- **Access**: Container internal only
- **Purpose**:
  - Store document vector embeddings
  - Semantic similarity retrieval
  - Core component of RAG system

---

### AI Model Services

#### **18085 - LLM Service (sglang)**
- **Service**: Large Language Model inference service
- **Process**: Python (non-Docker)
- **Model**: Qwen/Qwen3.5-4B
- **Purpose**:
  - Generate chat responses
  - Query rewriting
  - Context judging
  - Conversation summarization
- **API**: OpenAI-compatible interface (`/v1/chat/completions`)

#### **8080 - TEI Embedding Service**
- **Service**: Text Embeddings Inference
- **Container**: `bge-m3`
- **Model**: BAAI/bge-m3
- **Purpose**:
  - Convert text to vector embeddings
  - Support semantic retrieval
  - Multi-language support
- **Endpoint**: `http://localhost:8080/BAAI/bge-m3/embed`

---

### System Services

#### **22 - SSH**
- **Service**: Remote login
- **Purpose**: Server management

#### **80/443 - Nginx/Caddy**
- **Service**: Reverse proxy and HTTPS
- **Purpose**:
  - Unified entry point
  - SSL/TLS termination
  - Load balancing
  - Static file serving

---

## 🔄 Service Dependencies

### Frontend (8003) depends on:
- Backend (8007) - API calls
- Optional: Socket.IO (18420) - Speech-to-text

### Backend (8007) depends on:
- PostgreSQL (5432) - Data persistence
- Redis (6379) - Cache and task queue
- ChromaDB (8010) - Vector retrieval
- LLM (18085) - Generate responses
- TEI (8080) - Text embeddings

### Agent Core depends on:
- Redis (6379) - Keyword retrieval
- ChromaDB (8010) - Vector retrieval
- LLM (18085) - Inference generation
- TEI (8080) - Embedding computation

---

## 📝 Port Usage Recommendations

### Required Open Ports (External Access):
- **8003** - Frontend access
- **8007** - Backend API (if frontend on different machine)

### Optional Open Ports:
- **80/443** - If using Nginx unified entry
- **8001** - Django Admin (recommend internal network only)

### Protected Ports (Internal Access Only):
- **5432** - PostgreSQL (database security)
- **6379** - Redis (cache security)
- **8010** - ChromaDB (data security)
- **18085** - LLM service (resource protection)
- **8080** - TEI service (resource protection)

---

## ⚠️ Identified Issues

### 1. Duplicate Django Services
**Problem**: Two Django containers running simultaneously:
- `chatdku-backend-1` (port 8007) - New service ✅
- `chatdku-django-1` (port 8001) - Old service ❌

**Recommendation**: Stop and remove old service
```bash
docker stop chatdku-django-1
docker rm chatdku-django-1
```

### 2. ChromaDB Port Not Exposed
**Current**: ChromaDB only accessible within containers
**Impact**: Cannot access ChromaDB from outside
**Recommendation**: If external access needed, add port mapping in `docker-compose.yml`:
```yaml
chromadb:
  ports:
    - "8010:8010"
```

---

## 🚀 Quick Start Commands

### Start Core Services (Recommended)
```bash
docker compose up -d
```

### Start Full Services (with Celery)
```bash
docker compose --profile django up -d
```

### Check Service Status
```bash
docker compose ps
```

### View Service Logs
```bash
docker compose logs -f backend
```

---

## 📊 Resource Usage Estimates

| Service | CPU | Memory | Disk |
|---------|-----|--------|------|
| Frontend | Low | ~200MB | ~500MB |
| Backend | Medium | ~500MB | ~1GB |
| PostgreSQL | Low | ~100MB | ~1GB |
| Redis | Low | ~50MB | ~500MB |
| ChromaDB | Medium | ~500MB | ~2GB |
| LLM (Qwen3.5-4B) | High | ~8GB | ~8GB |
| TEI (bge-m3) | Medium | ~2GB | ~2GB |
| **Total** | - | **~11GB** | **~15GB** |

---

## 🔧 Troubleshooting

### Frontend Cannot Access Backend
1. Check `NEXT_PUBLIC_API_BASE_URL` environment variable
2. Confirm backend container is running: `docker ps | grep backend`
3. Test backend connection: `curl http://localhost:8007/api/get_session`

### Backend Cannot Connect to Database
1. Check PostgreSQL container status
2. Verify database credentials (`.env`: `NAME_DB`, `USERNAME_DB`, `PASSWORD_DB`)
3. Test connection: `docker compose exec backend python manage.py check`

### RAG Retrieval Failed
1. Confirm Redis and ChromaDB are running
2. Check if data has been ingested
3. Verify LLM and TEI services are accessible

---

**Document Version**: 2026-03-11
**System Version**: ChatDKU 2.0 (Django Only)
