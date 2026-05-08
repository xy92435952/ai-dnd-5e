# AI 跑团平台 — DnD 5e

基于 DnD 5e 规则的 AI 跑团平台。玩家上传模组、创建角色，AI 担任地下城主和队友；支持单人冒险、多人房间、网格战斗、自然语言战斗行动和本地规则结算。

> 当前文档快照：2026-05-07
> 当前重点：DM Agent 四层化（输入 / 规则 / 叙事 / 记忆）、Adventure / Combat 前后端拆分、自然语言战斗体验修复。

## 当前能力

- **规则在后端本地结算**：骰子、技能检定、攻击、伤害、移动、法术、回合资源由 Python 规则层执行，AI 不直接决定数学结果。
- **AI DM 编排**：LangGraph 驱动模组解析、队友生成、DM 代理；DM Agent 已按输入、规则、叙事、记忆拆层。
- **输入安全层**：区分 `human_input`、`ai_generated_choice`、`system_action`、`ai_takeover`，拦截明显越界、注入、作弊和与游戏无关内容；AI 生成选项由后端校验来源后放行。
- **自然语言战斗**：玩家可以输入“我靠近最近的骷髅并用长剑攻击”。解析器会先用本地规则处理常见意图，再回退 LLM；近战目标不可达时只移动，不伪造攻击。
- **多人联机**：房间、成员、发言权、WebSocket 广播、战斗回合归属校验。
- **前端拆分**：Adventure / Combat 已拆成页面、hooks、adventure components、combat components、utils 和测试。

## 快速启动

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 OpenAI 兼容 LLM 配置
```

`.env` 最小示例：

```env
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash

DATABASE_URL=sqlite+aiosqlite:///./ai_trpg.db
CHROMADB_PATH=./chromadb_data
LANGGRAPH_DB_PATH=./langgraph_memory.db
JWT_SECRET=dev-secret-change-me-at-least-32-bytes
ENV=development
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

启动本地后端：

```bash
cd backend
source .venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8002
```

本地开发使用 8002 是因为 [frontend/vite.config.js](/Users/qft/Desktop/ai-dnd-5e/frontend/vite.config.js) 的 `/api` 代理指向 `http://localhost:8002`。

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问：

- 前端开发页：`http://127.0.0.1:3000`
- 后端健康检查：`http://127.0.0.1:8002/health`
- API 文档：`http://127.0.0.1:8002/docs`

## 部署简版

如果服务器沿用当前 nginx 读取静态 `dist/` 的方式：

```bash
cd /opt/ai-trpg/app
git pull

cd backend
pip install -r requirements.txt

cd ../frontend
npm install
npm run build
```

纯前端改动构建完成后 nginx 通常不需要重启。后端代码同步部署后，需要按服务器当前方式重启后端服务。

更完整的生产部署清单见 [doc/DEPLOY.md](/Users/qft/Desktop/ai-dnd-5e/doc/DEPLOY.md)。

## 项目结构

```text
ai-dnd-5e/
├── backend/
│   ├── main.py                         FastAPI 入口
│   ├── api/
│   │   ├── game.py                     /game 会话、探索、自然语言战斗入口
│   │   ├── combat/                     战斗端点包，按攻击/法术/AI回合/状态拆分
│   │   ├── rooms.py                    多人房间
│   │   ├── modules.py                  模组上传与解析
│   │   ├── characters.py               角色创建、队友生成、准备法术
│   │   └── auth.py / ws.py / deps.py
│   ├── services/
│   │   ├── graphs/dm_agent.py          DM Agent 公开入口和 LangGraph 连线
│   │   ├── graphs/dm_agent_nodes.py    input/rules/memory/combat/explore/parse 节点
│   │   ├── graphs/dm_agent_state.py    LangGraph state 类型和消息窗口
│   │   ├── graphs/dm_agent_prompts.py  探索/战斗/战役状态提示词
│   │   ├── graphs/dm_agent_utils.py    输入元数据、规则/记忆上下文、输出归一化
│   │   ├── graphs/dm_agent_runtime.py  骰池、初始状态、最终响应包装
│   │   ├── graphs/dm_agent_messages.py LLM 用户消息组装
│   │   ├── graphs/dm_agent_memory.py   LangGraph checkpoint 初始化
│   │   ├── graphs/dm_campaign_state.py 战役状态摘要生成
│   │   ├── input_guard.py              输入来源和拦截入口
│   │   ├── input_guard_policy.py       本地高置信度拦截/放行规则
│   │   ├── input_guard_types.py        输入守卫类型定义
│   │   ├── action_parser.py            自然语言战斗行动解析
│   │   ├── combat_service.py           攻击、伤害、条件等规则计算
│   │   ├── dnd_rules.py                5e 规则纯函数
│   │   ├── context_builder.py          DM 输入上下文
│   │   ├── state_applicator.py         DM 输出写回数据库
│   │   └── local_rag_service.py        ChromaDB 检索
│   ├── models/                         SQLAlchemy ORM
│   ├── schemas/                        HTTP / WS / 游戏响应 schema
│   └── tests/                          pytest: unit / integration / smoke
├── frontend/
│   └── src/
│       ├── pages/                      Home / Login / CharacterCreate / Adventure / Combat
│       ├── components/adventure/       Adventure 页面组件
│       ├── components/combat/          Combat 页面组件
│       ├── hooks/                      Adventure / Combat / WebSocket / User hooks
│       │   ├── useAdventureRoom.js     Adventure 多人房间查询
│       │   ├── useAdventureUiState.js  Adventure 页面 UI 状态和派生数据
│       │   ├── useCombatRuntime.js     Combat 页面流程接线
│       │   └── useCombatPageState.js   Combat 页面状态容器
│       ├── utils/                      combat、skillCheck、dialogue 等纯工具
│       │   ├── adventureSessionLoaded.js  Adventure session 恢复/开场剧场逻辑
│       │   └── combatPage.js              Combat 页面常量和可选副作用工具
│       ├── api/client.js               axios API 客户端
│       └── store/gameStore.js          Zustand 全局状态
├── docs/
│   └── json-field-convention.md        JSON 字段修改约定
├── doc/
│   ├── DEPLOY.md                       部署清单
│   ├── Technical_Architecture.md       当前技术架构
│   ├── DM_Agent_Architecture.html      DM Agent 四层可视化架构
│   └── Update_Roadmap.md               当前路线图和历史阶段
└── README.md
```

## 测试与发布前检查

后端：

```bash
cd backend
python -m pytest tests/ -q
```

常用定向回归：

```bash
cd ..
backend/.venv-codex/bin/pytest \
  backend/tests/unit/test_action_parser.py \
  backend/tests/integration/test_combat_endpoints.py \
  backend/tests/smoke/test_imports.py -q
```

前端：

```bash
cd frontend
npm test
npm run build
```

当前已知情况：

- `npm test` 应通过全部 Vitest 测试。
- `npm run build` 应成功，可能出现 chunk 体积和 CSS `@import` 顺序 warning，不阻塞部署。
- `npm run lint` 仍会扫到 `public/design-preview-*` 和部分历史 React Compiler 风格规则噪声；发布以测试和构建为准。

## 重要约定

- 不要提交 `backend/.env`、`frontend/dist/`、`.venv*`、`backend/.venv*`。
- 修改 SQLAlchemy JSON 字段时遵守 [docs/json-field-convention.md](/Users/qft/Desktop/ai-dnd-5e/docs/json-field-convention.md)。
- 改后端响应 schema 后，同步 OpenAPI 和前端类型：

```bash
cd backend
python scripts/export_openapi.py

cd ../frontend
npm run types:api
```

## 许可

项目仅供个人学习和原型验证使用。D&D 5e SRD 内容请遵守 Wizards of the Coast `Systems Reference Document 5.1 CC-BY-4.0`。
