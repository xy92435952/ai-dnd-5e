# AI 跑团平台 — DnD 5e

基于 DnD 5e 规则的 AI 跑团平台。上传模组，创建角色，AI 担任 DM 和队友；支持单人和多人房间。

- **规则骨架**：5e 引擎（骰子 / 检定 / 战斗 / 法术）全部在后端本地计算，AI 不参与数学
- **AI 叙事**：LangGraph StateGraph 编排 3 个独立 graph（模组解析 / 队友生成 / DM 代理）
- **本地 RAG**：ChromaDB 向量库，模组 chunks 按 `module_id` 隔离
- **多人联机**：WebSocket 广播，剧场模式同步、DM 思考动画跨玩家联动

详细架构见 [`CLAUDE.md`](./CLAUDE.md)；项目约定见 [`docs/`](./docs/)。

---

## 快速启动

### 1. 后端环境

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows（Linux/Mac: source venv/bin/activate）
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 LLM 配置
```

`.env` 示例（OpenAI 兼容 API，如 AiHubMix / OpenRouter / OpenAI）：

```env
# LLM（必填）
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://aihubmix.com/v1
LLM_MODEL=claude-sonnet-4-6

# 本地 RAG / 对话记忆（默认路径即可）
CHROMADB_PATH=./chromadb_data
LANGGRAPH_DB_PATH=./langgraph_memory.db
```

首次运行需要跑一次数据库迁移：

```bash
python migrate_multiclass.py
python migrate_turn_states.py
python migrate_dify_conversation_id.py
python migrate_condition_durations.py
```

### 2. 前端环境

```bash
cd frontend
npm install
```

### 3. 启动

**Windows 一键：**

```
start.bat
```

**手动：**

```bash
# 终端 1 - 后端
cd backend
python -m uvicorn main:app --port 8000
# 注意：Windows 上不要用 --reload（有 WinError 6 僵尸进程 bug）

# 终端 2 - 前端
cd frontend
npm run dev
```

访问 **http://localhost:3000**。API 文档在 **http://localhost:8000/docs**。

---

## 使用流程

1. **上传模组** — PDF / DOCX / Markdown / TXT
2. **等待解析** — LangGraph WF1 自动提取结构化信息 + 生成 RAG chunks（30–60 秒）
3. **创建角色** — 向导式 4–6 步，施法职业自动多一步"法术选择"
4. **生成队伍** — LangGraph WF2 按角色缺口生成 AI 队友
5. **开始冒险** — 输入行动 → WF3 DM 代理推进剧情 → 本地规则引擎解算骰子与战斗

---

## 项目结构

```
ai-dnd-5e/
├── backend/
│   ├── main.py                    FastAPI 入口
│   ├── api/
│   │   ├── game.py                会话 / 行动 / 休息 / checkpoint
│   │   ├── combat/                战斗包（11 个子模块，从单文件 5368 行拆出）
│   │   ├── characters.py          角色 CRUD / 队友生成
│   │   ├── modules.py             模组上传与解析
│   │   ├── rooms.py               多人房间
│   │   ├── auth.py / ws.py / deps.py
│   ├── services/
│   │   ├── graphs/                3 个 LangGraph StateGraph
│   │   ├── dnd_rules.py           5e 规则引擎（纯计算）
│   │   ├── combat_service.py      战斗逻辑
│   │   ├── spell_service.py       法术注册表
│   │   ├── context_builder.py     序列化为 DM 输入
│   │   ├── state_applicator.py    解析 state_delta 并写库
│   │   ├── character_roster.py    session → party 访问器
│   │   ├── local_rag_service.py   ChromaDB 检索
│   │   └── langgraph_client.py    统一 AI 客户端
│   ├── models/                    SQLAlchemy ORM
│   ├── schemas/                   JSON 字段 Pydantic
│   └── tests/                     pytest 套件（smoke / unit / integration）
├── frontend/
│   └── src/
│       ├── pages/                 Home / Login / Room / CharacterCreate / Adventure / Combat
│       ├── components/            通用组件 + adventure/ + combat/ 子目录
│       ├── hooks/                 useWebSocket / useUser
│       ├── store/gameStore.js     Zustand 全局状态
│       ├── utils/                 markdown / combat / dice
│       └── data/                  dnd5e.js / combat.js
├── docs/
│   └── json-field-convention.md   JSON 列修改约定（flag_modified）
├── dify_workflows/                遗留参考（Phase 11 已全迁 LangGraph，不再被代码引用）
├── CLAUDE.md                      详细架构 / ADR / Phase 记录
└── README.md
```

---

## 技术栈

| 层 | 选型 |
|----|------|
| 前端 | React 18 + Vite + Zustand |
| 后端 | FastAPI (async) + SQLAlchemy 2.0 + aiosqlite |
| AI 编排 | LangGraph StateGraph（Phase 11 替换 Dify） |
| LLM | AiHubMix / OpenRouter / OpenAI 任意 OpenAI 兼容 API，通过 `langchain-openai` 接入 |
| 对话记忆 | LangGraph `AsyncSqliteSaver`（`thread_id = session.id`） |
| RAG | ChromaDB 本地持久化 |
| 文件解析 | PyMuPDF (PDF) + python-docx + markdown |
| 多人通信 | FastAPI WebSocket |

---

## 测试

后端 pytest 套件：

```bash
cd backend
pip install -r requirements.txt       # 已含 pytest + pytest-asyncio
python -m pytest tests/ -v
```

- `tests/smoke/`       — 导入 / 路由注册 / 环境健康（不需网络）
- `tests/unit/`        — 纯函数（dnd_rules / combat_service / character_roster）
- `tests/integration/` — HTTP 端点（TestClient，使用独立的内存 SQLite）

前端构建校验：

```bash
cd frontend
npm run build
```

## 前后端类型同步

后端 Pydantic schema 是类型的**单一来源**。前端的 `src/types/api.d.ts` 从 OpenAPI 生成，改了后端字段后按顺序：

```bash
cd backend
python scripts/export_openapi.py          # 产出 backend/openapi.json

cd ../frontend
npm run types:api                          # 从上面那份 openapi.json 生成 src/types/api.d.ts
```

两份产物都入库。CI 会校验 `openapi.json` 与 `api.d.ts` 是否与代码同步，不同步直接红灯。

WebSocket 事件类型**不走 OpenAPI**，在两边各写一份：
- 后端：`backend/schemas/ws_events.py`（Pydantic）
- 前端：`frontend/src/types/ws.d.ts`（TypeScript interface）

改一处必改两处，`tests/unit/test_ws_events.py` 会校验后端侧的完整性。

---

## 开发阶段

见 [`CLAUDE.md`](./CLAUDE.md) §9。当前状态：**Phase 12 完成 — 结构性重构**

- P1 消除 companion 加载 / localStorage.user 等重复模式
- P2 拆 `api/combat.py`（5368 行）为 11 个职能子模块
- P3 从 Combat.jsx / Adventure.jsx 剥离内嵌子组件和工具
- P4 建 pytest 测试体系 + CI

---

## 许可

项目仅供个人学习使用。SRD 数据遵循 Wizards of the Coast `Systems Reference Document 5.1 CC-BY-4.0`。
