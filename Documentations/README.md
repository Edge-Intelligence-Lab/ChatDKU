# ChatDKU 部署文档

欢迎使用 ChatDKU！请根据您的需求选择合适的部署版本。

---

## 📦 版本选择

### Agent-Only 版本（推荐用于测试）

**适用场景**：
- 快速测试 ChatDKU 的核心 Agent 功能
- 本地开发和调试
- API 集成和自定义应用
- 学习和研究 RAG 系统

**特点**：
- ⚡ 部署时间：5-10 分钟
- 💻 资源需求：2C4G（不含 LLM/Embedding 服务）
- 🎯 核心功能：Agent 对话、RAG 检索、CLI 交互
- 🔧 部署方式：Docker Compose 或本地 Python

**文档**：
- [快速开始指南](./Agent-Only-Quick-Start_ZH.md) - 5 分钟快速部署
- [完整部署指南](./Agent-Only-Deployment_ZH.md) - 详细配置说明

---

### Full 版本（生产环境）

**适用场景**：
- 生产环境部署
- 多用户 Web 应用
- 需要用户管理和权限控制
- 需要文件上传和反馈系统

**特点**：
- ⏱️ 部署时间：30-60 分钟
- 🖥️ 资源需求：8C16G+
- 🌐 完整功能：Web 界面、用户管理、文件上传、反馈系统、异步任务
- 🏗️ 技术栈：Next.js + Django + PostgreSQL + Redis + ChromaDB

**文档**：
- [完整部署指南](./Full-Deployment-Guide_ZH.md) - 生产环境部署

---

## 🚀 快速决策

**如果您想要**：
- ✅ 快速测试 Agent 功能 → 选择 **Agent-Only**
- ✅ 本地开发和调试 → 选择 **Agent-Only**
- ✅ 集成到自己的应用 → 选择 **Agent-Only**
- ✅ 部署生产 Web 应用 → 选择 **Full**
- ✅ 需要用户管理系统 → 选择 **Full**

---

## 📚 其他文档

- [架构和端口说明](./Architecture-Ports_ZH.md)
- [数据导入指南](../data/README.md)

---

## 💡 提示

从 Agent-Only 版本开始是个好主意！您可以：
1. 快速验证 ChatDKU 是否满足需求
2. 测试 Agent 的检索和回答质量
3. 熟悉系统配置和数据准备流程
4. 需要时再升级到 Full 版本
