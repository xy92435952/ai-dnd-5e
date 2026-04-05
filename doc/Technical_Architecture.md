# 软件技术文档

**项目：** AI 跑团平台（DnD 5e）
**版本：** Phase 14 v8.0
**日期：** 2026-04-05（项目启动：2026-02-10）

---

## 1. 系统架构

### 1.1 架构总览

```
┌─────────────────────────────────────────────────┐
│                  用户层 (React 19)                │
│     Vite 8 + Tailwind CSS v4 + Zustand 5        │
│              + Fantastic Dice                    │
└──────────────────────┬──────────────────────────┘
                       │ HTTP / Vite Proxy
                       ▼
┌─────────────────────────────────────────────────┐
│              API 网关层 (FastAPI)                 │
│         JWT 认证 + 路由分发 + 异常处理             │
└──────────┬───────────┬──────────────────────────┘
           │           │
           ▼           ▼
┌──────────────┐ ┌────────────────────────────────┐
│  规则引擎层   │ │      AI 编排层 (LangGraph)       │
│ dnd_rules.py │ │  3 Graphs + AI Combat Agent    │
│combat_service│ │                                │
│spell_service │ │      ┌──────────────┐          │
└──────┬───────┘ │      │  RAG 知识库层  │          │
       │         │      │  (ChromaDB)  │          │
       │         │      └──────────────┘          │
       │         │              │                  │
       │         │              ▼                  │
       │         │    ┌──────────────────┐         │
       │         │    │   AI 模型层       │         │
       │         │    │ Claude Sonnet 4.6│         │
       │         │    │  via AiHubMix    │         │
       │         │    └──────────────────┘         │
       │         └────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────────┐
│            数据层 (SQLite + SQLAlchemy 2.0)       │
│          AsyncSession + 连接池 + 事务管理          │
└─────────────────────────────────────────────────┘
```

### 1.2 请求生命周期

```
用户操作 → React 组件 → Zustand Action → API Client (fetch)
  → Vite Dev Proxy (/api → localhost:8000)
  → FastAPI Router → 依赖注入 (get_db, get_current_user)
  → Service 层 (规则计算 / AI 调用)
  → 数据库读写
  → Pydantic 响应模型 → JSON 返回
```

### 1.3 技术栈版本

| 组件 | 版本 | 用途 |
|------|------|------|
| React | 19 | 前端 UI 框架 |
| Vite | 8 | 构建工具 + 开发服务器 |
| Tailwind CSS | v4 | 原子化 CSS |
| Zustand | 5 | 全局状态管理 |
| Fantastic Dice | latest | 3D 骰子动画渲染 |
| Python | 3.11+ | 后端运行时 |
| FastAPI | 0.115+ | Web 框架 |
| SQLAlchemy | 2.0 | ORM |
| SQLite | 3 | 关系型数据库 |
| LangGraph | latest | AI 工作流编排 |
| ChromaDB | latest | 向量数据库 |
| Claude Sonnet 4.6 | — | LLM（via AiHubMix OpenAI 兼容 API） |

---

## 2. 目录结构

```
ai-dnd-5e/
├── backend/
│   ├── main.py                   # FastAPI 应用入口，CORS，路由挂载
│   ├── config.py                 # 环境变量配置（API Key, DB URL, JWT Secret）
│   ├── database.py               # SQLAlchemy 引擎 + AsyncSession 工厂
│   │
│   ├── api/                      # API 路由层
│   │   ├── __init__.py
│   │   ├── auth.py               # 用户认证（POST /register, /login, GET /me）
│   │   ├── characters.py         # 角色 CRUD + AI 队友生成触发
│   │   ├── combat.py             # 战斗系统（~4500行）— 攻击/法术/移动/AI回合/子职业能力
│   │   ├── game.py               # 会话管理 + 主跑团循环（探索模式交互）
│   │   ├── modules.py            # 模组上传 + 解析触发
│   │   └── deps.py               # 共享依赖（get_db, get_current_user）
│   │
│   ├── services/                 # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── ai_combat_agent.py    # AI 战斗决策 Agent（敌人策略 + 队友策略）
│   │   ├── combat_service.py     # 战斗机制核心（攻击判定/偷袭/斩击/擒抱/借机攻击/条件优劣势）
│   │   ├── combat_narrator.py    # LLM 战斗叙事生成
│   │   ├── context_builder.py    # DM 上下文构建器（场景/角色/状态/金币→Prompt）
│   │   ├── dnd_rules.py          # 5e 规则引擎（~1500行）— 属性计算/AC/HP/技能/法术位
│   │   ├── spell_service.py      # 法术注册表（99+ SRD 法术，含效果/射程/伤害/豁免）
│   │   ├── state_applicator.py   # DM 响应 → 游戏状态应用（HP变化/金币/条件/战斗触发）
│   │   ├── llm.py                # LLM 工厂函数（ChatOpenAI 配置）
│   │   ├── langgraph_client.py   # LangGraph 统一调用客户端
│   │   ├── local_rag_service.py  # ChromaDB RAG 语义检索服务
│   │   │
│   │   └── graphs/               # LangGraph 工作流定义
│   │       ├── __init__.py
│   │       ├── dm_agent.py       # Graph 3: DM Agent（探索模式 + 战斗模式）
│   │       ├── module_parser.py  # Graph 1: 模组解析（文件→结构化JSON→向量化）
│   │       └── party_generator.py # Graph 2: AI 队友生成（职业互补+人格）
│   │
│   ├── models/                   # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── user.py               # User 模型
│   │   ├── module.py             # Module 模型
│   │   ├── character.py          # Character 模型（含 derived JSON）
│   │   ├── session.py            # Session 模型（含 game_state / campaign_state）
│   │   ├── combat_state.py       # CombatState 模型（先攻/位置/回合状态）
│   │   └── game_log.py           # GameLog 模型（对话/骰子/系统日志）
│   │
│   ├── schemas/                  # Pydantic 请求/响应模型
│   │   ├── __init__.py
│   │   ├── auth.py               # UserCreate, UserLogin, Token, UserResponse
│   │   ├── character.py          # CharacterCreate, CharacterResponse
│   │   ├── combat.py             # AttackRequest, SpellRequest, MoveRequest...
│   │   ├── game.py               # SessionCreate, SessionResponse, ChatRequest
│   │   └── module.py             # ModuleResponse
│   │
│   ├── data/
│   │   └── spells_srd.json       # SRD 法术数据库（99+ 法术完整定义）
│   │
│   └── chroma_db/                # ChromaDB 持久化存储目录
│
├── frontend/
│   ├── index.html                # SPA 入口
│   ├── vite.config.js            # Vite 配置（代理 /api → backend:8000）
│   ├── tailwind.config.js        # Tailwind CSS 配置
│   ├── package.json
│   │
│   └── src/
│       ├── main.jsx              # React 应用入口
│       ├── App.jsx               # 路由配置（React Router）
│       │
│       ├── pages/
│       │   ├── Home.jsx          # 首页 — 模组列表 + 存档列表 + 快速开始
│       │   ├── Login.jsx         # 登录 / 注册页面（双模式切换）
│       │   ├── CharacterCreate.jsx # 6-7步创角向导（种族→职业→子职→属性→技能→装备→法术）
│       │   ├── Adventure.jsx     # 主跑团界面 — 对话流 + DM 叙事 + 检定结果
│       │   ├── Combat.jsx        # 网格战斗页面（~1500行）— 地图/行动栏/状态面板
│       │   └── CharacterSheet.jsx # 角色详情页 — 属性/技能/装备/法术/特性
│       │
│       ├── components/
│       │   ├── DiceRollerOverlay.jsx # 3D 骰子动画覆盖层（Fantastic Dice 集成）
│       │   └── Icons.jsx           # SVG 图标组件库
│       │
│       ├── store/
│       │   └── gameStore.js      # Zustand 全局状态（用户/会话/角色/战斗/UI）
│       │
│       ├── api/
│       │   └── client.js         # API 客户端封装（fetch + JWT Header + 错误处理）
│       │
│       ├── data/
│       │   └── dnd5e.js          # SRD 静态数据（种族/职业/子职业/技能/专长定义）
│       │
│       └── index.css             # 全局样式 + Tailwind 指令
│
├── doc/                          # 项目文档
│   ├── BRD.docx                  # 业务需求文档
│   ├── MRD.docx                  # 市场需求文档
│   ├── PRD_LangGraph_Migration.docx # LangGraph 迁移 PRD
│   ├── architecture.html         # 架构可视化
│   ├── MVP_Report.md             # MVP 完成报告
│   ├── Technical_Architecture.md # 本文档
│   └── Update_Roadmap.md         # 更新路线图
│
├── .env                          # 环境变量（API Key, JWT Secret）
├── requirements.txt              # Python 依赖
└── README.md                     # 项目说明
```

---

## 3. 数据模型

### 3.1 ER 关系图

```
User (1) ──── (*) Session
User (1) ──── (*) Character

Module (1) ──── (*) Session

Session (1) ──── (1) Character [player_character]
Session (1) ──── (*) Character [party_members]
Session (1) ──── (0..1) CombatState
Session (1) ──── (*) GameLog
```

### 3.2 表结构详情

#### User

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, Auto | 用户 ID |
| username | String(50) | Unique, Not Null | 登录用户名 |
| password_hash | String(255) | Not Null | bcrypt 哈希密码 |
| display_name | String(100) | Nullable | 显示名称 |
| created_at | DateTime | Default=now | 创建时间 |

#### Module

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, Auto | 模组 ID |
| user_id | Integer | FK → User | 上传者 |
| name | String(200) | Not Null | 模组名称 |
| file_path | String(500) | Not Null | 原始文件路径 |
| parsed_content | JSON | Nullable | LangGraph 解析后的结构化内容 |
| parse_status | String(20) | Default='pending' | 解析状态（pending/processing/completed/failed） |
| created_at | DateTime | Default=now | 上传时间 |

#### Character

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, Auto | 角色 ID |
| user_id | Integer | FK → User | 所属用户 |
| session_id | Integer | FK → Session, Nullable | 所属会话（AI 队友） |
| name | String(100) | Not Null | 角色名 |
| race | String(50) | Not Null | 种族 |
| char_class | String(50) | Not Null | 职业 |
| subclass | String(50) | Nullable | 子职业 |
| level | Integer | Default=1 | 等级 |
| ability_scores | JSON | Not Null | 六维属性 {str, dex, con, int, wis, cha} |
| derived | JSON | Not Null | 派生属性（AC, HP, 攻击加值, 技能加值等） |
| equipment | JSON | Default=[] | 装备列表 |
| spell_slots | JSON | Default={} | 法术位 {1: max/current, 2: ...} |
| known_spells | JSON | Default=[] | 已知法术列表 |
| prepared_spells | JSON | Default=[] | 已准备法术列表 |
| conditions | JSON | Default=[] | 当前条件效果列表 |
| class_resources | JSON | Default={} | 职业资源（狂暴次数, Ki 点, 优越骰等） |
| hit_points | Integer | Not Null | 当前 HP |
| max_hit_points | Integer | Not Null | 最大 HP |
| temp_hit_points | Integer | Default=0 | 临时 HP |
| gold | Integer | Default=0 | 金币 |
| is_player | Boolean | Default=true | 是否为玩家角色 |
| is_ally | Boolean | Default=false | 是否为 AI 队友 |
| personality | Text | Nullable | AI 队友性格描述 |
| speech_style | Text | Nullable | AI 队友语言风格 |
| fighting_style | String(50) | Nullable | 战斗风格 |
| feats | JSON | Default=[] | 专长列表 |
| death_saves | JSON | Default={success:0, fail:0} | 濒死豁免计数 |
| created_at | DateTime | Default=now | 创建时间 |

#### Session

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, Auto | 会话 ID |
| user_id | Integer | FK → User | 所属用户 |
| module_id | Integer | FK → Module | 使用的模组 |
| player_character_id | Integer | FK → Character | 玩家角色 |
| current_scene | Text | Nullable | 当前场景描述 |
| game_state | JSON | Default={} | 游戏运行状态 |
| campaign_state | JSON | Default={} | 战役持久状态（事件/NPC/任务） |
| combat_active | Boolean | Default=false | 是否在战斗中 |
| created_at | DateTime | Default=now | 创建时间 |
| updated_at | DateTime | Auto | 最后更新时间 |

#### CombatState

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, Auto | 战斗状态 ID |
| session_id | Integer | FK → Session, Unique | 所属会话 |
| turn_order | JSON | Not Null | 先攻顺序 [{id, name, initiative, is_player}] |
| current_turn_index | Integer | Default=0 | 当前行动者索引 |
| round_number | Integer | Default=1 | 当前回合数 |
| entity_positions | JSON | Not Null | 实体位置 {entity_id: {x, y}} |
| turn_states | JSON | Default={} | 行动配额 {entity_id: {action, bonus, movement, reaction}} |
| enemies | JSON | Default=[] | 敌人数据列表 |
| combat_log | JSON | Default=[] | 战斗日志 |

#### GameLog

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, Auto | 日志 ID |
| session_id | Integer | FK → Session | 所属会话 |
| role | String(20) | Not Null | 角色（user/assistant/system） |
| content | Text | Not Null | 内容 |
| log_type | String(20) | Default='chat' | 类型（chat/dice/system/combat） |
| dice_result | JSON | Nullable | 骰子结果 {type, rolls, total, dc, success} |
| created_at | DateTime | Default=now | 时间戳 |

---

## 4. API 端点列表

### 4.1 认证模块 `/api/auth`

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/auth/register` | 用户注册 | `{username, password, display_name?}` | `{id, username, display_name}` |
| POST | `/api/auth/login` | 用户登录 | `{username, password}` | `{access_token, token_type}` |
| GET | `/api/auth/me` | 当前用户信息 | — | `{id, username, display_name}` |

### 4.2 模组管理 `/api/modules`

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/modules/upload` | 上传模组文件 | `multipart/form-data {file}` | `{id, name, parse_status}` |
| GET | `/api/modules` | 获取模组列表 | — | `[{id, name, parse_status}]` |
| GET | `/api/modules/{id}` | 获取模组详情 | — | `{id, name, parsed_content, parse_status}` |

### 4.3 角色管理 `/api/characters`

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/characters` | 创建角色 | `{name, race, char_class, subclass, ability_scores, skills, equipment, spells, fighting_style?, feats?}` | `{id, name, ...derived}` |
| GET | `/api/characters` | 获取角色列表 | — | `[{id, name, race, char_class, level}]` |
| GET | `/api/characters/{id}` | 获取角色详情 | — | 完整角色数据 |
| POST | `/api/characters/generate-party` | AI 生成队友 | `{session_id, player_character_id}` | `[{id, name, ...}]` |

### 4.4 会话管理 `/api/game`

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/game/sessions` | 创建会话 | `{module_id, character_id}` | `{id, module_id, player_character_id}` |
| GET | `/api/game/sessions` | 获取会话列表 | — | `[{id, module_name, character_name, updated_at}]` |
| GET | `/api/game/sessions/{id}` | 获取会话详情 | — | `{id, ..., game_state, campaign_state}` |
| DELETE | `/api/game/sessions/{id}` | 删除会话 | — | `{message}` |
| POST | `/api/game/sessions/{id}/chat` | 跑团对话 | `{message}` | `{response, dice_results?, combat_trigger?}` |
| POST | `/api/game/sessions/{id}/opening` | AI 生成开场白 | — | `{opening_narrative}` |
| POST | `/api/game/sessions/{id}/campaign-log` | 生成战役日志 | — | `{log}` |

### 4.5 战斗系统 `/api/combat`

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/combat/sessions/{id}/start` | 发起战斗 | `{enemies: [{name, hp, ac, ...}]}` | `{combat_state, turn_order}` |
| GET | `/api/combat/sessions/{id}/state` | 获取战斗状态 | — | `{turn_order, positions, round, current_turn}` |
| POST | `/api/combat/sessions/{id}/attack` | 攻击（两步） | `{attacker_id, target_id, weapon?, step, d20_value?, damage_values?}` | Step1: `{attack_roll, hit}` / Step2: `{damage, target_hp}` |
| POST | `/api/combat/sessions/{id}/spell` | 施法（两步） | `{caster_id, spell_name, target_id?, step, d20_value?, damage_values?}` | Step1: `{spell_roll, ...}` / Step2: `{effect, ...}` |
| POST | `/api/combat/sessions/{id}/move` | 移动 | `{entity_id, x, y}` | `{new_position, movement_remaining, opportunity_attacks?}` |
| POST | `/api/combat/sessions/{id}/end-turn` | 结束回合 | `{entity_id}` | `{next_turn, condition_ticks}` |
| POST | `/api/combat/sessions/{id}/ai-turn` | AI 回合决策 | — | `{actions: [{type, ...}], narrative}` |
| POST | `/api/combat/sessions/{id}/end` | 结束战斗 | — | `{summary, xp, loot}` |
| POST | `/api/combat/sessions/{id}/rest` | 长休/短休 | `{rest_type: "long"/"short"}` | `{hp_restored, slots_restored, resources_restored}` |

**短休资源恢复表（Phase 14 新增）：**

| 职业 | 恢复资源 |
|------|---------|
| Fighter | Second Wind, Action Surge, Battle Master 优越骰 |
| Monk | Ki 点（全部恢复） |
| Bard (Lv5+) | Bardic Inspiration 次数 |
| Cleric | Channel Divinity 次数 |
| Paladin | Channel Divinity 次数 |
| Druid (Circle of Land) | Natural Recovery 法术位 |
| POST | `/api/combat/sessions/{id}/death-save` | 濒死豁免 | `{character_id}` | `{roll, successes, failures, stabilized?, dead?}` |
| POST | `/api/combat/sessions/{id}/grapple` | 擒抱/推撞 | `{attacker_id, target_id, type}` | `{contest_result, success}` |

### 4.6 子职业能力 `/api/combat`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `.../divine-smite` | 神圣斩击（Paladin） |
| POST | `.../sneak-attack` | 偷袭（Rogue） |
| POST | `.../rage` | 狂暴（Barbarian） |
| POST | `.../action-surge` | 行动奔涌（Fighter） |
| POST | `.../second-wind` | 活力恢复（Fighter） |
| POST | `.../cunning-action` | 灵巧动作（Rogue） |
| POST | `.../wild-magic-surge` | 野蛮魔法涌动检测（Wild Magic Sorcerer） |
| POST | `.../maneuver` | 战技使用（Battle Master） |

---

## 5. AI 系统设计

### 5.1 LangGraph Graph 1: 模组解析

```
START
  │
  ▼
[read_file] ── 读取上传文件（PDF/DOCX/TXT/MD）
  │
  ▼
[extract_text] ── 提取纯文本内容
  │
  ▼
[parse_structure] ── LLM 调用：识别章节/场景/NPC/怪物/道具/地图描述
  │                   输出结构化 JSON
  ▼
[vectorize] ── 分段写入 ChromaDB（按场景/NPC/遭遇分 chunk）
  │
  ▼
[save_result] ── 更新 Module.parsed_content + parse_status
  │
  ▼
END
```

### 5.2 LangGraph Graph 2: AI 队友生成

```
START
  │
  ▼
[analyze_player] ── 分析玩家角色（职业/子职/属性/装备）
  │
  ▼
[select_classes] ── LLM 决策：选择 2 个互补职业+子职业
  │                  （坦克/治疗/输出/控制平衡）
  ▼
[generate_personalities] ── LLM 生成个性+背景故事+语言风格
  │
  ▼
[build_characters] ── 调用 dnd_rules.calc_derived() 生成完整属性
  │                    分配装备+法术
  ▼
[save_to_db] ── 存储 Character 记录（is_ally=true）
  │
  ▼
END
```

### 5.3 LangGraph Graph 3: DM Agent

```
START
  │
  ▼
[build_context] ── ContextBuilder 构建完整上下文
  │                 （角色状态/金币/场景/campaign_state）
  ▼
[rag_retrieve] ── ChromaDB 语义检索（当前场景相关模组内容）
  │
  ▼
[route] ── 路由判断：探索模式 or 战斗模式？
  │
  ├──[探索模式]──▶ [explore_dm] ── LLM 生成叙事响应
  │                                 （含检定/战斗触发/金币变化指令）
  │                    │
  │                    ▼
  │               [apply_state] ── StateApplicator 应用状态变化
  │                    │            （HP/金币/条件/campaign_state）
  │                    │
  │                    ▼
  │               [check_combat_trigger] ── 检测战斗触发
  │                    │
  │                    ├──[触发]──▶ 返回 combat_trigger 信号
  │                    └──[未触发]──▶ 返回叙事响应
  │
  └──[战斗模式]──▶ [combat_dm] ── LLM 生成战斗叙事
                       │            （骰子池/掩体/条件/专注检定提示）
                       ▼
                  [apply_combat] ── 应用战斗状态变化
                       │
                       ▼
                      END
```

### 5.4 AI Combat Decision Agent

AI 战斗决策使用独立的 LLM Agent，根据控制方（敌人/队友）采用不同策略。

#### 敌人策略 Prompt 设计

```
角色：你是一个 D&D 5e 战斗战术 AI，控制敌方阵营。

目标：
1. 做出合理的战术决策（集火脆皮、保护己方、利用地形）
2. 根据敌人智力调整策略（低智力→近战冲锋，高智力→战术配合）
3. 不要故意放水，也不要过于碾压

可用行动：
- attack: 攻击目标（需指定 target_id, weapon）
- spell: 施放法术（需指定 spell_name, target）
- move: 移动到指定位置（需指定 x, y）
- end-turn: 结束回合

输入：
- 战场地图（20x12 网格 + 实体位置）
- 所有实体状态（HP/AC/条件/位置）
- 行动配额剩余
- 可用技能/法术列表
```

#### 队友策略 Prompt 设计

```
角色：你是一个 D&D 5e AI 队友，扮演 {character_name}（{class}/{subclass}）。

人格：{personality}
语言风格：{speech_style}

目标：
1. 作为团队成员配合行动（治疗优先级、坦克拉仇恨、输出集火）
2. 保持角色扮演风格（决策反映人格特征）
3. 不要抢风头，让玩家角色做主角

策略优先级：
- 治疗者：队友 HP < 50% 时优先治疗
- 坦克：保护脆皮队友，拦截敌人
- 输出：集火 DM 标记的优先目标
```

#### 难度动态调节

```python
def adjust_difficulty(party_status):
    avg_hp_ratio = mean(c.hp / c.max_hp for c in party)

    if avg_hp_ratio < 0.3:
        # 队伍危险 → 敌人犯更多"错误"
        strategy = "conservative"  # 分散攻击，不集火
    elif avg_hp_ratio > 0.8:
        # 队伍健康 → 敌人更聪明
        strategy = "aggressive"    # 集火脆皮，使用控制技能
    else:
        strategy = "balanced"
```

---

## 6. 5e 规则引擎

### 6.1 calc_derived() 计算流程

`dnd_rules.py` 中的 `calc_derived()` 函数从基础属性计算所有派生值：

```
输入: ability_scores {str, dex, con, int, wis, cha}, race, class, subclass, level, equipment, feats

Step 1: 种族加值
  → 应用种族属性加值（如 Hill Dwarf: CON+2, WIS+1）

Step 2: 属性修正值
  → modifier = floor((score - 10) / 2)  对每个属性

Step 3: 熟练加值
  → proficiency_bonus = floor((level - 1) / 4) + 2

Step 4: 生命值
  → HP = hit_die_max + CON_mod                    (1级)
       + (level-1) * (hit_die_avg + CON_mod)       (2级+)
  → Hill Dwarf: +1 HP/level
  → Tough feat: +2 HP/level

Step 5: 护甲等级
  → 无甲: 10 + DEX_mod
  → 轻甲: armor_base + DEX_mod
  → 中甲: armor_base + min(DEX_mod, 2)
  → 重甲: armor_base (无 DEX)
  → 盾牌: +2
  → Barbarian 无甲防御: 10 + DEX_mod + CON_mod
  → Monk 无甲防御: 10 + DEX_mod + WIS_mod

Step 6: 攻击加值
  → 近战: STR_mod + proficiency (或 DEX for Finesse)
  → 远程: DEX_mod + proficiency
  → 法术: spellcasting_mod + proficiency

Step 7: 豁免
  → 每个职业有 2 个豁免熟练
  → save = modifier + (proficiency if proficient)

Step 8: 技能加值
  → skill = ability_mod + (proficiency if proficient)
  → Expertise: proficiency × 2

Step 9: 法术位
  → 按职业法术位表计算（全施法/半施法/1/3施法）
  → Warlock: 契约魔法（短休恢复）

Step 10: 职业资源
  → Barbarian: rage_count by level
  → Fighter: action_surge, second_wind
  → Monk: ki_points = level
  → Rogue: sneak_attack_dice
  → Paladin: divine_smite slots
  → Sorcerer: sorcery_points
  → Bard: bardic_inspiration_dice + count
  → Battle Master: superiority_dice count + size

Step 11: 子职业效果
  → 应用 subclass_effects（见 6.2）

输出: derived JSON（AC, HP, attacks, saves, skills, spell_slots, class_resources, speed, initiative...）
```

### 6.2 53 子职业效果清单

#### Barbarian（野蛮人）
| 子职业 | 效果 |
|--------|------|
| Berserker | 狂暴时可狂乱攻击（附赠行动近战），狂暴结束后力竭 |
| Totem Warrior (Bear) | 狂暴时抵抗除心灵外所有伤害类型 |
| Totem Warrior (Eagle) | 狂暴时借机攻击对你有劣势 |
| Totem Warrior (Wolf) | 狂暴时盟友对你相邻敌人有优势 |
| Ancestral Guardian | 狂暴攻击标记敌人，被标记者攻击其他人有劣势 |
| Storm Herald (Desert) | 狂暴时周围敌人受火焰伤害 |
| Storm Herald (Sea) | 狂暴时闪电射击（DEX 豁免） |
| Storm Herald (Tundra) | 狂暴时给予盟友临时 HP |
| Zealot | 狂暴首次攻击额外神圣/黯蚀伤害 |

#### Bard（吟游诗人）
| 子职业 | 效果 |
|--------|------|
| College of Lore | 额外技能熟练，削减灵感（反应减敌人攻击/检定） |
| College of Valor | 中甲+盾牌熟练，战斗灵感（加伤害或AC） |
| College of Swords | 剑舞风格（防御/灵巧/挥砍），额外攻击 |
| College of Glamour | 魅惑表演（临时HP+移动） |
| College of Whispers | 心灵之刃（类偷袭额外心灵伤害） |

#### Cleric（牧师）
| 子职业 | 效果 |
|--------|------|
| Life Domain | 治疗法术额外恢复（2+法术环级），重甲熟练 |
| Light Domain | 灼热反击（反应对攻击者造成光辉伤害） |
| War Domain | 战争牧师攻击（附赠行动攻击），引导神力+10攻击 |
| Tempest Domain | 雷电最大化伤害（引导神力），重甲+军用武器 |
| Knowledge Domain | 额外语言和技能，读取思维 |
| Trickery Domain | 幻影分身（优势来源），隐匿祝福 |

#### Druid（德鲁伊）
| 子职业 | 效果 |
|--------|------|
| Circle of the Land | 自然恢复（短休回法术位），地形奖励法术 |
| Circle of the Moon | 强化野性形态（更高 CR），战斗野性形态 |
| Circle of Spores | 孢子光环（毒素伤害），尸体操纵 |

#### Fighter（战士）
| 子职业 | 效果 |
|--------|------|
| Champion | 重击范围扩展（19-20），额外战斗风格 |
| Battle Master | 7种战技（精确/推撞/招架/佯攻/横扫/指挥/威吓），优越骰 |
| Eldritch Knight | 护盾术+法术绑定武器，战争魔法（施法+附赠攻击） |

#### Monk（武僧）
| 子职业 | 效果 |
|--------|------|
| Way of the Open Hand | 震山掌（附加效果：击倒/推开/禁反应） |
| Way of Shadow | 暗影步（传送到阴影），暗影施法 |
| Way of the Four Elements | 元素拳（Ki→法术效果） |

#### Paladin（圣骑士）
| 子职业 | 效果 |
|--------|------|
| Oath of Devotion | 神圣武器（+CHA攻击，发光），辟邪结界 |
| Oath of the Ancients | 自然守护（法术抗性光环） |
| Oath of Vengeance | 誓言之敌（优势攻击标记目标），追猎者 |

#### Ranger（游侠）
| 子职业 | 效果 |
|--------|------|
| Hunter | 巨人杀手 / 巨像破坏者 / 群敌破阵（三选一额外伤害） |
| Beast Master | 兽伴（标记，宠物系统未完整实装） |
| Gloom Stalker | 首轮额外攻击+伤害，黑暗视觉中隐形 |

#### Rogue（游荡者）
| 子职业 | 效果 |
|--------|------|
| Thief | 快手（附赠行动使用物品），攀爬速度 |
| Assassin | 突袭（先攻高于目标时自动重击），伪装 |
| Arcane Trickster | 法术手+隐形手，法术偷袭增强 |
| Swashbuckler | 华丽决斗（1v1 偷袭），优雅脱身（免借机攻击） |
| Scout | 敏捷探子（反应移动），自然/求生专精 |

#### Sorcerer（术士）
| 子职业 | 效果 |
|--------|------|
| Draconic Bloodline | 龙裔韧性（+1HP/级），元素亲和力（+CHA伤害） |
| Wild Magic | 涌动表（20种随机效果），潮汐混沌（优势/劣势操控） |
| Shadow Magic | 暗影猎犬，黑暗中优势，0HP时CON豁免存活 |

#### Warlock（邪术师）
| 子职业 | 效果 |
|--------|------|
| The Fiend | 击杀临时HP，地狱谴责（反应火焰伤害） |
| The Great Old One | 心灵感应，思维护盾（心灵抗性） |
| The Hexblade | 咒刃武器（CHA攻击），额外重击扩展 |

#### Wizard（法师）
| 子职业 | 效果 |
|--------|------|
| School of Evocation | 塑形术（队友豁免伤害法术），强效戏法（+INT伤害） |
| School of Abjuration | 奥术守护（临时HP护盾），法术抵抗 |
| School of Divination | 预言骰（预先掷骰替代任意 d20） |
| War Magic | 战术智慧（+INT先攻），奥术偏转（+2AC/+4豁免） |

### 6.3 战斗流程图

#### 玩家攻击流程

```
玩家选择"攻击" + 目标
  │
  ▼
POST /combat/.../attack {step: "attack-roll"}
  │
  ├─ 计算攻击加值 (STR/DEX_mod + proficiency + magic_bonus)
  ├─ 检查优势/劣势（conditions, flanking, class_features）
  ├─ 掷 d20 + 修正
  │
  ├─ Nat 20 → 重击（伤害骰翻倍）
  ├─ Nat 1 → 自动未命中
  └─ total >= target_AC → 命中
  │
  ▼
前端显示 3D 骰子动画
  │
  ▼
[命中] → POST /combat/.../attack {step: "damage-roll"}
  │
  ├─ 掷伤害骰 (weapon_damage + modifier)
  ├─ 重击: 伤害骰数量翻倍
  ├─ 检查偷袭 → 额外 sneak_attack_dice × d6
  ├─ 检查神圣斩击 → 额外 (slot_level+1) × d8
  ├─ 检查狂暴 → +rage_damage
  ├─ 计算抗性/易伤
  └─ 应用伤害 → 更新目标 HP
  │
  ├─ 目标 HP ≤ 0 → 死亡/濒死
  └─ 返回伤害结果 + 叙事
```

#### 法术施放流程

```
玩家选择"施法" + 法术 + 目标
  │
  ▼
POST /combat/.../spell {step: "spell-roll"}
  │
  ├─ 查询 spell_service 注册表
  ├─ 检查法术位是否足够
  ├─ 检查专注冲突
  │
  ├─ [攻击型法术] → 法术攻击骰 d20 + spell_mod + proficiency
  ├─ [豁免型法术] → 记录 DC = 8 + proficiency + spell_mod
  └─ [治疗/增益] → 直接进入效果阶段
  │
  ▼
POST /combat/.../spell {step: "spell-confirm"}
  │
  ├─ [攻击命中] → 掷伤害骰
  ├─ [豁免失败] → 施加完整效果
  ├─ [豁免成功] → 半伤或无效果
  ├─ [治疗] → 掷治疗骰 → 恢复 HP
  ├─ [Buff] → 应用条件效果（持续时间追踪）
  ├─ [Control/Utility] → 豁免检定 → 施加条件（Phase 14 新增）
  │     22 种法术→条件映射：
  │     Hold Person→paralyzed, Command→prone, Blindness→blinded,
  │     Web→restrained, Fear→frightened, Entangle→restrained,
  │     Hideous Laughter→prone+incapacitated, 等
  │
  ├─ 消耗法术位
  ├─ 设置专注（如适用）
  └─ 返回效果结果 + 叙事
```

#### AI 回合流程

```
当前回合 = AI 控制角色（敌人 or 队友）
  │
  ▼
POST /combat/.../ai-turn
  │
  ▼
[AI Combat Agent]
  │
  ├─ 构建战场信息（地图/位置/HP/条件/行动配额）
  ├─ 选择策略（敌人 vs 队友 Prompt）
  ├─ 难度动态调节
  │
  ▼
LLM 返回行动计划
  │
  ├─ 验证行动合法性（射程/配额/法术位）
  ├─ 自动移动靠近目标（如需要）
  │
  ▼
执行行动序列：
  ├─ 移动 → 更新位置 → 检测借机攻击
  ├─ 攻击 → attack-roll → damage-roll
  ├─ 法术 → spell-roll → spell-confirm（Phase 14: AI 队友可施法）
  │     AI 施法分支：消耗法术位，处理专注，支持伤害/治疗/控制
  ├─ 附赠行动 → 狂暴/灵巧动作/等
  └─ 结束回合 → 条件 tick → 下一个回合
  │
  安全机制（Phase 14 新增）：
  ├─ 20 回合上限 → 强制退出 AI 循环
  └─ turn-index-unchanged 检测 → 防止无限循环
  │
  ▼
返回行动结果 + LLM 叙事
```

---

## 7. 前端架构

### 7.1 页面路由

```
/                     → Home.jsx          （首页，模组列表+存档列表）
/login                → Login.jsx         （登录/注册）
/character/create     → CharacterCreate.jsx（创角向导）
/character/:id        → CharacterSheet.jsx （角色详情）
/adventure/:sessionId → Adventure.jsx     （跑团界面）
/combat/:sessionId    → Combat.jsx        （网格战斗）
```

路由守卫：未登录用户重定向至 `/login`，通过 Zustand store 中的 `token` 状态判断。

### 7.2 状态管理（Zustand Store）

`gameStore.js` 使用 Zustand 管理全局状态，采用单 store 多 slice 模式：

```javascript
// 状态结构
{
  // 用户状态
  user: null,              // 当前用户信息
  token: null,             // JWT Token

  // 会话状态
  currentSession: null,    // 当前游戏会话
  sessions: [],            // 会话列表

  // 角色状态
  currentCharacter: null,  // 当前玩家角色
  partyMembers: [],        // AI 队友列表

  // 战斗状态
  combatState: null,       // 战斗状态（turn_order, positions...）
  selectedAction: null,    // 当前选中的行动类型
  selectedTarget: null,    // 当前选中的目标
  actionStep: null,        // 两步行动的当前步骤

  // UI 状态
  diceRolling: false,      // 骰子动画播放中
  diceResults: null,       // 骰子结果（传给 Fantastic Dice）
  showSpellModal: false,   // 法术选择面板
  showManeuverModal: false,// 战技选择面板
  chatMessages: [],        // 对话消息列表
  isLoading: false,        // API 请求中
}
```

### 7.3 骰子动画系统（Phase 14: 前端驱动）

#### rollDice3D() — 前端驱动骰子系统

```
核心理念（Phase 14 新增）：
  前端 Fantastic Dice 物理模拟决定实际游戏值。
  骰子面值 = 显示数字 = 后端使用值。

触发流程：
  玩家触发行动（攻击/法术/检定）
    → rollDice3D() 调用 Fantastic Dice 物理模拟
    → 骰子滚动 → 落定 → 读取骰面值
    → 前端将结果发送给后端（d20_value / damage_values 参数）
    → 后端使用前端传来的值进行判定
    → 后端返回完整结果（命中/伤害/效果）

API 参数（向后兼容）：
  攻击端点: d20_value (optional int) — 前端 d20 骰面值
  伤害端点: damage_values (optional list[int]) — 前端伤害骰面值列表
  若未提供，后端自行掷骰（向后兼容旧客户端）

支持的骰子类型：
  d4, d6, d8, d10, d12, d20, d100 (percentile)

多骰同掷：
  如 Fireball 8d6 → 8 个 d6 同时在屏幕上滚动 → 读取每颗骰面值
```

### 7.4 战斗 UI 组件层次

```
Combat.jsx (主页面, ~1500行)
├── CombatMap (网格地图 20x12)
│   ├── GridCell × 240 (每个格子)
│   │   ├── EntityToken (角色/敌人图标)
│   │   └── TerrainIndicator (地形标记)
│   └── MoveOverlay (可移动范围高亮)
│
├── InitiativeTracker (先攻顺序条)
│   └── TurnIndicator × N (每个实体的先攻标记)
│
├── ActionBar (行动操作栏)
│   ├── AttackButton (攻击按钮)
│   ├── SpellButton (施法按钮 → 打开 SpellModal)
│   ├── MoveButton (移动按钮)
│   ├── EndTurnButton (结束回合)
│   ├── SubclassAbilityButtons × 15 (子职业能力按钮，动态)
│   │   ├── DivineSmiteBtn (神圣斩击)
│   │   ├── SneakAttackBtn (偷袭)
│   │   ├── RageBtn (狂暴)
│   │   ├── ActionSurgeBtn (行动奔涌)
│   │   ├── SecondWindBtn (活力恢复)
│   │   ├── CunningActionBtn (灵巧动作)
│   │   ├── ManeuverBtn (战技 → 打开 ManeuverModal)
│   │   └── ... (其他子职业按钮)
│   └── RestButton (休息按钮)
│
├── ReactionModal (反应选择弹窗, Phase 14 新增)
│   ├── Shield (护盾术 — +5AC，消耗1环法术位)
│   ├── Uncanny Dodge (不可思议闪避 — 伤害减半)
│   ├── Hellish Rebuke (地狱谴责 — 反击火焰伤害)
│   ├── Absorb Elements (吸收元素 — 抗性+下次攻击额外伤害)
│   └── Counterspell (反制法术 — 取消敌方法术)
│
├── SpellModal (法术选择弹窗, Phase 14: 按职业过滤)
│   ├── SpellLevelTabs (分环级标签)
│   └── SpellCard × N (按玩家职业过滤，非全部 99 法术)
│
├── ManeuverModal (战技选择弹窗)
│   └── ManeuverCard × 7 (7种战技)
│
├── EntityStatusPanel (实体状态面板)
│   ├── HPBar (血条)
│   ├── ConditionIcons (条件图标)
│   ├── SpellSlotDisplay (法术位显示)
│   └── ResourceDisplay (职业资源显示)
│
├── CombatLog (战斗日志滚动区)
│   └── LogEntry × N (日志条目)
│
└── DiceRollerOverlay (3D 骰子动画覆盖层)
    └── FantasticDice (第三方3D骰子库)
```

---

## 附录 A: 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `DATABASE_URL` | SQLite 数据库路径 | `sqlite+aiosqlite:///./app.db` |
| `JWT_SECRET` | JWT 签名密钥 | 随机字符串 |
| `AIHUBMIX_API_KEY` | AiHubMix API 密钥 | `sk-...` |
| `AIHUBMIX_BASE_URL` | AiHubMix API 基础 URL | `https://api.aihubmix.com/v1` |
| `MODEL_NAME` | LLM 模型名称 | `claude-sonnet-4-6-20250514` |
| `CHROMA_PERSIST_DIR` | ChromaDB 持久化目录 | `./chroma_db` |

## 附录 B: 关键依赖

### Python (requirements.txt)

| 包 | 用途 |
|----|------|
| fastapi | Web 框架 |
| uvicorn | ASGI 服务器 |
| sqlalchemy[asyncio] | ORM（异步） |
| aiosqlite | SQLite 异步驱动 |
| python-jose[cryptography] | JWT 处理 |
| passlib[bcrypt] | 密码哈希 |
| langchain / langgraph | AI 编排 |
| chromadb | 向量数据库 |
| openai | LLM API 客户端（AiHubMix 兼容） |
| python-multipart | 文件上传 |
| pydantic | 数据验证 |

### Node.js (package.json)

| 包 | 用途 |
|----|------|
| react / react-dom | UI 框架 |
| react-router-dom | 客户端路由 |
| zustand | 状态管理 |
| @3d-dice/fantastic-dice | 3D 骰子动画 |
| tailwindcss | 原子化 CSS |
| vite | 构建工具 |
