# 多用户 AI 智能助理平台

一个基于 [LangGraph](https://www.langchain.com/langgraph) 的多用户智能体平台，把一个原生的 Sidekick 智能体 Demo 改造成可对外服务的多用户系统。每个用户登录后拥有独立的会话空间，智能体可调用真实的浏览器、沙箱文件系统、网页搜索与维基百科等 MCP 工具完成任务，并在敏感操作前暂停等待用户审批。

## 功能特性

- **多用户认证**：邮箱式用户名 + argon2 密码哈希 + JWT 令牌，注册 / 登录 / 查询当前用户
- **数据隔离**：会话（conversation）绑定 `user_id`，跨用户访问返回 403 / 404
- **流式对话**：WebSocket 双向协议，逐步推送待办列表、人工审批、最终报告
- **智能体循环**：worker（`create_agent`）执行任务 → 独立 evaluator 校验是否达标 → 不达标带反馈重试（最多 `MAX_ATTEMPTS` 次）
- **人工审批暂停**：发送推送通知 / 请求人工协助等敏感操作前暂停，等待用户批准后继续
- **中间件**：容错、PII 脱敏（email / 信用卡号）、待办列表、模型调用上限
- **持久化**：LangGraph 检查点与业务数据均落到 SQLite，服务重启后对话状态保留
- **可观测性**：结构化日志（`LOG_LEVEL` 控制级别）；trace / token / 成本由 LangSmith 自动上报（`LANGSMITH_*` 环境变量）

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | FastAPI · Uvicorn · WebSocket |
| 智能体 | LangChain `create_agent` · LangGraph · AsyncSqliteSaver |
| 工具 | MCP（Playwright 浏览器 / 沙箱文件系统）· Wikipedia · Google Serper |
| 数据 | SQLAlchemy（异步）· SQLite + aiosqlite |
| 认证 | PyJWT · pwdlib[argon2] |
| 前端 | React 19 · Vite · TypeScript · Tailwind CSS v4 |
| 模型 | 默认 `glm-4.5-air`（可用任何 OpenAI 兼容接口） |
| 包管理 | uv（Python）· npm（前端） |

## 项目结构

```
多用户ai智能助理平台/
├── app/
│   ├── main.py                 # FastAPI 入口 + lifespan
│   ├── api/
│   │   ├── auth.py             # 注册 / 登录 / 查询当前用户
│   │   ├── routes.py           # 会话 CRUD + 对话流转
│   │   ├── websocket.py        # WebSocket 流式协议
│   │   └── deps.py             # get_current_user 依赖
│   ├── core/
│   │   ├── agent.py            # Sidekick 智能体 + evaluator 循环
│   │   ├── agent_manager.py    # conversation_id → Sidekick 映射
│   │   ├── checkpointer.py     # AsyncSqliteSaver 封装
│   │   ├── security.py         # 密码哈希 + JWT
│   │   ├── logging.py          # 结构化日志配置
│   │   ├── middleware.py       # TolerateToolErrors
│   │   └── config.py           # 路径 / 常量 / 配置
│   ├── models/                 # SQLAlchemy ORM 模型
│   ├── schemas/                # Pydantic 请求 / 响应模型
│   └── tools/                  # MCP 与自建工具
├── frontend/                   # React + Vite SPA（独立前端）
├── tests/                      # pytest 测试套件
├── data/                       # 运行时 SQLite（app.db / checkpoints.sqlite）
├── sandbox/                    # 沙箱文件系统（MCP filesystem 服务器）
├── Dockerfile                  # 后端镜像
├── frontend/Dockerfile         # 前端镜像
├── docker-compose.yml
├── .github/workflows/ci.yml    # CI：后端 pytest + 前端 build
└── pyproject.toml
```

## 环境准备

- Python ≥ 3.10（建议 3.12）
- [uv](https://docs.astral.sh/uv/) 包管理器
- Node.js ≥ 20（运行时 MCP 服务器通过 `npx` 启动，需可用）
- 一个 OpenAI 兼容的模型接口（默认 `glm-4.5-air`）

## 安装与配置

1. 安装 Python 依赖（含开发依赖 pytest）：

   ```bash
   uv sync
   ```

2. 配置环境变量。复制示例文件并填入真实值：

   ```bash
   cp .env.example .env
   ```

   关键变量：

   | 变量 | 说明 |
   | --- | --- |
   | `LLM_MODEL` | 模型名（默认 `glm-4.5-air`） |
   | `LLM_API_KEY` | 模型 API 密钥 |
   | `LLM_BASE_URL` | 模型服务地址 |
   | `JWT_SECRET` | JWT 签名密钥（生产必须改成强随机值） |
   | `LOG_LEVEL` | 日志级别（默认 `INFO`） |
   | `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | LangSmith 可观测性（可选） |

   > ⚠️ `.env` 含真实密钥，已被 `.gitignore` / `.dockerignore` 排除，**切勿提交**。

## 运行

启动后端（默认 `http://localhost:8000`）：

```bash
uv run uvicorn app.main:app --reload
```

启动前端（默认 `http://localhost:5173`，开发期已代理 `/api`、`/ws` 到后端，无跨域问题）：

```bash
cd frontend
npm install
npm run dev
```

首次启动会自动创建 `data/`（app.db、checkpoints.sqlite）与 `sandbox/` 目录。

### 冒烟脚本

不涉及 LLM 与 MCP 的快速验证脚本：

```bash
uv run python smoke_auth.py       # 认证：注册 → 登录 → 受保护端点
uv run python smoke_test.py       # 生命周期 + 会话 CRUD
uv run python smoke_isolation.py  # 跨用户隔离 + WebSocket 拒绝路径
```

## 测试

```bash
uv run pytest -q
```

测试使用独立临时 SQLite，通过依赖注入与假 `AgentManager` 隔离，**不触发真实 LLM / MCP / checkpointer**，可离线快速运行：

- `tests/test_security.py`：密码哈希与 JWT
- `tests/test_agent.py`：evaluator 的 JSON 解析与降级逻辑（模拟 LLM）
- `tests/test_auth.py`：注册 / 登录 / 当前用户
- `tests/test_isolation.py`：跨用户 403 / 404 与数据隔离

## 部署

### Docker Compose

```bash
docker compose up --build
```

- 前端（Nginx）：`http://localhost:8080`，`/api`、`/ws` 反向代理到后端
- 后端：`http://localhost:8000`（`env_file` 从 `.env` 注入，`data/`、`sandbox/` 挂卷持久化）

> 后端镜像因预装 Playwright Chromium 及系统依赖，体积较大（浏览器 MCP 所需）。

### CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) 在 push 到 `main` 或 PR 时执行：

- 后端：`uv sync --frozen` → `uv run pytest`
- 前端：`npm ci` → `npm run build`

## 核心概念

- **Sidekick 智能体**：`create_agent`（Layer 3 agent）外层套自建循环 —— worker 执行任务后用裸 LLM evaluator 校验 `success_criteria`，达标才接受，否则带上 feedback 重试，最多 `MAX_ATTEMPTS` 次，或转成向用户提问。
- **待办列表**：`TodoListMiddleware` 追踪任务分解，通过 WebSocket 的 `todos` 事件实时推给前端。
- **人工审批**：`HumanInTheLoopMiddleware` 在 `send_push_notification` / `request_human_help` 处中断，前端点「批准」后通过 `approve` 消息续接本轮。
- **持久化对齐**：`conversation_id` 与 LangGraph 的 `thread_id` 一一对应，业务库与检查点保持一致。