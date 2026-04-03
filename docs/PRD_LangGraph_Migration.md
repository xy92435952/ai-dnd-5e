# 【PRD】AI跑团平台 — 产品需求文档 V2.0

---

## 一：基础信息

### 版本信息

- **产品版本：** v14.0（Phase 14 完成）
- **创建时间：** 2026年4月1日
- **最后更新：** 2026年4月3日
- **创建人：** AI跑团平台团队

### 变更日志

| 时间 | 文档版本 | 变更人 | 主要变更内容 |
|------|----------|--------|--------------|
| 2026.4.1 | v1.0 | 团队 | 新建文档，LangGraph 迁移方案完整设计 |
| 2026.4.2 | v2.0 | 团队 | Phase 11 LangGraph 迁移完成 + Phase 12 完整 5e 角色特性实现 + E2E 测试通过 |
| 2026.4.3 | v3.0 | 团队 | Phase 13 完整 5e 战斗系统 + 3D 骰子动画 + UI 全面重构 + SQLAlchemy JSON 持久化修复 |
| 2026.4.3 | v4.0 | 团队 | Phase 14 V2 完整体验：角色面板 + 商店系统 + 装备管理 + 药水使用 + 移动/攻击范围可视化 + 装备伤害 |

### 名词解释

| 术语 / 缩略词 | 说明 |
|---------------|------|
| RAG | 检索增强生成（Retrieval-Augmented Generation） |
| LangGraph | LangChain 生态的有限状态图编排框架，用于构建多步骤 AI Agent |
| DM | 地下城主（Dungeon Master），AI 扮演的游戏主持人角色 |
| 5e | D&D 第五版规则（Dungeons & Dragons 5th Edition） |
| WF1/WF2/WF3 | 原 Dify 平台上的三个 AI Workflow（模组解析/队友生成/DM Agent） |
| Dify | 原 AI 编排平台（即将被替换） |
| ChromaDB | 本地向量数据库，用于 RAG 检索 |
| SqliteSaver | LangGraph 内置的 SQLite 状态持久化器 |
| StateGraph | LangGraph 核心概念，定义节点和边的有向图 |

---

## 二：项目背景

### 需求背景

> AI跑团平台已完成 Phase 1-10 开发，核心玩法（5e 规则引擎 + AI 叙事 + 网格战斗地图）已验证。当前 AI 层依赖 Dify 平台，但 Dify 存在严重的变量传递 bug，导致核心功能阻塞。

| 需求方 | 场景 | 痛点 | 诉求 |
|--------|------|------|------|
| 开发者 | 模组上传解析（WF1） | Dify Workflow 的 Start 节点变量在 LLM 节点 Input 始终为空 `{}`，WF1 完全无法工作，模组解析功能阻塞 | 需要一个可靠的 AI 编排层，彻底解决变量传递问题 |
| 开发者 | DM Agent 对话（WF3） | Dify Chatflow 的 Answer 节点变量引用在 API 调用时返回原始模板字符串而非 LLM 输出，DM 响应不稳定 | 需要可调试、可断点的 AI 编排方案 |
| 开发者 | RAG 知识检索 | 依赖 Dify Cloud Knowledge Base API，增加外部依赖和网络延迟；无法离线运行 | 需要本地化的 RAG 方案，零外部依赖 |
| 玩家（终端用户） | 开始冒险 | 上传模组后无法解析（WF1 阻塞），整个游戏流程无法启动 | 需要稳定可用的模组解析和游戏循环 |

### 项目目标

> 北极星指标：AI 编排层的端到端调用成功率

- **北极星指标：AI 调用成功率 > 99%**（当前 Dify WF1 成功率为 0%）
- **业务指标：** 模组上传 → 解析完成 → 开始游戏的全链路恢复可用
- **技术指标：** 去除所有 Dify 依赖，AI 层完全本地化（LangGraph + ChromaDB）

### 用户画像

**小王** — TRPG 爱好者 / 程序员

热爱桌游但难以凑齐线下团。希望利用碎片时间在浏览器上独自跑团，享受 AI 担任 DM 的沉浸式冒险体验。

**痛点：**
- 上传了精心准备的模组文件，但系统提示"解析失败"，无法开始游戏
- DM 的回复偶尔返回乱码或模板字符串，打断叙事沉浸感
- 多轮对话后 DM 遗忘之前的剧情发展，缺乏连贯性

**期望：**
1. 上传模组后能快速、稳定地完成解析，立即开始冒险
2. DM 的叙事响应始终是结构化、高质量的中文内容
3. AI 能记住之前的对话和剧情发展，保持故事连贯
4. 离线或弱网环境下也能正常游玩

### 原始用户流程图

```
玩家 → 上传模组文件（PDF/DOCX/MD/TXT）
     → [WF1] AI 解析模组 → 提取场景/NPC/怪物/剧情
     → 创建角色（种族/职业/能力值/法术）
     → [WF2] AI 生成队友（互补职业/个性/背景）
     → 创建游戏会话 → 进入冒险
     → 玩家输入行动 → [WF3] DM Agent 响应（叙事+状态变更）
     → 触发战斗 → 网格战斗（本地规则引擎）
     → 战斗结束 → 继续探索
     → [循环]
```

### 竞品分析

| 竞品名称 | 对标功能点 | 借鉴要点总结 |
|----------|------------|--------------|
| AI Dungeon | AI DM 叙事 | **优点：** 纯文本交互，响应速度快，叙事连贯。**借鉴：** 对话记忆窗口管理，确保 AI 不遗忘关键剧情 |
| Dify Workflow | AI 编排 | **问题：** UI 配置黑盒，变量传递不可靠，调试困难。**教训：** AI 编排层必须是代码级可控的，而非 UI 配置 |
| LangGraph 官方示例 | 状态图编排 | **借鉴：** StateGraph + 条件边 + SqliteSaver checkpointer 的成熟模式，适合有限状态机场景 |

---

## 五：功能规划

### 系统架构

> 本次迁移影响的架构层：AI 编排层（Dify → LangGraph）和 RAG 层（Dify KB → ChromaDB）

**架构分层：**

- **用户层：** React 18 前端（不变）
- **API 网关层：** FastAPI 路由（仅改 import，逻辑不变）
- **AI 编排层（本次迁移）：**
  - LangGraph StateGraph：module_parser / party_generator / dm_agent
  - LangGraphClient：统一接口（替换 DifyClient）
  - SqliteSaver：对话记忆持久化
- **RAG 层（本次迁移）：**
  - ChromaDB 本地向量库（替换 Dify KB）
  - LocalRagService / LocalRagUploader
- **规则引擎层：** dnd_rules / combat_service / spell_service（不变）
- **数据层：** SQLite + SQLAlchemy（不变）
- **模型层：** OpenAI 兼容 API（AiHubMix 等）

### 功能清单

| 一级功能 | 二级功能 | 描述 | 优先级 | 状态 |
|----------|----------|------|--------|------|
| 基础设施 | LLM 工厂函数 | 提供统一的 `get_llm(temperature, max_tokens)` 函数，通过 .env 配置 API Key / Base URL / Model | P0 | 待开发 |
| 基础设施 | 配置迁移 | `config.py` 删除所有 `dify_*` 字段，新增 `llm_*` / `chromadb_*` / `langgraph_*` 配置 | P0 | 待开发 |
| WF1 模组解析 | LangGraph 模组解析图 | 4 节点线性链：LLM 提取结构化数据 → Python 验证补全 → LLM 生成 RAG Chunks → Python 验证 Chunks | P0（阻塞） | 待开发 |
| WF1 模组解析 | ChromaDB RAG 上传 | 替换 DifyRagUploader，将 WF1 生成的 chunks 存入本地 ChromaDB | P0 | 待开发 |
| WF3 DM Agent | LangGraph DM Agent 图 | 条件分支图：骰子预掷 → 战斗/探索分流 → LLM 生成 → 解析验证；SqliteSaver 持久化对话记忆 | P0 | 待开发 |
| WF3 DM Agent | Campaign State 生成 | 简单 LLM 调用（无需图），压缩日志为结构化长期记忆 | P1 | 待开发 |
| WF2 队友生成 | LangGraph 队友生成图 | 3 节点线性链：角色缺口分析 → LLM 生成角色 → 计算衍生属性 | P2 | 待开发 |
| RAG 检索 | ChromaDB 本地检索 | 替换 DifyRagService，实现 BaseRagService 接口，metadata 过滤按 module_id 隔离 | P1 | 待开发 |
| 集成 | LangGraphClient | 统一客户端类，与 DifyClient 方法签名完全一致，API 路由仅改 import | P0 | 待开发 |
| 集成 | API 路由适配 | modules.py / characters.py / game.py 的 import 更新 + conversation_id 逻辑调整 | P0 | 待开发 |

---

## 六：功能需求

### 功能一：LangGraph 模组解析器（替换 WF1）

#### 业务流程图

```
用户上传模组文件
  → 后端提取文本（PyMuPDF / python-docx / markdown）
  → 截断文本（按配置限制）
  → [LangGraph Graph] module_parser.ainvoke({"module_text": text})
      ├─ Node 1: extract_structured_data（LLM, t=0.2）
      │   → 从模组文本提取 JSON：场景/NPC/怪物完整 stat block/魔法物品
      ├─ Node 2: validate_and_fill（Python）
      │   → 验证 JSON 结构，补全缺失怪物字段，计算能力调整值，钳制数值范围
      ├─ Node 3: generate_rag_chunks（LLM, t=0.3）
      │   → 生成最多 20 个语义检索 chunks（scene/npc/monsters/magic_item/setting）
      └─ Node 4: validate_rag_chunks（Python）
          → 验证 chunk 结构，补全默认值
  → 返回 (module_data_dict, rag_chunks_list)
  → 更新 Module.parsed_content
  → 上传 chunks 到 ChromaDB
```

#### 详细交互设计

| 模块 | 功能名称 | 详细说明 |
|------|----------|----------|
| 模组解析 | extract_structured_data | **LLM 节点**（temperature=0.2）：系统提示词迁移自 `01_module_parser.yml`，要求以严格 JSON 格式返回完整模组结构，包含怪物完整 stat block（ability_scores, actions, tactics, resistances, immunities）。输出写入 state.llm_extract_output |
| 模组解析 | validate_and_fill | **Python 节点**：迁移自 Dify Code 节点。含 `fill_monster_defaults(m)` 函数：根据 CR 生成默认 ability_scores，生成默认近战攻击 action（含熟练加值计算），补全 type/xp/hp_dice/speed 等字段。钳制 level_min/max 到 [1,20]，party_size 到 [1,6]。输出写入 state.module_data（dict）和 state.module_data_json（JSON string） |
| 模组解析 | generate_rag_chunks | **LLM 节点**（temperature=0.3）：系统提示词迁移自 `01_module_parser.yml` 第二个 LLM 节点。要求生成 JSON 数组，每个 chunk 含 chunk_id/source_type/content/summary/tags/entities/searchable_questions。最多 20 个 chunks |
| 模组解析 | validate_rag_chunks | **Python 节点**：迁移自 Dify Code 节点。验证每个 chunk 是 dict 且含 content 字段，补全默认 chunk_id/source_type/summary/tags/entities/searchable_questions。过滤空 content 的 chunks |

#### 入口函数签名（与 DifyClient 一致）

```python
async def parse_module(self, module_text: str) -> tuple[dict, list]:
    """返回 (module_data_dict, rag_chunks_list)"""
```

---

### 功能二：LangGraph DM Agent（替换 WF3）

#### 业务流程图

```
玩家输入行动
  → ContextBuilder.build(player_action)
      → game_state / module_context / campaign_memory / retrieved_context
  → [LangGraph Graph] dm_agent.ainvoke(state, config={"configurable": {"thread_id": session_id}})
      ├─ Node 1: pre_roll_dice（Python）
      │   → 预掷骰子池：d20[16], adv[6], dis[6], d4-d12, d100, hit_dice[6]
      │   → 从 game_state 判断 combat_active
      ├─ 条件边: route_by_mode
      │   ├─ combat_active=True → Node 2a: combat_dm（LLM, t=0.72）
      │   │   → 完整 5e 战斗规则裁定 + AI 单位行动 + 骰子消耗
      │   └─ combat_active=False → Node 2b: explore_dm（LLM, t=0.82）
      │       → 叙事推进 + 技能检定声明 + 战斗触发判定 + 队友反应
      └─ Node 3: parse_validate（Python）
          → 解析 JSON，验证 state_delta 结构，补全默认值
          → 追加 HumanMessage + AIMessage 到 messages 列表
  → SqliteSaver 自动持久化 state（含 messages 历史）
  → StateApplicator.apply(result)
  → 返回给前端
```

#### 详细交互设计

| 模块 | 功能名称 | 详细说明 |
|------|----------|----------|
| DM Agent | pre_roll_dice | **Python 节点**：迁移自 `03_dm_agent.yml` 骰子预掷逻辑。生成完整骰子池供 LLM 使用（确保真随机）。写入 state.dice_pool 和 state.combat_active |
| DM Agent | combat_dm | **LLM 节点**（temperature=0.72, max_tokens=3000）：系统提示词迁移自 `03_dm_agent.yml` 战斗分支。包含完整 5e 规则（命中判定/暴击/条件效果/专注中断/濒死豁免/AI 单位行为原则）。要求使用提供的骰子池，输出严格 JSON（action_type/narrative/dice_results/state_delta/ai_turns） |
| DM Agent | explore_dm | **LLM 节点**（temperature=0.82, max_tokens=2000）：系统提示词迁移自 `03_dm_agent.yml` 探索分支。包含叙事规则（第二人称/感官细节/150-200字）、技能检定声明规则（DM 只声明不掷骰）、战斗触发条件判定。输出 JSON（action_type/narrative/needs_check/companion_reactions/player_choices/state_delta） |
| DM Agent | parse_validate | **Python 节点**：迁移自 `03_dm_agent.yml` 验证节点。剥离 Markdown 代码块，解析 JSON，补全所有默认值（action_type/narrative/dice_results/state_delta/companion_reactions/ai_turns/player_choices），验证 state_delta 内部结构，确保 hp_change 为整数。解析失败时返回降级响应 |
| DM Agent | SqliteSaver 记忆 | **状态持久化**：使用 AsyncSqliteSaver，独立文件 `langgraph_memory.db`。thread_id = session.id。messages 列表窗口限制 20 条（10轮），与原 Dify Chatflow memory window=10 一致 |
| DM Agent | Campaign State | **简单 LLM 调用**（不用图）：迁移 `_CAMPAIGN_STATE_PROMPT` 和 `_merge_campaign_states()` 到新模块。使用 oneshot thread_id 避免污染游戏会话记忆 |

#### 入口函数签名（与 DifyClient 一致）

```python
async def call_dm_agent(self, player_action: str, game_state: str,
                         module_context: str, campaign_memory: str = "",
                         retrieved_context: str = "",
                         conversation_id: str | None = None) -> dict:
    """返回格式与 DifyClient.call_dm_agent 完全一致"""

async def generate_campaign_state(self, log_text: str,
                                   module_summary: str,
                                   existing_state: dict) -> dict:
    """返回合并后的 campaign_state dict"""
```

---

### 功能三：LangGraph 队友生成器（替换 WF2）

#### 业务流程图

```
玩家创建角色后点击"生成队友"
  → [LangGraph Graph] party_generator.ainvoke(state)
      ├─ Node 1: analyze_roles（Python）
      │   → 角色缺口分析：ROLE_MAP 映射 + 优先级排序（healer→tank→arcane_dps→utility）
      ├─ Node 2: generate_companions（LLM, t=0.85）
      │   → 生成角色数组（name/race/class/subclass/ability_scores/personality/speech_style/combat_preference/backstory/catchphrase）
      └─ Node 3: calc_derived_stats（Python）
          → 计算衍生属性：HIT_DICE + BASE_AC + proficiency_bonus + ability_modifiers → hp_max/ac/initiative/attack_bonus
  → 返回 list[dict] 的队友数组
  → 后端为每个队友创建 Character 记录
```

#### 入口函数签名（与 DifyClient 一致）

```python
async def generate_party(self, player_class: str, player_race: str,
                          player_level: int, party_size: int,
                          module_data: dict) -> list[dict]:
    """返回队友角色数组"""
```

---

### 功能四：ChromaDB 本地 RAG（替换 Dify KB）

#### 详细交互设计

| 模块 | 功能名称 | 详细说明 |
|------|----------|----------|
| RAG 上传 | upload_module_chunks | 将 WF1 生成的 chunks 存入 ChromaDB。Collection: `module_chunks`。Document = 格式化 chunk 文本（复用 `_format_chunk_content()` 函数）。Metadata = `{module_id, chunk_id, source_type}`。Document ID = `{module_id}_{chunk_id}`。使用 `collection.upsert()` |
| RAG 检索 | retrieve_module_context | 实现 BaseRagService 接口。查询：`collection.query(query_texts=[query], where={"module_id": module_id}, n_results=top_k)`。返回拼接的 chunk 文本 |
| RAG 删除 | delete_module_chunks | 模组删除时调用：`collection.delete(where={"module_id": module_id})`。零网络延迟 |
| RAG 嵌入 | Embedding 模型 | 默认 ChromaDB 内置 all-MiniLM-L6-v2。中文质量不足时可切换为 OpenAI 兼容 embeddings（一行配置） |

---

## 提示词设计

### WF1 — 模组结构化提取 Agent

```markdown
# 角色
你是一个专业的DnD 5e模组分析专家。从模组文本中提取关键信息，以严格的JSON格式返回。
怪物数据必须尽可能完整，这些数据将直接用于战斗规则计算。
只返回JSON，不要有任何额外文字或markdown代码块标记。

# 输出 JSON 结构
{
  "name": "模组名称",
  "setting": "世界观背景描述",
  "level_min": 1, "level_max": 5,
  "recommended_party_size": 4,
  "tone": "冒险基调",
  "plot_summary": "主线剧情摘要",
  "scenes": [{"title": "场景名", "description": "场景描述", "encounters": [], "npcs_present": [], "rewards": []}],
  "npcs": [{"name": "NPC名", "role": "关键/次要/商人", "description": "描述", "personality": "性格", "alignment": "阵营", "location": "所在场景", "quest_hook": "任务线索"}],
  "monsters": [{"name": "怪物名", "type": "类型", "cr": 2, "xp": 450, "hp": 30, "hp_dice": "5d8+10", "ac": 14, "ac_source": "天然护甲", "speed": "30ft", "ability_scores": {"str":14,"dex":12,"con":14,"int":6,"wis":10,"cha":6}, "saving_throws": {}, "skills": {}, "resistances": [], "immunities": [], "senses": "黑暗视觉60ft", "languages": "地精语", "special_abilities": [], "actions": [{"name": "弯刀", "type": "近战武器攻击", "to_hit": "+4", "reach": "5ft", "damage": "1d6+2", "damage_type": "挥砍"}], "legendary_actions": [], "typical_count": 3, "tactics": "直接冲向最近目标"}],
  "key_rewards": [],
  "magic_items": []
}
```

### WF1 — RAG Chunk 生成 Agent

```markdown
# 角色
你是专业的RAG知识库工程师，专门处理DnD 5e模组内容。
将结构化模组数据转化为适合语义检索的知识块（chunks）。
只输出JSON数组，不加任何前缀、解释或Markdown代码块。

# 输出格式
[
  {
    "chunk_id": "唯一标识",
    "source_type": "setting|scene|npc|monsters_overview|magic_item",
    "content": "完整内容文本，包含所有关键细节",
    "summary": "2-3句简洁摘要",
    "tags": ["标签1", "标签2"],
    "entities": ["命名实体"],
    "searchable_questions": ["玩家可能提出的问题"]
  }
]

# 规则
- setting + plot_summary → 1个 chunk
- 每个 scene → 1个 chunk
- 每个 NPC → 1个 chunk
- 所有 monsters → 1个 chunk
- 每个 magic_item → 1个 chunk
- 最多20个 chunks
```

### WF2 — 队友生成 Agent

```markdown
# 角色
你是一个DnD 5e角色创建专家，擅长创造有深度、有个性的角色。
你需要根据要求生成AI控制的队友角色。只返回JSON数组，不要有任何额外文字或markdown标记。

# 输出格式
[
  {
    "slot": 1,
    "name": "契合世界观的角色名",
    "race": "标准DnD种族",
    "class": "职业",
    "subclass": "子职业",
    "level": 5,
    "background": "背景（学者/士兵/罪犯等）",
    "alignment": "阵营",
    "personality_traits": "2-3句个性描写，包含具体细节",
    "speech_style": "说话风格（简练/健谈/冷静/幽默）",
    "combat_preference": "战斗偏好（激进/辅助/保护/机会主义）",
    "backstory": "80字以内的背景故事",
    "ability_scores": {"str":14, "dex":12, "con":13, "int":10, "wis":15, "cha":8},
    "catchphrase": "标志性口头禅"
  }
]

# 要求
- 性格各异，避免雷同
- 能力值总和约75-78
- 名字契合世界观设定
```

### WF3 — 战斗 DM Agent

```markdown
# 角色
你是一个精通DnD 5e规则的全能地下城主代理，当前处于战斗回合中。

# 职责
1. 裁定玩家行动结果（命中/伤害/豁免/条件）
2. 控制所有AI单位（队友+敌人）执行回合行动
3. 生成沉浸感的战斗叙事
4. 追踪所有状态变化（HP/条件/资源）

# 5e 战斗规则摘要
- 命中判定：d20 + 攻击加值 ≥ 目标AC → 命中；法术豁免：d20 + 豁免加值 ≥ 施法者DC → 成功
- 暴击（天然20）：伤害骰翻倍；大失败（天然1）：自动未命中
- 俯卧：近战优势，远程劣势
- 中毒/恐惧：攻击和能力检定劣势
- 失明：攻击劣势，攻击者优势
- 束缚：攻击劣势，攻击者优势，速度为0
- 昏迷/麻痹：近战自动暴击
- 专注：DC=max(10,伤害/2)，失败则失去法术
- 濒死豁免：≥10成功，<10失败；天然20立即复活1HP；天然1算2次失败

# 骰子使用规则
- 必须按顺序使用提供的骰子池，不得在LLM中生成随机数
- 每次使用记录到 dice_results

# AI 单位行为原则
- 敌人：优先攻击最低HP或最高威胁的目标，遵循怪物描述中的 tactics
- 队友：遵循其个性和战斗偏好，优先治疗濒死队友

# 输出格式（严格 JSON）
{
  "action_type": "combat_attack|combat_spell|combat_move|combat_special",
  "narrative": "100-150字战斗叙事，第二人称",
  "dice_results": [{"label":"描述","dice_face":20,"raw":15,"modifier":"+5","total":20,"against":"AC 15","outcome":"hit"}],
  "state_delta": {
    "characters": [{"id":"uuid","hp_change":-10,"conditions_add":[],"conditions_remove":[],"spell_slots_used":{},"concentration_set":null,"concentration_clear":false,"death_saves":{}}],
    "enemies": [{"id":"uuid","hp_change":-8,"conditions_add":[],"conditions_remove":[],"dead":false}],
    "combat_end": false, "combat_end_result": null
  },
  "ai_turns": [{"actor_id":"uuid","actor_name":"名字","actor_type":"enemy|ally","action_desc":"描述","dice_results":[...],"narrative":"50-80字","state_delta":{}}]
}
```

### WF3 — 探索 DM Agent

```markdown
# 角色
你是一个精通DnD 5e规则的地下城主，当前处于探索/叙事模式。

# 职责
1. 根据玩家行动推进故事
2. 扮演NPC，保持人格与阵营一致性
3. 声明技能检定（DM只声明，玩家本地掷骰）
4. 判断是否触发战斗
5. 生成AI队友的自然反应

# 技能检定声明规则
- 你的职责是声明"需要进行检定"并给出类型和DC，不是掷骰
- 当玩家行动有成功/失败可能时：needs_check.required = true
- 叙事中描述"你尝试..."，在结果处暂停
- 常见DC：10(简单)、15(中等)、20(困难)、25(极难)
- 纯叙事/对话/移动不需要检定

# 战斗触发条件
- 玩家主动攻击
- 敌人主动开战
- 对话/谈判失败且敌人敌对
- 触发陷阱/遭遇战

# 输出格式（严格 JSON）
{
  "action_type": "roleplay|skill_check|dialogue|movement|investigation|rest|lore",
  "narrative": "150-200字叙事，第二人称，感官细节（视觉/听觉/嗅觉）",
  "needs_check": {"required":false,"check_type":"stealth|perception|persuasion|...","ability":"dex|wis|cha|...","dc":15,"advantage":false,"disadvantage":false,"context":"检定原因"},
  "state_delta": {
    "characters": [{"id":"uuid","hp_change":0,"conditions_add":[],"conditions_remove":[]}],
    "enemies": [],
    "combat_trigger": false, "initial_enemies": [],
    "scene_advance": false, "new_scene_hint": null
  },
  "companion_reactions": "[角色名]: \"台词\"\n[角色名2]: \"台词\"",
  "player_choices": ["建议行动1", "建议行动2", "建议行动3"]
}
```

---

## 七：数据埋点需求

核心用户旅程：**上传模组 → 解析完成 → 创建角色 → 生成队友 → 开始冒险 → 多轮交互**

| 阶段 | 事件名 | 描述 | 关键属性 |
|------|--------|------|----------|
| 模组解析 | module_parse_start | 模组开始解析 | module_id, file_type, text_length |
| 模组解析 | module_parse_success | 解析成功 | module_id, duration_ms, monsters_count, scenes_count, chunks_count |
| 模组解析 | module_parse_fail | 解析失败 | module_id, error_type, error_msg |
| 队友生成 | party_generate_start | 队友生成开始 | session_id, player_class, party_size |
| 队友生成 | party_generate_success | 队友生成成功 | session_id, duration_ms, companions_count |
| DM 交互 | dm_action_start | 玩家发送行动 | session_id, action_type, combat_active |
| DM 交互 | dm_action_success | DM 响应成功 | session_id, duration_ms, response_action_type, json_parse_ok |
| DM 交互 | dm_action_fail | DM 响应失败 | session_id, error_type, fallback_used |
| RAG | rag_retrieve | RAG 检索触发 | module_id, query_length, results_count |

---

## 八：角色权限设计

> 当前为本地 MVP 单人版，暂无多用户权限需求。所有功能对本地用户全部开放。

| 功能集 | 功能点 | 本地用户 |
|--------|--------|----------|
| 模组管理 | 上传 / 解析 / 删除 | 全部开放 |
| 角色创建 | 创建角色 / 生成队友 | 全部开放 |
| 游戏会话 | 开始冒险 / 行动 / 战斗 | 全部开放 |
| 存档管理 | 存档 / 读档 / checkpoint | 全部开放 |

---

## 八（补充）：3D 骰子动画系统

### 功能描述

将原有 2D SVG 骰子动画升级为 **CSS 3D Transform 正二十面体**，带来沉浸式掷骰体验。

### 技术实现

| 特性 | 说明 |
|------|------|
| 3D 几何 | 正二十面体（12 顶点、20 三角面），使用黄金比例 φ=(1+√5)/2 计算顶点坐标 |
| 渲染方式 | CSS `transform-style: preserve-3d` + `perspective: 600px`，纯 CSS 无 WebGL 依赖 |
| 材质系统 | 探索模式：金色渐变（#d4b060→#705818）；战斗模式：钢铁渐变（#2a2a35→#0f0f18） |
| 光照模拟 | 根据每个面的法向量与光源方向的点积计算亮度，模拟平行光 |
| 翻滚动画 | `dice3dTumble` 关键帧：0.6s 周期内绕 X/Y/Z 三轴旋转，14 帧数字滚动后定格 |
| 粒子系统 | 探索模式：8 个金色星形粒子上飘；战斗模式：8 条血滴下落 + 血雾覆盖 |
| 暴击特效 | 自然 20：绿色发光 + "⚡ 大成功！" 弹出徽章；自然 1：红色发光 + "💀 大失败！" |
| 骰子类型 | d4/d6/d8/d10/d12/d20/d100 全支持，面上刻印对应数字 |
| 交互 | 点击任意处关闭覆盖层，3.5s 后自动消失 |

### 文件

- `frontend/src/components/DiceRollerOverlay.jsx` — 完整 3D 骰子组件（~340 行）

---

## 十二：Phase 13 — 完整 5e 战斗系统 + UI 重构

### 13.1 P0 核心战斗功能

| 功能 | 说明 | 涉及文件 | 状态 |
|------|------|----------|------|
| Extra Attack | Lv5+ 战士/圣武士/游侠/野蛮人/武僧每回合 2 次攻击；Lv11 战士 3 次；Lv20 战士 4 次 | combat.py `/action` | 已完成 |
| Divine Smite | 圣骑士命中后消耗法术位 +2d8 辐射伤害（每升 1 环 +1d8），对亡灵/邪魔额外 +1d8 | combat.py 新端点 | 已完成 |
| Sneak Attack | 游荡者有优势或盟友相邻时 +Nd6 伤害（N = ceil(level/2)） | combat_service.py | 已完成 |
| Rage（狂暴） | 野蛮人：+2/+3/+4 近战伤害加值（按等级递增），物理伤害抗性，力量检定/豁免优势，持续 1 分钟（10 回合） | combat_service.py | 已完成 |
| Second Wind | 战士：附赠行动恢复 1d10+等级 HP，每短休恢复 1 次 | combat.py | 已完成 |
| Action Surge | 战士：本回合获得额外行动，每短/长休恢复 1 次 | combat.py | 已完成 |
| Cunning Action | 游荡者：附赠行动冲刺/脱离/躲藏 | combat.py | 已完成 |
| Flurry of Blows | 武僧：消耗 1 气点，附赠行动额外 2 次徒手打击 | combat.py | 已完成 |
| 反应系统 | Shield 法术（+5AC 至下回合）、Uncanny Dodge（伤害减半）、Hellish Rebuke（反击 2d10 火焰） | combat.py + Combat.jsx | 已完成 |
| 借机攻击前端 | 后端 Phase 10 已实现；前端移动时弹出提示 + 反应选择 UI | Combat.jsx | 已完成 |
| 掩体系统 | 半掩体 +2AC / 3/4 掩体 +5AC / 完全掩体不可瞄准；基于攻击者与目标之间的障碍物线段检测 | combat_service.py | 已完成 |
| 升级系统 | XP/里程碑追踪 → HP 增长（生命骰+CON）→ 新法术位 → ASI/专长（Lv4/8/12/16/19） | dnd_rules.py + 新端点 | 已完成 |
| 生命骰池 | 短休时消耗生命骰恢复 HP（每骰 = 职业生命骰 + CON 修正），长休恢复一半生命骰 | game.py `/rest` | 已完成 |
| 濒死豁免 | 自然 20 立即复活 1HP；3 成功稳定；3 失败阵亡；自然 1 算 2 次失败 | combat.py `/death-save` | 已完成 |

### 13.2 P1 重要平衡功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 战斗风格实战效果 | Archery(+2 远程命中)、Defense(+1AC)、Dueling(+2 单手伤害)、GWF(重投 1-2)、Protection(相邻盟友被攻击时反应 -劣势)、TWF(副手加属性修正) | 已完成 |
| 专长战斗效果 | GWM/Sharpshooter(-5 命中 +10 伤害)、War Caster(专注豁免优势)、Sentinel(借机攻击停止移动+速度归零) | 已完成 |
| 伤害类型/抗性/易伤 | 怪物的 resistances（伤害减半）、immunities（伤害免疫）、vulnerabilities（伤害翻倍）实际应用于伤害计算 | 已完成 |
| 擒抱/推撞行动 | 力量(运动) vs 目标力量(运动)或敏捷(体操)的对抗检定；擒抱限制移动，推撞造成俯卧 | 已完成 |
| 被动感知 | 被动感知 = 10 + 感知修正 + 熟练加值（若感知熟练）；用于对抗隐匿检定和察觉隐藏敌人 | 已完成 |

### 13.3 P2 增强深度功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 金币/货币追踪 | Character 新增 gold 字段；NPC 商人交易；战利品拾取；起始金币按职业分配 | 已完成 |
| 疲劳等级 | 6 级递进 debuff：1 级=能力检定劣势、2 级=速度减半、3 级=攻击/豁免劣势、4 级=HP 上限减半、5 级=速度为 0、6 级=死亡 | 已完成 |
| 黑暗视觉 | 矮人/精灵/半精灵/半兽人/提夫林/龙裔自带黑暗视觉 60ft；昏暗光线下感知检定无劣势 | 已完成 |
| 弹药追踪 | 箭/弩矢消耗追踪；战斗结束后可回收一半弹药；Character 新增 ammunition 字段 | 已完成 |

### 13.4 关键 Bug 修复：SQLAlchemy JSON 列持久化

**问题根因**：SQLAlchemy 不会自动检测 JSON 列的 in-place 变更（如 `session.game_state["enemies"][0]["hp"] -= 5`），导致 `db.commit()` 时变更被静默丢弃。

**影响范围**：
- 敌人 HP 变更不持久化（攻击后刷新恢复满血）
- `turn_states` 行动配额重置不生效
- `entity_positions` 移动后位置不保存
- `combat_log` 战斗日志丢失

**修复方案**：在所有 JSON 列 in-place 变更后调用 `flag_modified(obj, "column_name")`，通知 SQLAlchemy 脏标记。

**受影响文件**：
- `api/combat.py` — 所有修改 `combat.turn_states`、`combat.entity_positions`、`combat.combat_log`、`combat.turn_order` 的位置
- `api/game.py` — 所有修改 `session.game_state` 的位置
- `services/state_applicator.py` — state_delta 应用逻辑

### 13.5 3D 骰子动画系统升级

| 特性 | 说明 |
|------|------|
| 引擎 | @3d-dice/dice-box-threejs（Three.js + Cannon-es 物理引擎） |
| 物理模拟 | 真实重力、碰撞检测、骰子翻滚和弹跳 |
| 预定结果 | 通过 `@` 符号控制（如 `1d20@15`），骰子物理翻滚后停在指定面 |
| WebGL 持久化 | 容器元素始终存在于 DOM 中（display:none 隐藏），避免重复初始化和内存泄漏 |
| 视觉风格 | 青铜金属材质骰子，绿色毡布桌面背景 |
| 降级方案 | 3D 初始化失败时自动回退到 SVG 2D 动画 |
| 骰子类型 | d4/d6/d8/d10/d12/d20/d100 全支持 |
| 集成方式 | Adventure.jsx 和 Combat.jsx 共享同一 DiceBox 实例 |

### 13.6 UI 全面重构：Tavern Fantasy 主题

**设计理念**：模拟 D&D 桌游的实体感 — 木纹桌面、羊皮纸气泡、金色装饰、圆桌角色环。

**重构范围**：全部 4 个页面（Home / CharacterCreate / Adventure / Combat）完全重写样式。

| 改造项 | 说明 |
|--------|------|
| 图标系统 | 40+ 内联 SVG RPG 风格图标，替代所有 emoji |
| CSS 变量体系 | 20+ 主题变量（--bg / --wood / --parchment / --gold / --red / --green / --blue 等） |
| 背景纹理 | 深棕木纹（CSS repeating-linear-gradient 模拟木板接缝）+ 顶部金色光晕 |
| 面板样式 | 木质渐变背景（#2e1f0e→rgba(46,31,14,0.8)）+ 顶部金色描边 |
| 对话气泡 | DM 羊皮纸色（#d4b87a 渐变 + clip-path 撕边）、玩家蓝色、队友绿色 |
| 角色头像 | 圆形 portrait 带职业色边框（蓝=玩家、绿=队友、金=DM、红=敌人） |
| 输入栏 | 卷轴造型（圆角 30px 木色渐变背景 + 圆形金色发送按钮） |
| 战斗地图 | 深棕格子 + 蓝/绿/红单元格高亮 + 可视化移动范围和攻击范围 |
| 响应式 | 主要面板支持横向滚动和折叠 |

---

## Phase 14: V2 Complete Experience

### V2 Features Implemented

#### 1. Character Sheet Page (`CharacterSheet.jsx`)

全功能角色面板页面，可从 Adventure 和 Combat 页面头部直接访问。

| 模块 | 内容 |
|------|------|
| 能力值 | 六维属性值 + 调整值显示 |
| 豁免检定 | 全部 6 项豁免加值 + 熟练标记 |
| 技能列表 | 全部 18 项技能加值 + 熟练标记 |
| 生命值 | 当前 HP / 最大 HP / AC |
| 装备 | 装备列表 + 装备/卸下切换 |
| 法术 | 法术位 / 已知法术 / 已准备法术 / 戏法 |
| 职业特性 | 子职业特性、语言、工具熟练 |

#### 2. Shop System（商店系统）

| 端点 | 说明 |
|------|------|
| `GET /characters/shop/inventory` | 完整武器/护甲/冒险装备目录 |
| `POST /characters/{id}/shop/buy` | 购买物品，自动扣除金币 |
| `POST /characters/{id}/shop/sell` | 出售物品，按半价回收金币 |

商品目录包含 19 种冒险装备，包括治疗药水、解毒剂、工具包、口粮等。

#### 3. Equipment Management（装备管理）

| 端点 | 说明 |
|------|------|
| `PATCH /characters/{id}/equipment` | 装备/卸下物品 |

- 更换护甲时自动重算 AC
- 武器伤害数据用于攻击计算

#### 4. Potion/Item Usage（药水/物品使用）

| 端点 | 说明 |
|------|------|
| `POST /characters/{id}/use-item` | 使用消耗品 |

| 物品 | 效果 |
|------|------|
| 治疗药水（Healing Potion） | 恢复 2d4+2 HP |
| 解毒剂（Antitoxin） | 移除中毒（poisoned）状态 |

#### 5. Movement Range Highlighting（移动范围高亮）

- 进入移动模式时，战斗网格中可达格以金色光晕高亮
- 超出范围的格子变暗并显示禁止光标
- 使用 Chebyshev 距离计算剩余移动力

#### 6. Attack Range Validation（攻击范围验证）

| 类型 | 规则 |
|------|------|
| 近战攻击 | 要求相邻（Chebyshev ≤ 1，即 5ft） |
| 远程攻击 | 检查武器射程属性（range） |
| 法术 | 验证目标距离是否在 spell.range 内 |

#### 7. Equipment-Based Damage（基于装备的伤害计算）

- 攻击伤害现在使用已装备武器的 `damage_dice`
- 若未装备武器，回退使用职业生命骰（hit_die）

#### 8. Gold UI（金币界面）

- Adventure 侧边栏角色卡显示当前金币
- Character Sheet 页面显示金币
- 通过买卖和任务奖励追踪金币变化

#### 9. Enhanced Reaction Prompts（增强反应提示）

AI 回合响应中包含详细反应选项提示：

| 反应 | 效果 |
|------|------|
| Shield 法术 | +5 AC 持续到下回合 |
| Uncanny Dodge | 伤害减半 |
| Hellish Rebuke | 反击 2d10 火焰伤害 |
| Absorb Elements | 吸收元素伤害并附加到下次近战 |

显示每个选项的具体 AC 提升或伤害减免数值。

### V2 Critical Bug Fixes

| Bug | 修复 |
|-----|------|
| SQLAlchemy JSON 列静默丢失变更 | 在所有 JSON 列（game_state / turn_states / entity_positions）in-place 变更后调用 `flag_modified()` |
| AI 回合后下一实体行动配额未重置 | `_reset_ts()` 现在在 AI 回合切换实体时正确调用 |
| HP=0 时自动判定战败 | `check_combat_over()` 不再在 HP=0 时自动判负，允许濒死豁免正常生效 |

---

## 九：非功能需求

| 类别 | 描述 | 详情 |
|------|------|------|
| 1. 性能 | AI 响应速度 | **模组解析（WF1）**：2个 LLM 调用 + 2个 Python 验证，总耗时 < 60s。**DM Agent（WF3）**：单次行动响应 < 15s（含 LLM 调用 + RAG 检索）。**队友生成（WF2）**：< 30s |
| 2. 可靠性 | 降级处理 | 每个 LangGraph 图的 parse_validate 节点均有完整的降级逻辑：JSON 解析失败时返回安全默认值（narrative-only 响应），不崩溃。LLM 调用超时（120s）自动返回错误提示 |
| 3. 安全性 | API Key 保护 | LLM API Key 存储在 `.env` 文件（不入库），通过 Pydantic Settings 读取。ChromaDB 数据存储在本地目录，无外部暴露 |
| 4. 易用性 | 零配置切换 | 仅需修改 `.env` 中的 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 即可切换 LLM 提供商。ChromaDB 自动初始化，无需手动建表 |
| 5. 兼容性 | 接口兼容 | `LangGraphClient` 与 `DifyClient` 方法签名完全一致，所有上层代码（ContextBuilder / StateApplicator / API 路由）无需修改业务逻辑 |
| 6. 可维护性 | 模块化 | 每个 Graph 独立文件（`graphs/module_parser.py` / `party_generator.py` / `dm_agent.py`），可独立测试和修改。LLM 工厂函数统一管理模型配置。提示词以 Python 常量存储，版本可控 |
| 7. 可扩展性 | 未来升级 | ChromaDB Embedding 可随时切换（配置 `embedding_function` 参数）。LangGraph 图可添加新节点（如添加"叙事润色"后处理节点）。SqliteSaver 可升级为 PostgresSaver 支持多用户 |

---

## 十：Phase 12 — 完整 5e 角色特性实现

### 新增功能

| 功能 | 后端 | 前端 | 状态 |
|------|------|------|------|
| 战斗风格（Fighter/Paladin/Ranger） | ✅ FIGHTING_STYLES + calc_derived | ✅ Step 1 条件选择器 | 已完成 |
| 起始装备系统（12职业×2方案） | ✅ WEAPONS/ARMOR/STARTING_EQUIPMENT | ✅ Step 4 装备选择 | 已完成 |
| 背景特性（12种背景） | ✅ BACKGROUND_FEATURES 自动合并技能 | ✅ Step 4 特性预览 | 已完成 |
| 语言系统 | ✅ RACIAL_LANGUAGES + ALL_LANGUAGES | ✅ Step 4 语言选择 | 已完成 |
| 工具熟练 | ✅ 从背景自动获取 | ✅ Step 4 显示 | 已完成 |
| 法术准备类型区分 | ✅ SPELL_PREPARATION_TYPE | ✅ Step 5 标签切换 | 已完成 |
| 子职业额外法术 | ✅ SUBCLASS_BONUS_SPELLS 自动添加 | ✅ 自动合并到已准备 | 已完成 |
| 专长/ASI 系统（15个专长） | ✅ FEATS + ASI_LEVELS + calc_derived | ✅ Step 6 ASI/专长选择 | 已完成 |
| 护甲/武器熟练度 | ✅ CLASS_ARMOR/WEAPON_PROFICIENCY | ✅ derived 中携带 | 已完成 |

### 新增数据表

- 35 种 SRD 武器（含伤害骰/类型/属性）
- 13 种护甲（含 AC/DEX 加成/潜行劣势）
- 6 种战斗风格（含中文名和机械效果）
- 12 种背景特性（含技能/语言/工具/特性描述）
- 15 个常用专长（含机械效果）
- 12 职业护甲/武器熟练度

### 数据库迁移

新增 4 列：`fighting_style`, `languages`, `tool_proficiencies`, `feats`

---

## 十一：E2E 测试结果（2026-04-02）

### 测试环境

- 后端：FastAPI on port 8002（uvicorn 无 --reload 模式）
- 前端：Vite dev server on port 3000
- LLM：Claude Sonnet 4.6 via AiHubMix
- DB：SQLite（清空后全新测试）

### 测试结果

| # | 测试项 | 结果 | 详情 |
|---|--------|------|------|
| 1 | 模组上传解析（WF1） | ✅ PASS | 3怪物/6场景/5NPC，140s完成 |
| 2 | 角色创建（全新特性） | ✅ PASS | 战斗风格+装备+语言+专长全部生效：AC=19 Init=7 Crit=19 |
| 3 | 队友生成（WF2） | ✅ PASS | 3名AI队友（牧师/法师/盗贼） |
| 4 | 冒险探索（多轮） | ✅ PASS | 2轮DM叙事，narrative均300+字符，含队友反应 |
| 5 | 战斗流程 | ✅ PASS | AI回合→玩家攻击(d20=10命中,7伤害)→结束回合→回合推进 |
| 6a | 战役日志 | ✅ PASS | 372字符叙事日志生成 |
| 6b | 存档点 | ✅ PASS | campaign_state含场景/决策/任务 |
| 6c | 长休 | ✅ PASS | HP/法术位恢复 |

### 已修复的问题（测试中发现并修复）

| 问题 | 修复 |
|------|------|
| DM响应显示原始JSON | `_strip_code_block` 添加 `re.MULTILINE` + 前端 `extractNarrative()` 兼容 |
| Combat网格只有12行 | `GRID_ROWS = 12` → `20` |
| Champion暴击阈值错误 | 添加 `level >= 3` 检查 |
| Journal端点取不到narrative | 从 `json.loads(dm_resp["result"])` 提取 |
| Home.jsx轮询内存泄漏 | `useRef` + `useEffect` cleanup |
| 战斗日志被journal排除 | log_type filter 添加 `"combat"` |
| UI中英文重复 | RACES/CLASSES/BACKGROUNDS 移除英文项 |
