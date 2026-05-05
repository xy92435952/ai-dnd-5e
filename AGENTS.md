# AGENTS.md — AI 跑团平台项目档案

> 最后更新：2026-05-05
> 当前代码状态：Phase 12 完成后持续演进
> 本次更新：同步多人联机、WS、combat 子模块拆分，以及 DM/队友反应内部解耦
> 项目路径：`C:\Users\Denny\Desktop\dnd\ai-dnd-5e`

---

## 1. 产品定位

这是一个基于 DnD 5e 规则、运行在浏览器中的 AI 跑团平台。

当前代码已经不再只是“本地单人 MVP”，而是同时覆盖：

- 模组上传与解析
- 玩家角色创建与养成
- AI 地下城主叙事
- AI 队友人格化陪跑
- 网格战斗与规则结算
- 登录鉴权
- 多人房间与 WebSocket 同步

一句话概括：

> 本地规则引擎负责数学与状态，LangGraph 负责叙事与生成，前端负责单人/多人体验承接。

---

## 2. 技术栈

### 后端

- FastAPI
- SQLAlchemy 2.0 + async session
- SQLite（本地开发默认）
- Pydantic v2 / pydantic-settings
- LangGraph StateGraph
- langchain-openai
- ChromaDB
- JWT + bcrypt
- Alembic

### 前端

- React 19
- Vite
- React Router DOM 7
- Zustand
- Axios
- 原生 CSS
- Vitest / Testing Library

### AI 层

- `module_parser` graph：模组解析 + RAG chunk 生成
- `party_generator` graph：AI 队友生成
- `dm_agent` graph：主 DM 叙事、规则裁定、战斗/探索分支

#### 当前 DM Agent 特点

`backend/services/graphs/dm_agent.py` 中的探索链路已做内部拆分：

- 主探索节点负责：
  - `narrative`
  - `needs_check`
  - `state_delta`
  - `player_choices`
- 队友反应节点负责：
  - 基于主叙事生成 `companion_reactions`
  - 保留 AI 队友人格
  - 避免队友台词挤占主叙事 prompt 注意力

这个拆分是**内部实现变更**，不改变前后端接口字段。

---

## 3. 当前目录结构

```text
ai-dnd-5e/
├── AGENTS.md
├── README.md
├── PRD.md
├── start.bat
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── requirements.txt
│   ├── openapi.json
│   ├── api/
│   │   ├── auth.py
│   │   ├── modules.py
│   │   ├── characters.py
│   │   ├── game.py
│   │   ├── rooms.py
│   │   ├── ws.py
│   │   └── combat/
│   │       ├── __init__.py
│   │       ├── info.py
│   │       ├── attacks.py
│   │       ├── turns.py
│   │       ├── movement.py
│   │       ├── reactions.py
│   │       ├── spellcasting.py
│   │       ├── conditions.py
│   │       ├── deathsaves.py
│   │       └── ai_turn.py
│   ├── models/
│   ├── schemas/
│   ├── services/
│   │   ├── dnd_rules.py
│   │   ├── combat_service.py
│   │   ├── spell_service.py
│   │   ├── context_builder.py
│   │   ├── state_applicator.py
│   │   ├── character_roster.py
│   │   ├── rag_service.py
│   │   ├── local_rag_service.py
│   │   ├── local_rag_uploader.py
│   │   ├── llm.py
│   │   ├── langgraph_client.py
│   │   └── graphs/
│   │       ├── module_parser.py
│   │       ├── party_generator.py
│   │       └── dm_agent.py
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/client.js
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── store/gameStore.js
│   │   ├── utils/
│   │   └── data/
│   └── public/
└── docs/
```

---

## 4. 后端主链路

### 4.1 模组上传

`/modules/upload`

流程：

1. 解析原始文件
2. 调用 `module_parser` graph
3. 产出结构化模组数据
4. 写入本地 RAG（ChromaDB）

### 4.2 角色创建

`/characters/*`

包含：

- 玩家角色创建
- 角色选项查询
- AI 队友生成
- 法术准备与角色养成辅助操作

### 4.3 主叙事动作

`/game/action`

主流程：

1. `ContextBuilder` 组装输入
2. `LangGraphClient.call_dm_agent()`
3. `StateApplicator` 解析并落库
4. 如有需要触发战斗初始化
5. 多人模式下通过 WS 广播

### 4.4 战斗动作

战斗接口按功能拆到了 `backend/api/combat/` 子包内，外部路径不变，仍然挂在：

- `/game/combat/{session_id}`
- `/game/combat/{session_id}/action`
- `/game/combat/{session_id}/attack-roll`
- `/game/combat/{session_id}/damage-roll`
- `/game/combat/{session_id}/move`
- `/game/combat/{session_id}/spell`
- `/game/combat/{session_id}/end-turn`
- `/game/combat/{session_id}/ai-turn`
- `/game/combat/{session_id}/reaction`
- `/game/combat/{session_id}/death-save`

---

## 5. 当前数据模型要点

### Session

`backend/models/session.py`

除单人会话字段外，已包含多人字段：

- `is_multiplayer`
- `room_code`
- `host_user_id`
- `max_players`

### Character

角色模型除了基础职业/属性外，还承担：

- 玩家角色
- AI 队友
- 多职业信息
- 法术位 / 已知法术 / 准备法术
- 条件与持续时间
- 死亡豁免
- 个性字段：
  - `personality`
  - `speech_style`
  - `combat_preference`
  - `catchphrase`
  - `backstory`

这些人格字段现在会被 DM/队友反应链路消费。

### CombatState

当前战斗状态除位置、先攻、日志外，还包含：

- `turn_states`

用于追踪：

- `action_used`
- `bonus_action_used`
- `reaction_used`
- `movement_used`
- `movement_max`
- `disengaged`
- `being_helped`

---

## 6. 前端架构要点

### 当前页面

- `Login.jsx`
- `Home.jsx`
- `CharacterCreate.jsx`
- `Adventure.jsx`
- `Combat.jsx`
- `CharacterSheet.jsx`
- `RoomLobby.jsx`
- `Room.jsx`

### 当前特点

- `Adventure.jsx` 和 `Combat.jsx` 仍然是高复杂度页面
- 但已经拆出不少 hooks / components / utils
- WS 连接逻辑集中在 `src/hooks/useWebSocket.js`
- API 调用集中在 `src/api/client.js`

### 设计方向

当前前端不是单纯原型，而是偏“沉浸式桌游风格 + CRPG 感”的混合体验，已经有：

- 3D 骰子动画
- 战斗网格地图
- 角色头像/精灵资源
- 冒险与战斗的分屏 UI
- 多人回合提示与房间同步

---

## 7. 多人联机现状

当前代码已支持：

- 注册 / 登录
- 创建房间
- 通过房间码加入
- 分配角色
- WebSocket 在线状态同步
- 发言权轮转
- DM 思考中广播
- 联机战斗状态刷新

相关文件：

- `backend/api/rooms.py`
- `backend/api/ws.py`
- `backend/models/session_member.py`
- `backend/services/ws_manager.py`
- `frontend/src/hooks/useWebSocket.js`
- `frontend/src/pages/RoomLobby.jsx`
- `frontend/src/pages/Room.jsx`

---

## 8. 规则引擎现状

核心规则仍在本地后端处理，而不是交给 LLM：

- 掷骰
- 命中判定
- 伤害 / 治疗
- 豁免
- 先攻
- 条件效果
- 集中检定
- 死亡豁免
- 部分职业特性
- 借机攻击
- 双持攻击

主要文件：

- `backend/services/dnd_rules.py`
- `backend/services/combat_service.py`
- `backend/services/spell_service.py`

原则保持不变：

> AI 负责叙事与意图组织，本地代码负责规则与数值可信度。

---

## 9. 当前已知现实情况

这份文档刻意以**代码实际状态**为准，而不是历史设计稿。

需要特别记住的几点：

1. 仓库已经不是单人 MVP
2. combat 路由已经拆包，不再是单文件巨型实现
3. 前端实际依赖不是 React 18 / Router v6 / fetch，而是：
   - React 19
   - Router 7
   - Axios
4. `dm_agent` 已经开始做内部职责解耦，避免队友反应抢占主叙事

---

## 10. 启动方式

### 后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

默认访问：

- 前端：`http://localhost:3000` 或 Vite 当前端口
- 后端文档：`http://localhost:8000/docs`

---

## 11. 维护建议

如果后续继续演进，优先保持这几个约束：

1. **前后端接口稳定**
   - 内部 graph 怎么拆都行，外部字段尽量别抖

2. **规则结算留在本地**
   - 不把核心数学交给模型

3. **AI prompt 职责分层**
   - DM 主叙事
   - 队友人格化反应
   - 不让附属输出挤压主体验

4. **多人逻辑单独审视**
   - 单人可行不代表多人也可行
   - 发言权、当前行动者、WS 重连都要单独验证

5. **文档以代码为准**
   - 每次结构变化后同步这里，避免档案继续漂移
