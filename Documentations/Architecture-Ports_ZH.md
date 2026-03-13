# ChatDKU 系统架构与端口说明

本文档说明 ChatDKU 系统中所有服务、端口及其作用。

---

## 📊 系统架构概览

```
用户浏览器
    ↓
[Nginx :80/:443] (可选)
    ↓
[Frontend :8003] ← Next.js 前端
    ↓
[Backend :8007] ← Django 后端 (主服务)
    ↓
├─ [PostgreSQL :5432] ← 用户数据、会话、反馈
├─ [Redis :6379] ← 缓存、速率限制、关键词检索
├─ [ChromaDB :8010] ← 向量数据库
├─ [LLM :18085] ← 大语言模型 (sglang)
└─ [TEI :8080] ← 文本嵌入服务
```

---

## 🐳 Docker 容器列表

### ChatDKU 核心服务

| 容器名 | 镜像 | 端口映射 | 状态 | 说明 |
|--------|------|----------|------|------|
| `chatdku-frontend-1` | chatdku-frontend | 8003:8003 | ✅ 运行中 | Next.js 前端应用 |
| `chatdku-backend-1` | chatdku-backend | 8007:8007 | ✅ 运行中 | Django 后端 (Flask 已移除) |
| `chatdku-django-1` | chatdku-django | 8001:8020 | ⚠️ 旧服务 | **待移除**：旧的 Django 服务 |
| `chatdku-postgres-1` | postgres:16 | 5432:5432 | ✅ 运行中 | PostgreSQL 数据库 |
| `chatdku-redis-1` | redis-stack-server | 6379:6379 | ✅ 运行中 | Redis 缓存和向量存储 |
| `chatdku-chromadb-1` | chromadb/chroma | 内部 8000 | ✅ 运行中 | ChromaDB 向量数据库 |

### 外部依赖服务

| 容器名 | 镜像 | 端口映射 | 说明 |
|--------|------|----------|------|
| `bge-m3` | text-embeddings-inference | 8080:80 | 文本嵌入模型服务 (TEI) |
| `mihomo` | metacubex/mihomo | 7890-7891, 9090 | 代理服务 (可选) |
| `subconverter` | tindy2013/subconverter | 25500 | 订阅转换服务 (可选) |

---

## 🔌 端口详细说明

### 前端服务

#### **8003 - Next.js 前端**
- **服务**: ChatDKU Web 界面
- **容器**: `chatdku-frontend-1`
- **访问**: `http://<server-ip>:8003`
- **作用**:
  - 用户交互界面
  - 聊天对话
  - 文件上传
  - 会话管理

#### **3000 - 开发服务器** (非 Docker)
- **服务**: Next.js 开发模式
- **作用**: 本地开发时使用，支持热重载

---

### 后端服务

#### **8007 - Django 后端 (主服务)**
- **服务**: ChatDKU 主后端 API
- **容器**: `chatdku-backend-1`
- **访问**: `http://<server-ip>:8007`
- **作用**:
  - RESTful API 端点
  - 聊天流式响应 (`/api/chat`)
  - 用户认证和会话管理
  - 文件上传处理 (`/user/upload`)
  - 反馈收集 (`/api/feedback`)
  - 速率限制和安全中间件
  - OpenAPI 文档 (`/doc/schema/view/`)
  - Django Admin (`/admin/`)
  - Prometheus 监控 (`/metrics`)

#### **8001 - 旧 Django 服务** ⚠️
- **服务**: 旧的 Django 实例
- **容器**: `chatdku-django-1`
- **状态**: **应该停止并移除**
- **说明**: 这是迁移前的旧服务，现在已被 8007 端口的服务替代

---

### 数据库服务

#### **5432 - PostgreSQL**
- **服务**: 关系型数据库
- **容器**: `chatdku-postgres-1`
- **作用**:
  - 存储用户信息 (UserModel)
  - 存储聊天会话 (UserSession)
  - 存储聊天消息 (ChatMessages)
  - 存储上传文件元数据 (UploadedFile)
  - 存储用户反馈 (Feedback)
  - 课程大纲数据 (Syllabi Tool)

#### **6379 - Redis**
- **服务**: 内存数据库
- **容器**: `chatdku-redis-1`
- **作用**:
  - 会话缓存
  - 速率限制计数器
  - Celery 任务队列
  - 关键词检索索引 (BM25)
  - 向量存储 (Redis Vector)

#### **8010 - ChromaDB** (内部端口)
- **服务**: 向量数据库
- **容器**: `chatdku-chromadb-1`
- **访问**: 仅容器内部访问
- **作用**:
  - 存储文档向量嵌入
  - 语义相似度检索
  - RAG 系统的核心组件

---

### AI 模型服务

#### **18085 - LLM 服务 (sglang)**
- **服务**: 大语言模型推理服务
- **进程**: Python (非 Docker)
- **模型**: Qwen/Qwen3.5-4B
- **作用**:
  - 生成聊天回复
  - 查询重写
  - 上下文判断
  - 对话摘要
- **API**: OpenAI 兼容接口 (`/v1/chat/completions`)

#### **8080 - TEI 嵌入服务**
- **服务**: Text Embeddings Inference
- **容器**: `bge-m3`
- **模型**: BAAI/bge-m3
- **作用**:
  - 将文本转换为向量嵌入
  - 支持语义检索
  - 多语言支持
- **端点**: `http://localhost:8080/BAAI/bge-m3/embed`

---

### 系统服务

#### **22 - SSH**
- **服务**: 远程登录
- **作用**: 服务器管理

#### **80/443 - Nginx/Caddy**
- **服务**: 反向代理和 HTTPS
- **作用**:
  - 统一入口
  - SSL/TLS 终止
  - 负载均衡
  - 静态文件服务

---

## 🔄 服务依赖关系

### Frontend (8003) 依赖：
- Backend (8007) - API 调用
- 可选：Socket.IO (18420) - 语音转文字

### Backend (8007) 依赖：
- PostgreSQL (5432) - 数据持久化
- Redis (6379) - 缓存和任务队列
- ChromaDB (8010) - 向量检索
- LLM (18085) - 生成回复
- TEI (8080) - 文本嵌入

### Agent 核心依赖：
- Redis (6379) - 关键词检索
- ChromaDB (8010) - 向量检索
- LLM (18085) - 推理生成
- TEI (8080) - 嵌入计算

---

## 📝 端口使用建议

### 必需开放的端口（外部访问）：
- **8003** - 前端访问
- **8007** - 后端 API（如果前端在不同机器）

### 可选开放的端口：
- **80/443** - 如果使用 Nginx 统一入口
- **8001** - Django Admin（建议仅内网访问）

### 应该保护的端口（仅内部访问）：
- **5432** - PostgreSQL（数据库安全）
- **6379** - Redis（缓存安全）
- **8010** - ChromaDB（数据安全）
- **18085** - LLM 服务（资源保护）
- **8080** - TEI 服务（资源保护）

---

## ⚠️ 发现的问题

### 1. 重复的 Django 服务
**问题**: 同时运行两个 Django 容器：
- `chatdku-backend-1` (端口 8007) - 新服务 ✅
- `chatdku-django-1` (端口 8001) - 旧服务 ❌

**建议**: 停止并移除旧服务
```bash
docker stop chatdku-django-1
docker rm chatdku-django-1
```

### 2. ChromaDB 端口未暴露
**当前**: ChromaDB 仅容器内部访问
**影响**: 无法从外部直接访问 ChromaDB
**建议**: 如需外部访问，在 `docker-compose.yml` 中添加端口映射：
```yaml
chromadb:
  ports:
    - "8010:8010"
```

---

## 🚀 快速启动命令

### 启动核心服务（推荐）
```bash
docker compose up -d
```

### 启动完整服务（含 Celery）
```bash
docker compose --profile django up -d
```

### 查看服务状态
```bash
docker compose ps
```

### 查看服务日志
```bash
docker compose logs -f backend
```

---

## 📊 资源使用估算

| 服务 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| Frontend | 低 | ~200MB | ~500MB |
| Backend | 中 | ~500MB | ~1GB |
| PostgreSQL | 低 | ~100MB | ~1GB |
| Redis | 低 | ~50MB | ~500MB |
| ChromaDB | 中 | ~500MB | ~2GB |
| LLM (Qwen3.5-4B) | 高 | ~8GB | ~8GB |
| TEI (bge-m3) | 中 | ~2GB | ~2GB |
| **总计** | - | **~11GB** | **~15GB** |

---

## 🔧 故障排查

### 前端无法访问后端
1. 检查 `NEXT_PUBLIC_API_BASE_URL` 环境变量
2. 确认后端容器运行：`docker ps | grep backend`
3. 测试后端连接：`curl http://localhost:8007/api/get_session`

### 后端无法连接数据库
1. 检查 PostgreSQL 容器状态
2. 验证数据库凭据（`.env` 中的 `NAME_DB`, `USERNAME_DB`, `PASSWORD_DB`）
3. 测试连接：`docker compose exec backend python manage.py check`

### RAG 检索失败
1. 确认 Redis 和 ChromaDB 运行
2. 检查数据是否已摄取
3. 验证 LLM 和 TEI 服务可访问

---

**文档版本**: 2026-03-11
**系统版本**: ChatDKU 2.0 (Django Only)
