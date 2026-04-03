# CLAUDE.md — AI跑团平台项目档案

> 最后更新：2026-04-01
> 项目状态：Phase 11 完成 — Dify → LangGraph 全面迁移完成，AI 层完全本地化
> 当前阻塞：无
> 项目路径：`D:\program\game`

---

## 目录

1. [产品定位](#1-产品定位)
2. [技术栈](#2-技术栈)
3. [目录结构](#3-目录结构)
4. [数据模型](#4-数据模型)
5. [后端 API 全览](#5-后端-api-全览)
6. [LangGraph AI 编排](#6-langgraph-ai-编排phase-11-替换-dify)
7. [5e 规则引擎](#7-5e-规则引擎)
8. [前端架构](#8-前端架构)
9. [开发阶段与当前进度](#9-开发阶段与当前进度)
10. [待办与已知问题](#10-待办与已知问题)
11. [架构决策记录](#11-架构决策记录)
12. [启动方式](#12-启动方式)

---

## 1. 产品定位

**AI跑团平台**：基于 DnD 5e 规则、运行于浏览器的单人跑团游戏。

- 用户上传模组文件（PDF/DOCX/MD/TXT）
- AI 担任地下城主（DM）并扮演 AI 队友
- 完整实现 5e 规则引擎（骰子/检定/战斗/法术）
- 网格战斗地图，实时可视化
- 当前目标：**本地 MVP，验证核心玩法**

核心差异点：规则骨架（5e 引擎）+ AI 叙事 + 网格战斗地图，三者结合。

---

## 2. 技术栈

### 后端

| 组件 | 版本/选型 |
|------|---------|
| 框架 | FastAPI (async) |
| 数据库 | SQLite + SQLAlchemy 2.0 (async) |
| 驱动 | aiosqlite |
| 数据验证 | Pydantic v2 |
| 文件解析 | pymupdf（PDF）、python-docx（DOCX）、markdown |
| AI 编排 | LangGraph StateGraph（替换 Dify） |
| LLM 接入 | langchain-openai（OpenAI 兼容 API，AiHubMix） |
| 对话记忆 | LangGraph AsyncSqliteSaver（thread_id=session_id） |
| RAG 向量库 | ChromaDB（本地持久化，替换 Dify KB） |
| 运行 | uvicorn |

### 前端

| 组件 | 选型 |
|------|------|
| 框架 | React 18 + Vite |
| 路由 | React Router v6 |
| 全局状态 | Zustand |
| HTTP | fetch（封装在 `api/client.js`） |
| 样式 | 原生 CSS（无 UI 库） |

### AI 服务（Phase 11 迁移后）

- **编排框架**：LangGraph StateGraph（纯 Python，替换 Dify）
- **LLM Provider**：AiHubMix（OpenAI 兼容 API），通过 `langchain-openai` 接入
- **模型**：Claude Sonnet 4.6（`claude-sonnet-4-6`），可通过 `.env` 一行切换
- **对话记忆**：`AsyncSqliteSaver`，独立文件 `langgraph_memory.db`，`thread_id = session.id`
- **RAG**：ChromaDB 本地向量库，`module_chunks` collection，metadata 过滤按 module_id 隔离
- **Graph 架构**：3 个独立 StateGraph — module_parser / party_generator / dm_agent
- **统一接口**：`LangGraphClient`（与旧 `DifyClient` 方法签名完全一致，零改动上层代码）

---

## 3. 目录结构

```
game/
├── CLAUDE.md                    ← 本文件
├── PRD.md                       ← 产品需求文档
├── README.md
├── start.bat                    ← 一键启动脚本
├── test_module_silver_hollow.txt ← 测试用模组文本
│
├── backend/
│   ├── main.py                  ← FastAPI 入口，注册所有 router
│   ├── config.py                ← Pydantic Settings（读取 .env），含 RAG/Chatflow 新配置
│   ├── database.py              ← SQLAlchemy engine / session / Base
│   ├── requirements.txt
│   ├── .env                     ← 实际密钥（不入库）
│   ├── .env.example             ← 密钥模板
│   ├── ai_trpg.db               ← SQLite 数据库文件
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py              ← 共享依赖：get_session_or_404, char_brief,
│   │   │                           entity_snapshot, serialize_combat, serialize_log
│   │   ├── modules.py           ← /modules — 模组上传/解析/列表/删除
│   │   ├── characters.py        ← /characters — 角色创建/列表/AI队友生成/准备法术
│   │   ├── game.py              ← /game — Session管理/主跑团循环(ContextBuilder+StateApplicator)/
│   │   │                           技能检定/战役日志/checkpoint/休息
│   │   └── combat.py            ← /game/combat — 战斗全流程/法术/移动/结束回合
│   │
│   ├── models/
│   │   ├── __init__.py          ← 统一导出所有 ORM 模型
│   │   ├── module.py            ← Module（模组）
│   │   ├── character.py         ← Character（玩家+AI队友），含多职业/条件计时/子职业
│   │   └── session.py           ← Session + CombatState + GameLog
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── game_schemas.py      ← JSON字段 Pydantic 类型：DerivedStats,
│   │                               EnemyState, GameState, TurnEntry,
│   │                               CombatEntitySnapshot, EntityPosition
│   │
│   ├── services/
│   │   ├── dnd_rules.py         ← 核心规则引擎（纯计算，无 IO）
│   │   ├── combat_service.py    ← CombatService（攻击/治疗/条件/AI目标选择）
│   │   ├── spell_service.py     ← SpellService，从 data/spells_srd.json 加载法术注册表
│   │   ├── llm.py               ← LLM 工厂函数 get_llm()（所有 Graph 共用）★ Phase 11 新增
│   │   ├── langgraph_client.py  ← LangGraphClient（替换 DifyClient，接口签名完全一致）★
│   │   ├── dify_client.py       ← DifyClient（已废弃，保留兼容，不再被引用）
│   │   ├── module_parser.py     ← 本地文件解析（PDF/DOCX/MD/TXT → 纯文本）
│   │   ├── context_builder.py   ← ContextBuilder：序列化为 DM Agent 输入（含 RAG）
│   │   ├── state_applicator.py  ← StateApplicator：解析 state_delta，应用到数据库
│   │   ├── rag_service.py       ← RAG 服务接口：BaseRagService + get_rag_service()
│   │   │                           工厂（自动选择 LocalRagService 或存根）
│   │   ├── local_rag_service.py ← LocalRagService（ChromaDB 检索）★ Phase 11 新增
│   │   ├── local_rag_uploader.py ← LocalRagUploader（ChromaDB 上传/删除）★ Phase 11 新增
│   │   ├── dify_rag_uploader.py ← DifyRagUploader（已废弃，不再被引用）
│   │   │
│   │   └── graphs/              ← LangGraph StateGraph 定义 ★ Phase 11 新增
│   │       ├── __init__.py
│   │       ├── module_parser.py ← WF1 图：4节点线性链（LLM提取→验证→LLM chunks→验证）
│   │       ├── party_generator.py ← WF2 图：3节点线性链（角色分析→LLM生成→衍生属性）
│   │       └── dm_agent.py      ← WF3 图：条件分支（骰子预掷→战斗/探索LLM→解析验证）
│   │                               + SqliteSaver 对话记忆 + Campaign State 生成
│   │
│   ├── data/
│   │   └── spells_srd.json      ← SRD 法术数据（99+ 法术，0-7 环，支持 // 注释）
│   │
│   └── migrate_*.py             ← 数据库迁移脚本（手动运行）
│       ├── migrate_multiclass.py          ← 添加 multiclass_info 列
│       ├── migrate_turn_states.py         ← 添加 CombatState.turn_states 列
│       ├── migrate_dify_conversation_id.py ← 添加 Session.dify_conversation_id 列
│       └── migrate_condition_durations.py ← 添加 Character.condition_durations 列
│
├── frontend/
│   ├── index.html
│   ├── vite.config.js           ← 代理 /api → http://localhost:8000
│   ├── package.json
│   ├── eslint.config.js
│   ├── src/
│   │   ├── main.jsx             ← React 入口
│   │   ├── App.jsx              ← 路由定义（/、/setup/:moduleId、/adventure/:sessionId、/combat/:sessionId）
│   │   ├── App.css / index.css
│   │   ├── api/client.js        ← 所有 API 调用封装（gameApi 对象，含 endTurn/deathSave/prepareSpells 等）
│   │   ├── store/gameStore.js   ← Zustand 全局状态
│   │   ├── data/dnd5e.js        ← D&D 5e 游戏数据（种族/职业/技能等）
│   │   ├── pages/
│   │   │   ├── Home.jsx         ← 主页：模组列表/上传/选择存档
│   │   │   ├── CharacterCreate.jsx  ← 角色创建向导（施法职业5步/非施法4步，含法术选择）
│   │   │   ├── Adventure.jsx    ← 主跑团界面（对话+日志+技能检定）
│   │   │   └── Combat.jsx       ← 战斗界面（网格地图+行动配额面板+结束回合）
│   │   └── components/
│   │       └── DiceRollerOverlay.jsx  ← 3D骰子动画覆盖层（CSS 3D正二十面体）
│   └── dist/                    ← Vite 构建产物
│
└── dify_workflows/
    ├── 01_module_parser.yml          ← WF1：模组解析
    ├── 02_party_generator.yml        ← WF2：AI队友生成
    ├── 03_game_master.yml            ← WF3 旧版（blocking，保留兼容）
    ├── 03_game_master_chatflow.yml   ← WF3 当前版（Chatflow，原生对话记忆）★
    ├── 03_dm_agent.yml               ← WF3 新版 All-in-One（合并探索+战斗，设计中）
    └── 04_combat_narrator.yml        ← WF4：战斗叙述（保留，较少调用）
```

---

## 4. 数据模型

### Module（模组）

```
id, name, description, file_path, file_type,
raw_content(Text), parsed_content(JSON),
parse_status, parse_error,
level_min, level_max, recommended_party_size,
created_at
```

`parsed_content` 结构（由 WF1 输出）：
```json
{
  "setting": "...",
  "plot_summary": "...",
  "scenes": [{"title": "...", "description": "..."}],
  "npcs": [{"name": "...", "role": "...", "description": "..."}],
  "monsters": [{"name": "...", "cr": 2, "hp": 30, "ac": 13}]
}
```

### Character（角色，玩家+AI队友共用）

```
id, name, race, char_class, level, background
subclass(String)             # 子职业（圣武士誓约/牧师领域/战士流派等）
ability_scores(JSON)         # {str,dex,con,int,wis,cha} — 基础值（含种族加成后）
derived(JSON)                # DerivedStats: hp_max,ac,initiative,proficiency_bonus,
                             #   attack_bonus,spell_save_dc,spell_slots_max,
                             #   ability_modifiers,saving_throws,caster_type...
hp_current(Int)
spell_slots(JSON)            # {1st:2, 2nd:1, ...} — 当前剩余，用完递减
known_spells(JSON)           # 已知法术名称列表
prepared_spells(JSON)        # 已准备法术（法师/牧师/德鲁伊）
cantrips(JSON)               # 戏法列表（0环，无限使用）
concentration(String)        # 当前专注法术名，None表示未专注
proficient_skills(JSON)      # 熟练技能列表，如["运动","隐匿"]
proficient_saves(JSON)       # 熟练豁免，如["str","con"]
conditions(JSON)             # 当前状态条件列表
condition_durations(JSON)    # 各条件剩余回合数，如{"poisoned":3,"prone":1}
death_saves(JSON)            # 濒死豁免 {successes:0, failures:0, stable:false}，HP=0时启用
multiclass_info(JSON)        # 多职业信息，如{"char_class":"Fighter","level":2}，单职业为null
is_player(Bool)              # True=玩家，False=AI队友
session_id(String FK)        # 绑定到的会话
personality(Text)            # AI队友个性描述
backstory(Text)
speech_style(Text)           # AI队友说话风格（如"古板严肃"）
combat_preference(Text)      # AI队友战斗偏好（如"优先保护弱小"）
catchphrase(Text)            # AI队友口头禅
```

### Session

```
id, module_id, player_character_id
current_scene(Text)
session_history(Text)        # 近期对话（Chatflow 迁移后作为补充上下文）
game_state(JSON)             # GameState: companion_ids, scene_index, flags, enemies
combat_active(Bool)
dify_conversation_id(String) # Chatflow 对话 ID，跨轮次持久化（原生记忆）
campaign_state(JSON)         # 结构化长期记忆（checkpoint 生成）
save_name(String)
created_at, updated_at
```

`campaign_state` 结构：
```json
{
  "completed_scenes": ["场景1", "场景2"],
  "key_decisions": ["选择帮助村庄"],
  "npc_registry": {
    "NPC名": {
      "relationship": "friendly/hostile/neutral/unknown",
      "key_facts": ["..."],
      "promises": ["..."]
    }
  },
  "quest_log": [
    {"quest": "拯救村庄", "status": "active/completed/failed", "outcome": "..."}
  ],
  "world_flags": {"event_key": true},
  "notable_items": ["神器1"],
  "party_changes": ["角色升级", "成员加入"]
}
```

### CombatState

```
id, session_id
grid_data(JSON)          # {x_y: "wall/difficult"} 地形数据
entity_positions(JSON)   # {character_id: {x, y}}
turn_order(JSON)         # [TurnEntry: character_id, name, initiative, is_player, is_enemy]
current_turn_index(Int)
round_number(Int)
combat_log(JSON)
turn_states(JSON)        # 行动配额追踪，结构见下
created_at, updated_at
```

`turn_states` 结构（每实体一条）：
```json
{
  "entity_id": {
    "action_used": false,
    "bonus_action_used": false,
    "reaction_used": false,
    "movement_used": 0,
    "movement_max": 6,
    "disengaged": false,
    "being_helped": false
  }
}
```

### GameLog

```
id, session_id
role(String)             # dm / player / companion_{name} / system
content(Text)
log_type(String)         # narrative / combat / dice / companion / system
dice_result(JSON)        # 骰子原始结果
created_at
```

---

## 5. 后端 API 全览

### 模组 `/modules`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/modules` | 获取所有模组 |
| POST | `/modules/upload` | 上传并解析模组文件（multipart） |
| GET | `/modules/{id}` | 获取模组详情 |
| DELETE | `/modules/{id}` | 删除模组 |

### 角色 `/characters`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/characters` | 获取所有角色 |
| GET | `/characters/options` | 获取创建选项（种族/职业/技能/种族加成/法术列表/施法职业元数据） |
| POST | `/characters` | 创建玩家角色（含法术选择/多职业/技能验证） |
| POST | `/characters/generate-party` | AI生成队友（调用WF2） |
| GET | `/characters/{id}` | 获取角色详情 |
| PATCH | `/characters/{id}/hp` | 更新HP |
| PATCH | `/characters/{id}/prepared-spells` | 更新准备法术（法师/牧师/德鲁伊长休后） |

### 游戏会话 `/game`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/game/sessions` | 创建游戏会话（开始冒险） |
| GET | `/game/sessions` | 获取所有存档 |
| GET | `/game/sessions/{id}` | 获取会话完整状态 |
| POST | `/game/action` | 玩家行动 → ContextBuilder → Chatflow DM → StateApplicator |
| POST | `/game/skill-check` | 执行技能检定（本地骰子） |
| POST | `/game/sessions/{id}/journal` | 生成战役日志（调用WF3旧版） |
| POST | `/game/sessions/{id}/checkpoint` | 将当前会话压缩为结构化 Campaign State JSON |
| GET | `/game/sessions/{id}/checkpoint` | 获取当前战役档案 |
| POST | `/game/sessions/{id}/rest` | 长休/短休（`?rest_type=long\|short`） |

### 战斗 `/game/combat`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/game/combat/{session_id}` | 获取当前战斗状态 |
| POST | `/game/combat/{session_id}/action` | 玩家战斗行动（攻击/防御/冲刺/脱离/协助） |
| POST | `/game/combat/{session_id}/end-turn` | 明确结束当前实体回合（条件计时/回合推进/下一实体重置） |
| POST | `/game/combat/{session_id}/ai-turn` | 触发AI回合（队友+敌人） |
| POST | `/game/combat/{session_id}/spell` | 施法（验证法术位/消耗/效果/AoE多目标） |
| POST | `/game/combat/{session_id}/move` | 移动（Chebyshev距离/分段移动力追踪） |
| POST | `/game/combat/{session_id}/end` | 结束战斗 |
| POST | `/game/combat/{session_id}/condition/add` | 向实体添加状态条件（含可选持续回合数） |
| POST | `/game/combat/{session_id}/condition/remove` | 从实体移除状态条件 |
| POST | `/game/combat/{session_id}/death-save` | 濒死豁免检定（自然20复活/3成功稳定/3失败阵亡） |
| GET | `/game/spells` | 获取全部法术列表 |
| GET | `/game/spells/class/{class_name}` | 获取职业可用法术 |

---

## 6. LangGraph AI 编排（Phase 11 替换 Dify）

### 核心原则

> **本地负责数学，AI 负责创意**
>
> - 本地引擎：所有骰子、HP、命中判断、规则计算（`dnd_rules.py` / `combat_service.py`）
> - LangGraph AI：叙事、生成、角色决策、内容创作（3 个 StateGraph）
> - StateApplicator：将 AI 输出的 `state_delta` 安全地应用到本地数据库

### 统一接口 — LangGraphClient (`services/langgraph_client.py`)

与旧 `DifyClient` 方法签名完全一致，API 路由仅改 import：
- `parse_module(module_text) → (dict, list)` — 调用 module_parser graph
- `generate_party(...) → list[dict]` — 调用 party_generator graph
- `call_dm_agent(...) → dict` — 调用 dm_agent graph
- `generate_campaign_state(...) → dict` — 直接 LLM 调用

### LLM 工厂 (`services/llm.py`)

`get_llm(temperature, max_tokens) → ChatOpenAI`，统一管理模型配置，所有 Graph 共用。

### Graph 1 — 模组解析器 (`services/graphs/module_parser.py`)

```
START → extract_structured_data(LLM,t=0.2) → validate_and_fill(Python) → generate_rag_chunks(LLM,t=0.3) → validate_rag_chunks(Python) → END
```

- **Node 1**：LLM 提取结构化 JSON（怪物完整 stat block），提示词迁移自 `01_module_parser.yml`
- **Node 2**：Python 验证+补全（`fill_monster_defaults()`、钳制数值范围、计算能力调整值）
- **Node 3**：LLM 生成 RAG chunks（max 20，scene/npc/monsters/setting/magic_item）
- **Node 4**：Python 验证 chunk 结构，补全默认值
- **JSON 修复**：`_try_parse_json()` + `_fix_unescaped_quotes()` 状态机处理 LLM 输出中的未转义引号
- **返回**：`(module_data_dict, rag_chunks_list)`

### Graph 2 — 队友生成器 (`services/graphs/party_generator.py`)

```
START → analyze_roles(Python) → generate_companions(LLM,t=0.85) → calc_derived_stats(Python) → END
```

- **Node 1**：角色缺口分析（`ROLE_MAP` + `ROLE_FILL`，优先级：healer→tank→arcane_dps→utility）
- **Node 2**：LLM 生成角色数组（name/race/class/personality/ability_scores/catchphrase）
- **Node 3**：计算衍生属性（`HIT_DICE` + `BASE_AC` → hp_max/ac/initiative/attack_bonus）
- **返回**：`list[dict]`

### Graph 3 — DM Agent (`services/graphs/dm_agent.py`)

```
START → pre_roll_dice(Python) → [combat_active?]
                                  ├─ True  → combat_dm(LLM,t=0.72) → parse_validate(Python) → END
                                  └─ False → explore_dm(LLM,t=0.82) → parse_validate(Python) → END
```

- **pre_roll_dice**：预掷骰子池（d20[16], d4-d12, adv/dis, d100, hit_dice）
- **combat_dm**：完整 5e 战斗规则裁定（命中/暴击/条件/专注/濒死/AI行动原则）
- **explore_dm**：叙事推进 + 技能检定声明 + 战斗触发判定 + 队友反应
- **parse_validate**：JSON 解析 + 降级 fallback + 追加到 messages 列表
- **SqliteSaver**：`AsyncSqliteSaver`，`thread_id = session.id`，messages 窗口 20 条
- **Campaign State**：简单 LLM 调用（不用 Graph），`_merge_campaign_states()` 增量合并

### RAG 层 — ChromaDB

- **上传** (`services/local_rag_uploader.py`)：`collection.upsert()`，metadata=`{module_id, chunk_id, source_type}`
- **检索** (`services/local_rag_service.py`)：`collection.query(where={"module_id": ...})`，按模组隔离
- **删除**：模组删除时 `collection.delete(where={"module_id": ...})`
- **Embedding**：ChromaDB 默认 all-MiniLM-L6-v2，可切换 OpenAI embeddings

### Dify Workflow 文件（已废弃，保留参考）

`dify_workflows/` 目录下的 YAML 文件不再被代码引用，仅作为提示词和逻辑迁移的参考源：
- `01_module_parser.yml` → `services/graphs/module_parser.py`
- `02_party_generator.yml` → `services/graphs/party_generator.py`
- `03_dm_agent.yml` + `03_game_master_chatflow.yml` → `services/graphs/dm_agent.py`
- `04_combat_narrator.yml` → 已废弃（叙事由 DM Agent 内联生成）

---

## 7. 5e 规则引擎

### `services/dnd_rules.py` — 核心规则引擎

#### 数据表（本地 SRD 数据）

```python
# 法术位表（三种施法者类型）
SPELL_SLOTS_FULL     # 全施法者（法师/术士/吟游/德鲁伊/牧师等）1-20级，9环
SPELL_SLOTS_HALF     # 半施法者（圣武士/游侠）1-20级
SPELL_SLOTS_WARLOCK  # 魔契者（特殊契约魔法机制）1-20级

# 职业到施法类型映射
CASTER_TYPE = {"Wizard":"full", "Paladin":"half", "Warlock":"pact", "Fighter":None, ...}

# 种族能力值加成（SRD 5.1 CC-BY-4.0）
RACIAL_ABILITY_BONUSES = {
    "Human":    {str:1, dex:1, con:1, int:1, wis:1, cha:1},
    "Elf":      {dex:2, int:1},
    "Dwarf":    {con:2},
    "Halfling": {dex:2},
    "Half-Elf": {cha:2, dex:1, wis:1},
    "Half-Orc": {str:2, con:1},
    "Dragonborn": {str:2, cha:1},
    "Tiefling": {int:1, cha:2},
    # 同名中文版本也收录
}

# 职业豁免熟练
CLASS_SAVE_PROFICIENCIES = {
    "Fighter": ["str","con"],
    "Wizard":  ["int","wis"],
    "Cleric":  ["wis","cha"],
    # ... 12个职业全覆盖
}

# 职业技能选择（数量+可选列表）
CLASS_SKILL_CHOICES = {
    "Barbarian": {"count":2, "options":["运动","驯兽","恐吓","自然","感知","求生"]},
    "Rogue":     {"count":4, "options":[...11项]},
    "Bard":      {"count":3, "options": ALL_SKILLS},
    # ... 12个职业
}

# 各施法职业1级时的起始已知法术数（不含戏法）
STARTING_SPELLS_COUNT = {
    "Wizard":6, "Cleric":4, "Druid":4,
    "Sorcerer":2, "Bard":4, "Warlock":2,
    "Paladin":0, "Ranger":0, "Fighter":0, "Barbarian":0, "Rogue":0, "Monk":0,
}

# 有施法能力的职业（前端法术选择步骤触发条件）
SPELLCASTER_CLASSES = ["Wizard","Cleric","Druid","Sorcerer","Bard","Warlock"]
```

#### 主要函数

```python
apply_racial_bonuses(ability_scores, race) -> dict
    # 将种族加成叠加到基础属性值

get_spell_slots(char_class, level) -> dict
    # 返回该职业该等级的法术位 {"1st":2, "2nd":1, ...}
    # 魔契者特殊处理：{"slots":2, "slot_level":"2nd"}

roll_dice(expression) -> dict
    # 解析 "2d6+3" 等表达式，返回 {total, dice, modifier, rolls}

roll_skill_check(character, skill, dc, advantage, disadvantage) -> dict
    # 正确检查 proficient_skills，熟练时加 proficiency_bonus
    # 返回 {d20, modifier, total, success, proficient}

roll_attack(attacker, target, is_ranged, advantage, disadvantage) -> dict
    # 返回 {d20, attack_total, target_ac, hit, is_crit, is_fumble}

roll_saving_throw(character, ability, dc) -> dict
    # 检查 proficient_saves，返回 {d20, modifier, total, success, proficient}

roll_advantage() -> int    # 掷2d20取高
roll_disadvantage() -> int # 掷2d20取低
roll_initiative(combatants) -> list[TurnEntry]  # 按先攻排序
calc_derived(ability_scores, level, char_class) -> dict  # 计算全部衍生属性
```

### `services/combat_service.py` — 战斗服务

```python
CombatService（全静态方法）:
  resolve_melee_attack(attacker_derived, target_derived, adv, dis) -> AttackResult
  apply_damage(current_hp, damage, max_hp) -> int
  apply_heal(current_hp, heal, max_hp) -> int
  check_combat_over(enemies, player_hp) -> (bool, "victory"|"defeat"|None)
  get_attack_modifiers(conditions) -> (adv: bool, dis: bool)
  get_defense_modifiers(conditions) -> (adv: bool, dis: bool)
  choose_ai_target(actor_is_enemy, player, allies, enemies_alive) -> dict|None
  check_concentration(character_dict, damage) -> Optional[dict]
    # DC=max(10, damage//2)，CON豁免；返回 {required, dc, spell_name, broke, roll_result}
```

条件效果（5e SRD）：

| 条件 | 效果 |
|------|------|
| poisoned/frightened/prone/blinded/restrained | 攻击时劣势 |
| invisible/hidden | 攻击时优势 |
| paralyzed/petrified/stunned/unconscious/prone | 对其攻击时优势 |

### `services/spell_service.py` — 法术服务

```python
# 从 data/spells_srd.json 加载（99+ 法术，0-7环，支持 // 注释语法）
SPELL_REGISTRY: dict

SpellService（单例 spell_service）:
  get_all() -> list
  get(name) -> dict
  get_for_class(class_name) -> list       # 过滤职业可用法术
  get_cantrips_for_class(class_name) -> list
  calc_upcast_dice(spell, cast_level) -> str   # 计算升环骰型
  resolve_damage(spell, caster_derived, cast_level) -> dict
  resolve_heal(spell, cast_level) -> dict
  consume_slot(char_spell_slots, slot_level) -> dict  # 消耗法术位
  validate_slot_level(spell, cast_level) -> None      # 不足则 raise HTTPException
```

### `services/context_builder.py` — 上下文构建器（Phase 7 新增）

```python
ContextBuilder(session, characters, module, rag_service=RagService()):
  build(player_action: str) -> dict
    # 返回 DM Chatflow 所需完整输入：
    # {player_action, game_state, module_context, campaign_memory, retrieved_context}

  _build_game_state() -> str     # 当前游戏状态 JSON 快照（角色HP/法术位/位置/敌人状态）
  _build_module_context() -> str # 模组背景摘要（setting/plot_summary/current_scene）
  _build_campaign_memory() -> str # 长期记忆（来自 session.campaign_state checkpoint）
  _build_retrieved_context() -> str # RAG 语义检索（stub 返回空串，待激活）
```

### `services/state_applicator.py` — 状态应用器（Phase 7 新增）

```python
@dataclass
ApplyResult:
  narrative: str          # DM 叙事文本
  action_type: str        # exploration / combat / rest / ...
  companion_reactions: list[dict]
  combat_triggered: bool
  combat_ended: bool
  state_delta: dict       # 原始 state_delta（前端可用）

StateApplicator(session, characters, combat_state=None):
  apply(dm_output: dict) -> ApplyResult
    # 解析 state_delta，应用到 DB：
    # - 角色 HP / 条件 / 法术位 / 濒死豁免变更
    # - 敌人状态变更
    # - 写入 GameLog
    # - 信号战斗触发/结束事件
```

### `services/rag_service.py` — RAG 服务（Phase 9 完整激活）

```python
# 抽象接口
BaseRagService:
  retrieve_module_context(query, module_id, top_k) -> str
  retrieve_history_context(query, session_id, top_k) -> str
  retrieve(query, module_id, session_id) -> str   # 统一入口（合并两路检索）

# 存根（KB 未配置时自动使用）
RagService(BaseRagService)  # 所有方法返回空串

# 当前激活（.env 中填入 KB 配置后自动生效）
DifyRagService(BaseRagService)
  # 使用 Dify Cloud /datasets/{id}/retrieve API（hybrid_search）
  # Python 侧按 chunk 内容第一行「模组ID: {module_id}」过滤，实现 per-module 隔离
  # 无需 metadata_filter，兼容所有 Dify 版本

# 工厂函数（ContextBuilder 默认使用）
get_rag_service() -> BaseRagService
  # DIFY_KNOWLEDGE_API_KEY + DIFY_MODULE_DATASET_ID 均非空 → DifyRagService
  # 否则 → RagService（存根）
```

### `services/dify_rag_uploader.py` — RAG 上传器（Phase 9 新增）

```python
DifyRagUploader:
  upload_module_chunks(module_id, chunks) -> int   # 上传 WF1 生成的 rag_chunks 到 Dify KB
  delete_module_chunks(module_id)                  # 模组删除时清理 KB 文档（前缀过滤）

# chunk 上传格式（content 第一行固定为「模组ID: {module_id}」）：
# 模组ID: abc123
# 类型: scene
# 内容: ...
# 摘要: ...
# 标签: 村庄, 入口
# 相关实体: 银谷村, 村长
# 常见问题:
# - 这个场景里有什么？
```

### `schemas/game_schemas.py` — JSON字段类型

```python
AbilityModifiers   # str/dex/con/int/wis/cha: int = 0
SavingThrows       # 同上
DerivedStats       # 完整衍生属性（hp_max, ac, initiative, spell_slots_max...）
EnemyDerived       # 敌人简化衍生属性
EnemyState         # 战斗中的敌人状态（含position）
GameState          # session.game_state 完整结构
EntityPosition     # {x, y}
TurnEntry          # 先攻顺序条目
CombatEntitySnapshot  # 发送给前端的实体快照
```

所有 Schema 均使用 `Config.extra = "allow"` 以保持前向兼容。

---

## 8. 前端架构

### UI 设计风格 — 桌游奇幻主题（Tavern Fantasy）

**设计理念**：模拟 D&D 桌游的实体感 — 木纹桌面、羊皮纸气泡、金色装饰、圆桌角色环。

**核心视觉元素**：
- **背景**：深棕木纹纹理（CSS repeating-linear-gradient 模拟木板接缝）+ 顶部金色光晕
- **面板**：木质渐变背景（#2e1f0e→rgba(46,31,14,0.8)）+ 顶部金色描边
- **对话气泡**：DM 用羊皮纸色（#d4b87a 渐变 + clip-path 撕边）、玩家蓝色、队友绿色
- **角色头像**：圆形 portrait 带职业色边框（蓝=玩家、绿=队友、金=DM、红=敌人）
- **按钮**：木质渐变 + 悬浮时金色边框发光 + translateY 微动
- **输入栏**：卷轴造型（圆角30px 木色渐变背景 + 圆形金色发送按钮）
- **骰子**：CSS 3D Transform 正二十面体（探索金色/战斗钢铁 双材质）
- **战斗地图**：深棕格子 + 蓝/绿/红单元格高亮（玩家/队友/敌人）

**色彩系统**（CSS 变量）：
```css
--bg: #1a120b          /* 深棕主背景 */
--wood: #2e1f0e        /* 木板色 */
--wood-light: #4a3520  /* 木框边线 */
--parchment: #e8d5a8   /* 羊皮纸文字 */
--gold: #c9a84c        /* 金色强调 */
--red: #8b2020 / --red-light: #c44040    /* 敌人/危险 */
--green: #2a5a2a / --green-light: #4a8a4a /* 队友/成功 */
--blue: #1a3a5a / --blue-light: #3a7aaa   /* 玩家/信息 */
```

### 页面流程

```
Home.jsx
  ├── 模组上传/选择（木纹卡片 + 金色标签）
  ├── 存档列表（继续游戏）
  └── → CharacterCreate.jsx
         ├── Step 1: 基础信息（种族/职业/背景 + 战斗风格选择 + 语言）
         ├── Step 2: 能力值（Point Buy / 标准数组，六维卡片网格）
         ├── Step 3: 技能熟练（按职业限制选择）
         ├── Step 4: 装备选择（起始装备方案 + 背景特性预览）
         ├── Step 5: 法术选择（仅施法职业，区分法术书/准备/已知）
         ├── Step 6: 专长/ASI（仅 Lv4+）
         └── Step N: 确认队伍（生成AI队友）
                     └── → Adventure.jsx（酒馆圆桌布局）
                               ├── 角色头像环（顶部）
                               ├── 对话气泡区（DM羊皮纸 / 玩家蓝 / 队友绿）
                               ├── 骰子徽章（居中）
                               ├── 卷轴输入栏（底部）
                               ├── 技能快捷按钮
                               └── 战斗触发 → Combat.jsx
                                              ├── 三栏布局：先攻面板 | 战斗地图 | 行动面板
                                              ├── 网格地图（20x20，木色格子）
                                              ├── 行动配额追踪（配额点+颜色指示）
                                              ├── 行动按钮组（攻击红/法术紫/移动蓝/结束金）
                                              ├── 3D 骰子动画覆盖层
                                              └── 战斗日志
```

### 全局状态 (Zustand `gameStore.js`)

```javascript
selectedModule     // 当前选中模组
playerCharacter    // 玩家角色数据
companions         // AI队友数组
sessionId          // 当前会话ID
logs               // 游戏日志数组
combatActive       // 是否处于战斗
combatState        // 战斗完整状态（含 turn_states）
isLoading          // AI响应加载中
diceRoll           // 骰子动画状态 {faces, result, label}
```

### API 客户端 (`api/client.js`)

所有请求通过 `gameApi` 对象统一管理，Vite 代理 `/api` → `http://localhost:8000`。

新增方法：
```javascript
prepareSpells(charId, preparedSpells)   // PATCH /characters/{id}/prepared-spells
castSpell(sessionId, casterId, spellName, spellLevel, targetIds)
addCondition(sessionId, entityId, condition, isEnemy, duration)
removeCondition(sessionId, entityId, condition, isEnemy)
deathSave(sessionId, characterId)
endTurn(sessionId)
```

---

## 9. 开发阶段与当前进度

### Phase 1 ✅ 完成
- 项目骨架搭建（FastAPI + React + SQLite）
- 模组上传解析（Dify WF1）
- 基础角色创建
- 存档管理

### Phase 2 ✅ 完成
- 主跑团循环（玩家行动 → DM 响应，Dify WF3）
- AI 队友生成（Dify WF2）
- 基础战斗系统（网格地图、先攻、攻击/闪避）
- 战斗叙事（Dify WF4）
- 3D 骰子动画组件（CSS 3D Transform 正二十面体）
- 战役日志生成

### Phase 3 ✅ 完成（架构重构）

**Fix 1 — 5e 规则完善性修复**
- `dnd_rules.py` 完整重写：种族加成、三类法术位表（全/半/魔契）、职业豁免、职业技能选择
- `character.py` 新增字段：`known_spells`, `prepared_spells`, `cantrips`, `concentration`, `proficient_skills`, `proficient_saves`
- `characters.py` 修复：角色创建时正确应用种族加成，验证技能选择，设置豁免熟练
- `CharacterCreate.jsx` 重写：4步向导，技能熟练选择步骤，实时种族加成预览
- 修复 `roll_skill_check()` bug：原实现将所有角色视为所有技能都熟练

**Fix 2 — 代码拆分（game.py 从 850行 → 200行）**
- 新建 `api/deps.py`：跨路由共享的依赖函数
- 新建 `services/combat_service.py`：CombatService（战斗计算）
- 新建 `services/spell_service.py`：SpellService + SPELL_REGISTRY
- 新建 `api/combat.py`：所有战斗端点独立路由
- `main.py` 注册 `combat_router`

**Fix 3 — Pydantic 内部类型**
- 新建 `schemas/game_schemas.py`：所有非结构化 JSON 字段的类型定义
- 新建 `schemas/__init__.py`：统一导出

### Phase 4 ✅ 完成（战斗精炼 + 记忆系统）

**Campaign State 记忆系统**
- `Session.campaign_state` 字段：结构化跨 session 记忆
- `POST /sessions/{id}/checkpoint`：AI 提炼日志 → 结构化档案（增量合并）
- `DifyClient.generate_campaign_state()` + `_merge_campaign_states()`

**战斗系统精炼**
- 专注中断检定：受伤后 DC=max(10, 伤害/2) CON 豁免
- AoE 法术多目标：`target_ids` 字段，每目标独立豁免，成功减半伤害
- 法术注册表标记：`"aoe": True, "half_on_save": True`
- 长休/短休端点：HP/法术位恢复，生命骰掷骰，魔契者短休复槽

### Phase 5 ✅ 完成（法术创角 + 完整战斗状态机）

**施法职业角色创建**
- `dnd_rules.py` 新增 `STARTING_SPELLS_COUNT` 和 `SPELLCASTER_CLASSES`
- `CharacterCreate.jsx` 升级为动态步骤数：施法职业5步（新增「法术选择」Step 4）
- 法术选择界面：蓝色戏法格子 + 紫色已知法术格子

**濒死豁免系统**
- `Character.death_saves` 字段：`{successes, failures, stable}`
- `POST /combat/{id}/death-save`：自然20=立即复活1HP，自然1=2次失败，3成功=稳定，3失败=阵亡

**状态条件管理端点**
- `POST /combat/{id}/condition/add`
- `POST /combat/{id}/condition/remove`

### Phase 6 ✅ 完成（Chatflow DM + SRD法术 + 行动配额）

**WF3 迁移至 Chatflow**
- `dify_workflows/03_game_master_chatflow.yml`：advanced-chat 模式，原生 conversation_id 记忆
- `Session.dify_conversation_id`：持久化 Chatflow 对话 ID
- `DifyClient.call_dm_agent()`：改用 `/chat-messages` API

**SRD 法术 JSON 扩展**
- `backend/data/spells_srd.json`：99 个法术，0-7 环，含 `// 注释`

**战斗行动配额系统（Tier 1 全部实现）**
- `CombatState.turn_states`：行动/移动/奖励行动/反应追踪
- `POST /combat/{id}/end-turn`：明确结束回合，条件倒计时 + 推进 + 重置
- `/action`、`/spell` 不再自动推进回合
- `/move` 改用 Chebyshev 距离 + 分段移动力追踪
- 新行动：冲刺（移动力x2）、脱离接战（disengaged标志）、协助（被协助者攻击优势）
- 远程攻击劣势：相邻敌人（Chebyshev≤1）自动附加劣势
- 前端：行动配额显示、新按钮组、协助选友模式、「结束回合」按钮

### Phase 7 ✅ 完成（行动管线重构 + 多职业 + RAG 框架）

**ContextBuilder + StateApplicator 架构**
- `services/context_builder.py`：将 Session/Character/Combat ORM 对象序列化为 Chatflow 输入（含 RAG 接口）
- `services/state_applicator.py`：解析 `state_delta` JSON，将所有状态变更安全写入数据库
- `/game/action` 端点重构：旧版手动状态更新替换为 ContextBuilder→Chatflow→StateApplicator 管线
- `ApplyResult` dataclass：统一行动结果数据结构

**RAG 服务框架**
- `services/rag_service.py`：`BaseRagService` 抽象接口 + `RagService` 存根（当前激活）+ `DifyRagService` 完整实现模板（待激活）
- 激活方式：在 `main.py` 中将 `RagService()` 替换为 `DifyRagService()`，无需其他代码改动

**多职业支持**
- `Character.multiclass_info` 字段：`{"char_class":"Fighter","level":2}`
- `Character.subclass` 字段：子职业名称（圣武士誓约/牧师领域/法师流派等）
- `migrate_multiclass.py`：数据库迁移脚本

**AI 队友扩展字段**
- `Character.speech_style`、`combat_preference`、`catchphrase`：更丰富的队友个性描述
- `Character.condition_durations`：条件计时器（回合级别），`migrate_condition_durations.py` 迁移

**WF3 All-in-One 设计**
- `dify_workflows/03_dm_agent.yml`：合并探索+战斗的高级工作流（已设计，未集成）

### Phase 8 ✅ 完成（规则精炼 + 子职业接入）

**ai-turn 条件计时修复**
- `api/combat.py` — `ai_combat_turn()` 中的 `_tick_conditions` 调用从回合开始前移至行动后（回合结束时）
- 与 `end_turn` 的 tick 时机统一（5e 规则：条件在实体自己的回合结束时倒计时）
- `e` / `achar` 实体引用在函数内保持作用域，供回合结束段复用

**生命域牧师 Disciple of Life 接入**
- `services/spell_service.py` — `resolve_heal()` 新增 `bonus_healing: bool = False` 参数
- 当 `bonus_healing=True` 且法术位 ≥1 环时，自动附加 `2 + slot_level` 额外治疗量
- `api/combat.py` — `cast_spell` 端点从 `caster.derived["bonus_healing"]` 提取并传递到两处 `resolve_heal` 调用（AoE + 单目标）
- 返回的 `dice_detail` 中新增 `life_bonus` 字段供前端展示

### Phase 9 ✅ 完成（RAG 管线全链路上线）

**WF1 合并 chunk 增强（v0.3 → v0.4）**
- `dify_workflows/01_module_parser.yml`：新增 `node-llm-chunk-enricher`（生成 RAG chunks）+ `node-code-rag-chunks`（验证格式）
- WF1 现在同时输出 `module_data`（结构化，原有）和 `rag_chunks`（JSON数组，新增）
- 每个 chunk 含：`chunk_id / source_type / content / summary / tags / entities / searchable_questions`
- 最多生成 20 个 chunks（scene/npc/monsters_overview/magic_item/setting 各一个）

**WF3 Chatflow 优化**
- 新增 `retrieved_context` 输入变量（Start 节点第 4 个变量），RAG 检索结果注入 DM 上下文
- 新增 `node-code-json-guard`：清理 LLM 输出的 Markdown 包裹，JSON 解析失败时返回降级响应
- 记忆窗口 20 → **10**（减少 token 消耗），temperature 0.8 → **0.7**
- `initial_enemies` 示例格式升级（含 tactics/actions/ability_scores）

**RAG 服务激活**
- `services/rag_service.py`：`DifyRagService` 完整实现（Python 侧 module_id 前缀过滤），新增 `get_rag_service()` 工厂
- `services/dify_rag_uploader.py`（新文件）：`DifyRagUploader` 负责上传/删除 Dify KB 文档
- `services/context_builder.py`：默认 RAG 服务改用 `get_rag_service()`（自动激活）
- `api/modules.py`：解析完成后自动调用 `rag_uploader.upload_module_chunks`；删除模组时调用 `delete_module_chunks`
- `services/dify_client.py`：`parse_module` 返回 `(dict, list)` 兼容新 WF1 输出；`call_dm_agent` 现在真正传入 `retrieved_context`
- `config.py`：新增 `dify_kb_base_url`（默认 `https://api.dify.ai/v1`）
- `.env` / `.env.example`：填入 KB API Key 和 Dataset ID

### Phase 10 ✅ 完成（借机攻击 + 双武器战斗）

**借机攻击（Opportunity Attack，5e PHB p.195）**
- `api/combat.py` 新增辅助函数 `_chebyshev()` 和 `_resolve_opportunity_attacks()`
- `/move` 端点：移动前自动检测——若移动实体未脱离接战（`disengaged=False`），且从某威胁者的临近格（Chebyshev≤1）移入非临近格，则该威胁者消耗 reaction 发起借机攻击
- 触发方向双向支持：玩家/队友移动时相邻敌人发动；敌人移动时玩家及队友发动
- 借机攻击结果写入 GameLog，并在 `/move` 响应中返回 `opportunity_attacks` 列表
- 借机攻击不阻止移动（5e 规则：受到借机攻击后仍可继续移动）

**双武器战斗（Two-Weapon Fighting，5e PHB p.195）**
- `services/combat_service.py`：`resolve_melee_attack()` 新增 `is_offhand: bool = False` 参数
  - `is_offhand=True` 时伤害不加属性修正（STR/DEX 调整值）
  - 攻击者有 `derived["two_weapon_fighting"]=True`（双武器战斗特技）时恢复完整修正
- `api/combat.py`：`CombatActionRequest` 新增 `is_offhand: bool = False` 字段
- `/action` 端点新增副手攻击分支（`is_offhand=True` 或 action_text 含「副手」）：
  - 前提：本回合已使用主手攻击（`action_used=True`）
  - 消耗：附赠行动（`bonus_action_used=True`）
  - 返回 `action: "offhand_attack"`，骰子结果含 `"offhand": true` 标记

### Phase 11 ✅ 完成（Dify → LangGraph 全面迁移）

**AI 编排层迁移（去 Dify 依赖）**
- 新增 `services/llm.py`：LLM 工厂函数 `get_llm()`，统一管理 AiHubMix API 配置
- 新增 `services/graphs/module_parser.py`：WF1 图，4节点线性链（2 LLM + 2 Python 验证）
- 新增 `services/graphs/party_generator.py`：WF2 图，3节点线性链（角色分析 + LLM + 衍生属性）
- 新增 `services/graphs/dm_agent.py`：WF3 图，条件分支（骰子预掷 → 战斗/探索 LLM → 解析验证）+ SqliteSaver + Campaign State
- 新增 `services/langgraph_client.py`：`LangGraphClient`，与 `DifyClient` 接口签名完全一致

**本地 RAG 层（去 Dify KB 依赖）**
- 新增 `services/local_rag_service.py`：`LocalRagService`（ChromaDB 检索，实现 BaseRagService）
- 新增 `services/local_rag_uploader.py`：`LocalRagUploader`（ChromaDB 上传/删除）
- `services/rag_service.py`：`get_rag_service()` 工厂改为返回 `LocalRagService`

**配置迁移**
- `config.py`：删除所有 `dify_*` 字段，新增 `llm_api_key/base_url/model` + `chromadb_path` + `langgraph_db_path`
- `.env` / `.env.example`：AiHubMix API Key + `claude-sonnet-4-6`
- `requirements.txt`：新增 langgraph / langgraph-checkpoint-sqlite / langchain-openai / langchain-core / chromadb

**API 路由适配（最小改动）**
- `api/modules.py`：import 改为 `langgraph_client` + `local_rag_uploader`（2行）
- `api/characters.py`：import 改为 `langgraph_client`（1行）
- `api/game.py`：import 改为 `langgraph_client` + `conversation_id` 改用 `session.id`（2行）
- `main.py`：lifespan 中初始化 LangGraph SqliteSaver

**JSON 鲁棒性修复**
- `_try_parse_json()` + `_fix_unescaped_quotes()`：状态机修复 LLM 输出中未转义的中文双引号
- `_strip_code_block()`：添加 `re.MULTILINE` 标志正确去除 Markdown 代码块
- `parse_validate` fallback：正则提取 narrative 字段兜底
- 前端 `extractNarrative()`：兼容处理旧 JSON 格式日志

**3D 骰子动画升级**
- `DiceRollerOverlay.jsx` 从 2D SVG 多边形重写为 CSS 3D Transform 正二十面体
- 使用真实正二十面体 12 顶点 20 三角面几何数据构建
- 支持 d4/d6/d8/d10/d12/d20/d100 七种骰子
- 翻滚动画：`dice3dTumble` keyframes 360° 全向旋转
- 光照模拟：根据面法向量计算亮度，模拟平行光照射
- 双模式视觉：探索模式金色材质 + 金色粒子，战斗模式钢铁材质 + 血滴粒子
- 暴击/大失手特效：绿色/红色发光 + 弹出徽章动画

**已知 Windows 问题**
- `uvicorn --reload` 在 Windows 上有 `[WinError 6]` bug，reload 后产生僵尸进程
- 解决方案：不使用 `--reload` 模式，代码修改后手动重启

---

## 10. 待办与已知问题

### 战斗系统待精炼

| 优先级 | 问题 | 说明 |
|--------|------|------|
| ✅ | 专注中断检定 | 已实现，CON 豁免 DC=max(10, 伤害/2) |
| ✅ | 范围法术多目标 | 已实现，AoE 标记+逐目标豁免+成功减半 |
| ✅ | 状态条件添加/移除 | 已实现，含可选持续回合数 |
| ✅ | 濒死豁免 | 已实现，完整5e规则 |
| ✅ | 行动配额追踪 | 已实现，turn_states 追踪 action/movement/bonus/reaction |
| ✅ | 冲刺/脱离/协助 | 已实现 |
| ✅ | 远程攻击劣势 | 已实现，相邻敌人 Chebyshev≤1 |
| ✅ | 条件持续时间倒计时 | 已实现，在 end-turn 端点 tick |
| ✅ | ai-turn 条件计时时机 | 已修复：tick 移至回合结束（行动后），与 end-turn 逻辑统一 |
| ✅ | 远程攻击使用 DEX 属性 | 已实现：`calc_derived()` 已计算 `ranged_attack_bonus`（prof+DEX），`CombatService.resolve_melee_attack()` 根据 `is_ranged` 自动选择 |
| ✅ | 借机攻击 | 已实现：`_resolve_opportunity_attacks()` 在 `/move` 端点触发，双向检测，消耗 reaction |
| ✅ | 双武器战斗 | 已实现：`/action` 副手攻击分支，消耗附赠行动，`is_offhand` 不加属性修正 |

### 角色创建待完善

| 问题 | 说明 |
|------|------|
| ✅ 法术选择步骤 | 施法职业 CharacterCreate.jsx 已增加法术选择步骤 |
| ✅ 准备法术 UI | `PrepareSpellsModal` 组件已在 Adventure.jsx 完整实现（📖备法按钮 + 弹窗选择） |
| ✅ 子职业机械效果 | `calc_derived()` 已实现：冠军武士暴击阈值(19/18)、生命域治疗加值、狂战士狂暴标记、塑能法师护盾标记；`bonus_healing` 已接入 `spell_service.resolve_heal()` |
| ✅ Point Buy 验证 | `adjustScore()` 已验证范围(8-15)和可用点数，超限时阻止操作 |
| ✅ 多职业前端 | CharacterCreate.jsx 已支持双职业：Step 1 提供多职业切换，验证属性先决条件（`MULTICLASS_REQUIREMENTS`） |

### ✅ LangGraph 迁移已完成（Phase 11）

迁移已在 Phase 11 中完成，详见上方 Phase 11 小节。

### 5e 规则合规性待办（Phase 13 全面审计结果）

#### P0 — 核心规则缺失（影响游戏平衡）

| # | 功能 | 说明 | 涉及文件 |
|---|------|------|----------|
| P0-1 | **Extra Attack** | Lv5+ 战士/圣武士/游侠/野蛮人/武僧每回合 2 次攻击 | combat.py `/action` |
| P0-2 | **Divine Smite** | 圣骑士命中后消耗法术位 +2d8 辐射伤害（+1d8/环级） | combat.py 新端点 |
| P0-3 | **Sneak Attack** | 游荡者有优势或盟友相邻时 +Nd6 伤害（N=等级/2 向上取整） | combat_service.py |
| P0-4 | **Rage（狂暴）** | 野蛮人：+伤害/物理抗性/力量优势，持续1分钟 | combat_service.py |
| P0-5 | **核心职业特性** | Cunning Action(游荡者)/Second Wind(战士)/Action Surge(战士)/Flurry of Blows(武僧) | combat.py |
| P0-6 | **反应系统** | 敌人攻击时玩家选择窗口：Shield法术(+5AC)/Uncanny Dodge(伤害减半)/Hellish Rebuke | combat.py + Combat.jsx |
| P0-7 | **借机攻击前端** | 后端已实现，前端需要：移动时弹出提示 + 反应选择 | Combat.jsx |
| P0-8 | **掩体系统** | 半掩体+2AC / 3/4掩体+5AC / 完全掩体不可瞄准 | combat_service.py |
| P0-9 | **升级系统** | XP/里程碑追踪 → HP增长 → 新法术位 → ASI/专长 | dnd_rules.py + 新端点 |
| P0-10 | **生命骰池** | 短休时消耗生命骰恢复HP（当前无限制） | game.py `/rest` |

#### P1 — 重要平衡功能

| # | 功能 | 说明 |
|---|------|------|
| P1-1 | 战斗风格实战效果 | Archery(+2远程)/Defense(+1AC)/Dueling(+2单手伤害) 在 combat 中实际应用 |
| P1-2 | 专长战斗效果 | GWM/Sharpshooter(-5命中+10伤害)、War Caster(专注优势)、Sentinel(借机停止移动) |
| P1-3 | 伤害类型/抗性/易伤 | 怪物的 resistances/immunities 实际减半/免疫伤害 |
| P1-4 | 擒抱/推撞行动 | 力量(运动) vs 力量/敏捷的对抗检定 |
| P1-5 | 被动感知+隐匿 | 被动感知 = 10+感知修正+熟练，对抗隐匿检定 |
| P1-6 | 灵巧/重型武器属性 | Finesse允许DEX攻击，Heavy对小型种族劣势 |
| P1-7 | 武器射程/弹药 | 远程武器射程限制 + 弹药消耗追踪 |

#### P2 — 增强深度

| # | 功能 | 说明 |
|---|------|------|
| P2-1 | 金币/经济/商店 | 金币追踪、NPC商人、买卖物品 |
| P2-2 | 疲劳等级 | 6级递进debuff（劣势→速度减半→HP上限减半→...→死亡） |
| P2-3 | 光照/黑暗视觉 | 昏暗光线感知劣势、黑暗视觉种族特性 |
| P2-4 | 弹药追踪 | 箭/弩矢消耗和补充 |
| P2-5 | 魔法物品调谐 | 调谐上限3件、调谐效果激活 |
| P2-6 | 仪式施法 | 标记为仪式的法术可不消耗法术位（+10分钟） |

#### P3 — 可选高级规则

| # | 功能 | 说明 |
|---|------|------|
| P3-1 | 夹击（可选规则） | 两个盟友对角包围敌人时攻击优势 |
| P3-2 | 持久伤势 | 暴击/濒死时可选随机持久效果 |
| P3-3 | 反魔法区域 | 特定区域内法术失效 |

### 已知技术债

| 问题 | 位置 |
|------|------|
| CombatState 未使用 Pydantic Schema 验证 | `api/combat.py` 直接操作 JSON 列 |
| `session_history` 按字符截断可能切断中文 | `api/game.py` |
| 前端 Combat.jsx 和 Adventure.jsx 部分逻辑重复 | 状态同步、日志加载 |
| StateApplicator 收到未知实体ID时仅发出警告 | `services/state_applicator.py` |

---

## 11. 架构决策记录

### ADR-001: 本地规则引擎 vs 纯 AI 驱动

**决策**：骰子/HP/命中等所有数学计算在本地完成，AI 只负责叙事与生成。

**理由**：
- AI 实时参与战斗计算（每次攻击都调用 API）延迟不可接受（2-5s/次）
- AI 会"欺骗"骰子结果（倾向于有戏剧性的结果而非随机）
- 本地计算可离线运行，便于测试

### ADR-002: 怪物数值本地化 vs AI 实时生成

**决策**：怪物 stat block 在模组解析时（WF1）一次性提取并存入 `parsed_content.monsters`，战斗时从此处读取。

**理由**：
- 战斗实时请求 AI 生成怪物数值延迟和不稳定性不可接受
- WF1 已能从模组文本提取怪物信息
- 未来可增强 WF1 输出更完整的 stat block

### ADR-003: 拆分 game.py 的边界

**决策**：以「是否需要骰子数学」为分割线——`game.py` 处理叙事循环，`combat.py` 处理战斗规则。

**理由**：单一职责，便于独立测试和修改。两者通过 `api/deps.py` 共享数据库辅助函数。

### ADR-004: 法术注册表手写 vs SRD JSON 导入

**决策**：已迁移为从 `data/spells_srd.json` 加载，支持 `//` 注释语法。

**理由**：99+ SRD 法术已入库，JSON 格式便于维护和扩展，`SpellService` 接口保持不变。参考：`5e-bits/5e-database`（CC-BY-4.0）。

### ADR-005: Dify → LangGraph 迁移（Phase 11 已完成）

**原决策**：所有 AI 功能通过 Dify Workflow / Chatflow 接入。

**废弃原因**：
- Dify Workflow 存在无法修复的变量传递 bug
- Dify Chatflow 的 Answer 节点变量引用在 API 调用时返回原始模板字符串

**新决策**：迁移至 **LangGraph**（Phase 11 已完成实施）。

**实施结果**：
- 3 个 LangGraph StateGraph 替换所有 Dify Workflow（module_parser / party_generator / dm_agent）
- `LangGraphClient` 与 `DifyClient` 方法签名完全一致，API 路由仅改 import
- `AsyncSqliteSaver` 替换 `dify_conversation_id`，对话记忆更可靠
- ChromaDB 替换 Dify KB，RAG 完全本地化
- AI 调用成功率从 0%（WF1）提升到 100%

### ADR-006: ContextBuilder + StateApplicator 管线

**决策**：将「序列化输入」和「应用输出」分别封装为独立 service，`/game/action` 只负责协调。

**理由**：
- 旧版 `game.py` 在 action 端点内直接构造 prompt 并手动更新状态，耦合度高
- 新架构：ContextBuilder 负责所有状态序列化，StateApplicator 负责所有状态写入，两者可独立测试
- Chatflow 原生记忆大幅简化了 ContextBuilder 的工作（不再需要手动维护 session_history 滚动窗口）

### ADR-007: RAG 服务插件化

**决策**：RAG 服务以 `BaseRagService` 抽象接口注入 `ContextBuilder`，`get_rag_service()` 工厂自动按 config 选择实现。

**理由**：
- `DifyRagService` 现已完整实现，`DIFY_KNOWLEDGE_API_KEY` 和 `DIFY_MODULE_DATASET_ID` 填入后零配置激活
- Python 侧按内容前缀（`模组ID: {id}`）过滤，不依赖 Dify metadata API，兼容所有 Dify 版本
- 存根和真实实现共享接口，测试无需改动

### ADR-008: WF1 合并 chunk 增强（消除 WF5）

**决策**：将 chunk 语义增强（原设计为 WF5）合并到 WF1 的第二个 LLM 节点，一次解析同时产出结构化数据和 RAG chunks。

**理由**：
- WF1 的 LLM 已有完整模组 context，此时做增强质量最高
- 省一次 Workflow API 调用，减少模组上传延迟
- 单文件维护，WF1 输出增加 `rag_chunks` 字段，后端通过返回值类型（tuple）兼容旧 WF1

---

## 12. 启动方式

### 快速启动（Windows）

```bash
# 项目根目录运行
start.bat
```

### 手动启动

**后端**：
```bash
cd backend
# 首次：安装依赖
pip install -r requirements.txt
# 首次或数据库结构变更后：运行迁移脚本
python migrate_multiclass.py
python migrate_turn_states.py
python migrate_dify_conversation_id.py
python migrate_condition_durations.py
# 启动
python -m uvicorn main:app --port 8000
# 注意：Windows 上不要用 --reload（有 WinError 6 僵尸进程 bug）
```

**前端**：
```bash
cd frontend
# 首次：安装依赖
npm install
# 启动
npm run dev
# 访问 http://localhost:3000
```

### 环境配置

复制 `backend/.env.example` 为 `backend/.env`，填入以下内容：

```env
# LLM（OpenAI 兼容 API）
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx          # AiHubMix / OpenRouter / OpenAI API Key
LLM_BASE_URL=https://aihubmix.com/v1    # API 基础 URL
LLM_MODEL=claude-sonnet-4-6              # 模型名称（可切换）

# ChromaDB（本地 RAG 向量库，自动创建）
CHROMADB_PATH=./chromadb_data

# LangGraph 对话记忆（独立 SQLite 文件）
LANGGRAPH_DB_PATH=./langgraph_memory.db
```

### API 文档

后端启动后访问：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- 健康检查: `http://localhost:8000/health`
