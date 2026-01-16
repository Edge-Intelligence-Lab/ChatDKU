<p align="center">
  <img src="docs/images/chatdku-logo.png" alt="ChatDKU Logo" width="200"/>
</p>

<h1 align="center">ChatDKU</h1>

<p align="center">
  <strong>🎓 首个专为校园场景设计的开源 Agentic RAG 系统</strong>
</p>

<p align="center">
  <a href="./README.md">English</a> | <a href="./README_CN.md">中文</a>
</p>

<p align="center">
  <a href="https://github.com/xxx/ChatDKU/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License">
  </a>
  <a href="https://github.com/xxx/ChatDKU/stargazers">
    <img src="https://img.shields.io/github/stars/xxx/ChatDKU" alt="Stars">
  </a>
  <a href="https://github.com/xxx/ChatDKU/issues">
    <img src="https://img.shields.io/github/issues/xxx/ChatDKU" alt="Issues">
  </a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Next.js-15-black.svg" alt="Next.js">
</p>

<p align="center">
  <a href="#-功能特性">功能特性</a> •
  <a href="#-系统架构">系统架构</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-数据导入">数据导入</a> •
  <a href="#-贡献指南">贡献指南</a>
</p>

---

## ✨ 功能特性

ChatDKU 是一个基于 **DSPy** 的 Agentic RAG 系统，专为大学校园场景设计，提供智能问答服务。

### 🤖 Agentic RAG 核心

不同于传统的 RAG 系统，ChatDKU 采用 **Agentic RAG** 架构，Agent 能够：

- **自主规划**：根据用户问题自动决策检索策略
- **质量评估**：Judge 模块评估检索结果，决定是否需要补充检索
- **多轮检索**：支持迭代检索，直到获得足够的上下文信息
- **工具调用**：支持扩展工具，如 SQL 查询、API 调用等

```
用户问题 → Query Rewrite → 检索 → Judge评估 → 需要更多信息? 
                              ↑                    ↓ Yes
                              └────────────────────┘
                                       ↓ No
                              Synthesizer → 回答
```

### 🔍 混合检索系统

ChatDKU 采用 **向量检索 + 关键词检索** 的混合检索架构：

| 检索方式 | 技术栈 | 特点 |
|---------|--------|------|
| **向量检索** | ChromaDB + HuggingFace Embeddings | 语义相似度匹配，理解同义词和上下文 |
| **关键词检索** | Redis + BM25 | 精确匹配，处理专有名词和缩写 |
| **结果融合** | Re-ranking | 综合排序，提升检索准确率 |

### 🎓 校园特化工具

- **课程大纲查询**：基于 SQL Agent 的课程数据库查询
- **校园文档问答**：支持 PDF、Word、PPT、Excel 等多种格式
- **用户文档上传**：支持用户上传私有文档进行问答
- **语音输入**：集成 Whisper 模型，支持语音转文字

### 📊 可观测性

- **Phoenix 集成**：完整的 LLM 调用链路追踪
- **OpenTelemetry**：标准化监控指标
- **性能分析**：Token 使用量、延迟分析、成本统计

---

## 🏗 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ChatDKU 系统架构                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        Frontend (Next.js)                        │   │
│  │  • 响应式聊天界面      • Markdown 渲染      • 语音输入           │   │
│  │  • 文件上传           • 深色/浅色主题       • 移动端适配          │   │
│  └───────────────────────────────┬─────────────────────────────────┘   │
│                                  │ REST API                             │
│                                  ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     Backend (Django + Flask)                     │   │
│  │  • 用户认证           • 会话管理           • 文件处理            │   │
│  │  • API 路由           • 流式响应           • 语音转写 (Whisper)  │   │
│  └───────────────────────────────┬─────────────────────────────────┘   │
│                                  │                                      │
│                                  ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      DSPy Agent Core                             │   │
│  │                                                                   │   │
│  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │   │
│  │   │Query Rewriter│───▶│   Planner    │───▶│    Judge     │      │   │
│  │   │  查询重写     │    │   任务规划    │    │  质量评估     │      │   │
│  │   └──────────────┘    └──────────────┘    └──────┬───────┘      │   │
│  │                                                   │              │   │
│  │         ┌─────────────────────────────────────────┤              │   │
│  │         │                                         │              │   │
│  │         ▼                                         ▼              │   │
│  │   ┌──────────────┐                         ┌──────────────┐      │   │
│  │   │   Tools      │                         │ Synthesizer  │      │   │
│  │   │ • RAG检索    │                         │   答案生成    │      │   │
│  │   │ • SQL查询    │                         └──────────────┘      │   │
│  │   │ • API调用    │                                               │   │
│  │   └──────────────┘                                               │   │
│  │                                                                   │   │
│  └───────────────────────────────┬─────────────────────────────────┘   │
│                                  │                                      │
│          ┌───────────────────────┼───────────────────────┐             │
│          ▼                       ▼                       ▼             │
│    ┌──────────┐           ┌──────────┐           ┌──────────┐         │
│    │ ChromaDB │           │  Redis   │           │ Postgres │         │
│    │ 向量存储  │           │ BM25索引  │           │ 课程数据  │         │
│    └──────────┘           └──────────┘           └──────────┘         │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Observability (Phoenix)                       │   │
│  │           LLM 调用追踪 • Token 统计 • 延迟分析                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Agent 工作流程

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Agent 处理流程                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. 用户输入                                                              │
│     │                                                                    │
│     ▼                                                                    │
│  2. 加载历史对话 (Conversation Memory)                                    │
│     │                                                                    │
│     ▼                                                                    │
│  3. 查询重写 (Query Rewriter)                                            │
│     • 修正拼写错误                                                        │
│     • 结合对话历史补充上下文                                               │
│     • 生成检索优化的查询                                                   │
│     │                                                                    │
│     ▼                                                                    │
│  4. 并行检索                                                              │
│     ├─── KeywordRetriever (Redis BM25) ───┐                             │
│     │                                      ├──▶ 结果融合 + Re-rank       │
│     └─── VectorRetriever (ChromaDB) ──────┘                             │
│     │                                                                    │
│     ▼                                                                    │
│  5. 质量评估 (Judge)                                                      │
│     │                                                                    │
│     ├─── 上下文充分 ──▶ 进入第6步                                        │
│     │                                                                    │
│     └─── 上下文不足 ──▶ 返回第3步，使用 internal_memory 避免重复检索       │
│                        （最多迭代 max_iterations 次）                     │
│     │                                                                    │
│     ▼                                                                    │
│  6. 答案生成 (Synthesizer)                                               │
│     • 结合检索上下文                                                      │
│     • 参考对话历史                                                        │
│     • 生成结构化回答                                                      │
│     │                                                                    │
│     ▼                                                                    │
│  7. 对话记忆更新                                                          │
│     • 总结本轮对话                                                        │
│     • 存储到 conversation_history                                        │
│     │                                                                    │
│     ▼                                                                    │
│  8. 返回回答给用户                                                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 核心组件说明

| 组件 | 功能 | 技术实现 |
|------|------|----------|
| **Query Rewriter** | 清理拼写错误，添加对话上下文 | DSPy Module |
| **Planner** | 规划工具调用策略（多工具时启用） | DSPy Module |
| **Judge** | 评估检索质量，决定是否继续检索 | DSPy Refine |
| **VectorRetriever** | 语义相似度检索 | ChromaDB + BGE-M3 |
| **KeywordRetriever** | BM25 关键词检索 | Redis RediSearch |
| **Synthesizer** | 基于上下文生成最终回答 | DSPy Module |
| **Syllabi Tool** | SQL Agent 查询课程数据库 | Postgres + DSPy |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+ (LTS)
- Redis 7+
- Docker & Docker Compose（推荐）

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/xxx/ChatDKU.git
cd ChatDKU

# 2. 复制并编辑配置文件
cp docker/.env.example docker/.env
vim docker/.env  # 设置 LLM API Key 等

# 3. 启动所有服务
docker-compose -f docker/docker-compose.yml up -d

# 4. 查看服务状态
docker-compose -f docker/docker-compose.yml ps

# 5. 访问应用
# 前端: http://localhost:3000
# Phoenix: http://localhost:6006
```

### 方式二：本地开发

```bash
# 1. 克隆项目
git clone https://github.com/xxx/ChatDKU.git
cd ChatDKU

# 2. 创建 Python 虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. 安装 Python 依赖
cd chatdku
pip install -e ".[dev]"

# 4. 启动 Redis
redis-server

# 5. 启动后端服务
python chatdku/core/agent.py

# 6. 启动前端（新终端）
cd chatdku/frontend
npm install
npm run dev

# 7. 访问 http://localhost:3000
```

### 配置说明

主要环境变量（在 `.env` 文件中配置）：

```bash
# ===== LLM 配置 =====
LLM_PROVIDER=openai              # openai / vllm / ollama
LLM_MODEL=gpt-4o                 # 模型名称
LLM_URL=https://api.openai.com   # API 地址
LLM_API_KEY=sk-xxx               # API Key

# ===== Embedding 配置 =====
EMBEDDING_MODEL=BAAI/bge-m3      # Embedding 模型
TEI_URL=http://localhost:8080    # TEI 服务地址（可选）

# ===== 数据库配置 =====
REDIS_HOST=localhost
REDIS_PORT=6379
CHROMA_HOST=localhost
CHROMA_PORT=8001

# ===== 可观测性 =====
PHOENIX_PORT=6006
```

---

## 📥 数据导入

ChatDKU 的数据导入流程分为三个阶段：数据采集 → 数据处理 → 向量索引。

### 数据流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         数据导入流程                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │ 数据采集     │     │  数据处理   │     │  向量索引   │               │
│  │ (Scraper)   │────▶│(Ingestion) │────▶│  (Loading) │               │
│  └─────────────┘     └─────────────┘     └─────────────┘               │
│                                                                         │
│   • 网站爬虫          • 文件解析           • ChromaDB                   │
│   • 文档收集          • 文本分块           • Redis BM25                 │
│   • PDF/HTML/...      • 节点生成           • 课程数据库                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. 数据采集（Scraper）

使用异步爬虫采集校园网站内容：

```bash
cd scraper

# 安装依赖
pip install -e .

# 运行爬虫（默认爬取 dukekunshan.edu.cn）
python scraper.py

# 查看爬取报告
python report.py -s progress.pkl
```

输出目录结构：
```
./dku_website/
├── domain/
│   └── path/
│       ├── index.html
│       └── ...
└── progress.pkl  # 爬取进度记录
```

### 2. 数据处理（Ingestion）

将原始文件转换为可检索的文本节点：

```bash
cd chatdku/chatdku/ingestion

# 增量更新数据（自动检测新增/删除的文件）
python update_data.py \
    --data_dir /path/to/data \
    --user_id Chat_DKU \
    -v True
```

**支持的文件格式**：PDF、HTML、CSV、XLSX、DOCX、TXT、Markdown

**输出文件**：
- `nodes.json` - 所有解析后的文本节点
- `log.json` - 当前已处理文件的记录

### 3. 向量索引（Loading）

将处理后的节点加载到向量数据库：

**加载到 ChromaDB**：
```bash
# 生产环境（会重置现有数据）
python load_chroma.py

# 测试环境（推荐）
python load_chroma.py \
    --nodes_path /path/to/test/nodes.json \
    --collection_name test_collection
```

**加载到 Redis**：
```bash
# 生产环境
python -m chatdku.chatdku.ingestion.load_redis

# 测试环境（推荐）
python -m chatdku.chatdku.ingestion.load_redis \
    --nodes_path /path/to/nodes.json \
    --index_name test_index \
    --reset False
```

### 4. 课程数据导入

课程大纲数据存储在 PostgreSQL 中：

```bash
# 1. 创建数据库表
psql -U chatdku_user -d chatdku_db -f create_table.sql

# 2. 从 PDF/DOCX 导入课程大纲
python local_ingest.py --input_dir /path/to/syllabi
```

---

## 🌐 前后端说明

### 前端（Frontend）

**技术栈**：Next.js 15 + TailwindCSS + shadcn/ui

```bash
cd chatdku/frontend

# 开发模式
npm install
npm run dev          # http://localhost:3000

# 生产构建
npm run build        # 输出到 out/ 目录

# 部署
sudo rsync -av --delete out/ /var/www/chatdku/
```

**主要功能**：
- 响应式聊天界面，支持桌面和移动端
- Markdown 渲染，支持代码高亮
- 语音输入（调用 Whisper 服务）
- 文件上传（支持用户私有文档）
- 深色/浅色主题切换

### 后端（Backend）

**技术栈**：Django REST Framework + Flask

**Django 服务**（主 API）：
```bash
cd chatdku/django

# 启动开发服务器
python manage.py runserver 0.0.0.0:8000

# API 文档
# http://localhost:8000/api/docs/  (drf-spectacular)
```

**Flask 服务**（Agent + STT）：
```bash
cd chatdku/backend

# 启动 Agent 服务
python agent_app_parellel.py

# 启动语音转写服务
python stt_app.py
```

**API 端点示例**：

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/chat/` | POST | 发送聊天消息 |
| `/api/chat/stream/` | POST | 流式聊天响应 |
| `/api/upload/` | POST | 上传用户文档 |
| `/api/stt/` | POST | 语音转文字 |
| `/api/sessions/` | GET | 获取会话列表 |

---

## 📁 项目结构

```
ChatDKU/
├── chatdku/                      # 核心 Python 包
│   ├── chatdku/
│   │   ├── core/                 # Agent 核心
│   │   │   ├── agent.py          # 主 Agent 入口
│   │   │   ├── dspy_classes/     # DSPy 组件
│   │   │   │   ├── query_rewriter.py
│   │   │   │   ├── judge.py
│   │   │   │   ├── synthesizer.py
│   │   │   │   └── ...
│   │   │   └── tools/            # Agent 工具
│   │   │       ├── rag_tool.py
│   │   │       └── syllabi_tool/
│   │   ├── ingestion/            # 数据导入
│   │   │   ├── update_data.py    # 增量更新
│   │   │   ├── load_chroma.py    # ChromaDB 加载
│   │   │   └── load_redis.py     # Redis 加载
│   │   ├── backend/              # Flask 后端
│   │   │   ├── agent_app_parellel.py
│   │   │   └── stt_app.py
│   │   ├── django/               # Django API
│   │   │   └── chatdku_django/
│   │   └── frontend/             # Next.js 前端
│   │       ├── app/
│   │       ├── components/
│   │       └── public/
│   └── pyproject.toml
├── scraper/                      # 网站爬虫
├── utils/                        # 工具脚本
├── benchmarks/                   # 性能基准测试
├── docker/                       # Docker 配置
│   ├── docker-compose.yml
│   └── .env.example
├── docs/                         # 文档
├── LICENSE
├── README.md
└── CONTRIBUTING.md
```

---

## 🧪 开发指南

### 环境搭建

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit hooks
pre-commit install

# 运行代码检查
ruff check .
ruff format .

# 类型检查
mypy chatdku/

# 运行测试
pytest tests/ -v
```

### 添加新工具

参考 [Issue #122](https://github.com/xxx/ChatDKU/issues/122) 了解如何为 Agent 添加新工具。

基本步骤：
1. 在 `chatdku/core/tools/` 创建工具模块
2. 实现工具函数，返回检索结果
3. 在 `agent.py` 中注册工具
4. 更新 Planner 的工具描述

---

## 📊 性能基准

| 指标 | 数值 | 测试条件 |
|------|------|----------|
| 首 Token 延迟 | ~1.5s | vLLM 后端，A100 GPU |
| 检索准确率 | 85%+ | DKU 问答数据集 |
| 上下文相关性 | 0.82 | RAGAS 评估 |
| 端到端延迟 | ~3s | 平均查询 |

详见 [benchmarks/](benchmarks/) 目录。

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

### 贡献方式

- 🐛 **报告 Bug**：提交 Issue 描述问题
- 💡 **功能建议**：提交 Feature Request
- 📝 **改进文档**：帮助完善文档
- 🔧 **提交代码**：提交 Pull Request

### Commit 规范

```
feat: 新功能
fix: Bug 修复
docs: 文档更新
refactor: 代码重构
test: 测试相关
chore: 构建/工具相关
```

---

## 📜 开源协议

本项目采用 [Apache License 2.0](LICENSE) 开源协议。

---

## 🙏 致谢

- [DSPy](https://github.com/stanfordnlp/dspy) - Agent 框架
- [LlamaIndex](https://github.com/run-llama/llama_index) - RAG 工具
- [ChromaDB](https://github.com/chroma-core/chroma) - 向量数据库
- [Phoenix](https://github.com/Arize-ai/phoenix) - LLM 可观测性
- [shadcn/ui](https://ui.shadcn.com/) - UI 组件库

---

## 📬 联系方式

- **GitHub Issues**: [提交问题](https://github.com/xxx/ChatDKU/issues)
- **Email**: contact@chatdku.edu
- **Discord**: [ChatDKU Community](https://discord.gg/xxx)

---

<p align="center">
  Made with ❤️ at Duke Kunshan University
</p>
