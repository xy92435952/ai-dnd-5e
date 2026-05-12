# 技术架构文档

**项目：** AI 跑团平台（DnD 5e）
**文档更新时间：** 2026-05-09
**当前状态：** Adventure / Combat / DM Agent 已进入结构化拆分阶段，多人联机已加入分队焦点和 Multiplayer DM 桌面裁决。

## 1. 总览

```text
React 19 + Vite 8
  │
  │ HTTP / WebSocket
  ▼
FastAPI + SQLAlchemy 2.0
  ├─ 本地 5e 规则层：dnd_rules / combat_service / api.combat
  ├─ DM 编排层：LangGraph dm_agent
  ├─ 输入安全层：input_guard
  ├─ 自然语言战斗解析：action_parser
  ├─ RAG：ChromaDB
  └─ DB：SQLite（本地）/ PostgreSQL（生产）
```

核心原则：

- **AI 负责叙事和意图理解，不负责规则数学。**
- **后端是规则权威。** 前端可以展示骰子和交互，但最终 HP、条件、回合资源由后端写库。
- **DM Agent 拆成输入 / 规则 / 叙事 / 记忆四层。** 这样后续改 prompt 或规则校验时不必碰整条链路。
- **多人和单人共用主业务入口。** `/game/action` 根据 `session.combat_active` 和多人发言权分流。
- **多人桌面秩序先于叙事。** 复杂分队、切镜头、秘密行动和同时行动先由 Multiplayer DM v2 裁决是否进入基础 DM；简单同组行动继续走确定性聚合，避免每次多人输入都增加 LLM 延迟。

## 2. 技术栈

| 层 | 当前选型 |
|----|----------|
| 前端 | React 19、React Router 7、Vite 8、Zustand 5 |
| 前端测试 | Vitest 4、Testing Library、jsdom |
| 后端 | FastAPI、Pydantic v2、SQLAlchemy 2.0 async |
| 数据库 | SQLite（本地默认）、PostgreSQL（生产推荐） |
| AI 编排 | LangGraph StateGraph |
| LLM 接入 | `langchain-openai`，支持 DeepSeek / OpenAI / AiHubMix / OpenRouter 等 OpenAI 兼容 API |
| RAG | ChromaDB 本地持久化 |
| 通信 | HTTP + FastAPI WebSocket |
| 部署 | nginx 静态前端 + uvicorn 后端，或 Docker Compose |

## 3. 后端架构

### 3.1 API 层

```text
backend/api/
├── auth.py                 注册 / 登录
├── modules.py              模组上传、解析、列表
├── characters.py           角色创建、队友生成、准备法术
├── game.py                 会话、探索行动、自然语言战斗入口、休息、日志、checkpoint
├── rooms.py                多人房间
├── ws.py                   WebSocket
├── deps.py                 共享依赖和序列化
└── combat/                 战斗端点包
```

`api/combat/` 已从历史大文件拆为多个职责模块：

```text
_shared.py                  回合状态、距离、移动、广播等共享 helper
info.py                     战斗状态和技能栏查询
turns.py                    结束回合、回合推进
movement.py                 地图移动
attack_rolls.py             攻击检定 pending attack
attack_damage.py            伤害确认
attack_targeting.py         目标和距离辅助
attack_modifiers.py         优劣势 / 暴击 / 修正
attack_actions.py           攻击动作组合
attacks.py                  旧 /action 攻击兼容路径
spell_rolls.py              法术掷骰 pending spell
spell_effects.py            法术效果应用
spell_targets.py            法术目标校验
spell_catalog.py            法术目录辅助
spellcasting.py             旧施法入口兼容
pending_spells.py           pending spell 状态
ai_turn*.py                 AI 回合上下文、动作、攻击、施法、结束
class_features.py           职业特性
grapples.py                 擒抱 / 推撞
maneuvers.py                战技
smites.py                   神圣斩击
reactions.py                反应
conditions.py               条件
deathsaves.py               濒死豁免
schemas.py                  combat 请求/响应模型
```

### 3.2 服务层

```text
backend/services/
├── campaign_delta.py           Living Campaign State 归一化与合并
├── graphs/
│   ├── module_parser.py        模组解析 graph
│   ├── party_generator.py      AI 队友生成 graph
│   ├── dm_agent.py             DM Agent 公开入口和 LangGraph 连线
│   ├── dm_agent_nodes.py       input/rules/memory/combat/explore/parse 节点
│   ├── dm_agent_state.py       LangGraph state 类型和消息窗口
│   ├── dm_agent_prompts.py     探索/战斗/战役状态提示词
│   ├── dm_agent_utils.py       兼容出口：输入/规则/记忆/输出 helper
│   ├── dm_agent_input_meta.py  输入元数据
│   ├── dm_agent_rules_context.py     规则层上下文
│   ├── dm_agent_memory_context.py    记忆层上下文
│   ├── dm_agent_output_normalizer.py DM 输出归一化与 schema repair
│   ├── dm_agent_runtime.py     骰池、初始状态、最终响应包装
│   ├── dm_agent_messages.py    LLM 用户消息组装
│   ├── dm_agent_memory.py      LangGraph checkpoint 初始化
│   ├── dm_campaign_state.py    战役状态摘要生成
│   ├── multiplayer_dm_agent.py       多人 DM 桌面裁决入口
│   ├── multiplayer_dm_context.py     多人房间 / 分队上下文快照
│   ├── multiplayer_dm_prompts.py     v2 裁决提示词
│   └── multiplayer_dm_state.py       v1/v2 裁决数据模型
├── input_guard.py              输入分类和拦截入口
├── input_guard_policy.py       本地高置信度拦截/放行规则
├── input_guard_types.py        输入守卫类型定义
├── action_parser.py            自然语言战斗行动解析
├── combat_service.py           攻击/伤害/治疗/条件核心规则
├── dnd_rules.py                5e 属性、检定、先攻、骰子等规则
├── combat_narrator.py          战斗机械结果 → 叙事
├── ai_combat_agent.py          敌人/队友 AI 战斗决策
├── context_builder.py          构建 DM 输入上下文
├── state_applicator.py         DM 输出 state_delta 写库
├── langgraph_client.py         AI graph 统一客户端
├── llm.py                      LLM 工厂
├── local_rag_service.py        ChromaDB 检索
└── character_roster.py         session 队伍访问器
```

## 4. DM Agent 四层流程

可视化架构版本见 [DM_Agent_Architecture.html](./DM_Agent_Architecture.html)，其中单独展开了输入来源、规则拦截、叙事分支、记忆来源、自然语言战斗解析和输出契约。

```mermaid
flowchart TD
  A["/game/action"] --> B["输入层 input_layer"]
  B --> C{"输入来源 / 安全分类"}
  C -->|blocked| X["拒绝回复，不进规则和叙事"]
  C -->|in_game| P["pre_roll_dice"]
  P --> D["规则层 rules_layer"]
  D --> F["记忆层 memory_layer"]
  F --> E{"combat_active?"}
  E -->|true| G1["叙事层 combat_dm"]
  E -->|false| G2["叙事层 explore_dm"]
  G1 --> H["parse_validate"]
  G2 --> H["parse_validate"]
  H --> I["StateApplicator 写库"]
  I --> J["PlayerActionResponse"]
```

### 输入层

输入来源：

- `human_input`
- `ai_generated_choice`
- `system_action`
- `ai_takeover`

AI 生成选项不是客户端说了算。后端会检查 `session.game_state.last_turn.player_choices`，只有点击文本匹配上一轮 DM 生成选项时才承认为 `ai_generated_choice`。

### 规则层

规则层负责：

- 识别技能检定、战斗触发、规则作弊。
- 放行合理术语，例如优势骰、激励骰、帮助动作。
- 阻断明显超出 5e 规则或游戏边界的内容。

### 叙事层

叙事层负责把规则允许的行动写成 DM 文本，但不能绕过后端规则。战斗伤害、HP、条件、回合资源仍由规则层和 API combat 模块决定。

### 记忆层

记忆来自：

- `GameLog`
- `session.session_history`
- `session.campaign_state`
- LangGraph checkpoint
- RAG 检索出的模组片段

### Living Campaign State

探索 DM 可以在标准响应中输出 `campaign_delta`，用于表达本轮产生的结构化战役变化：

- `quest_updates`：任务状态变化，按任务名去重更新 `campaign_state.quest_log`。
- `npc_updates`：NPC 关系、关键事实、承诺，按 NPC 名合并进 `campaign_state.npc_registry`。
- `key_decisions_add`：影响后续剧情的关键决定，去重追加到 `campaign_state.key_decisions`。
- `world_flags_set`：世界状态 flag，合并到 `campaign_state.world_flags`。
- `clues_add`：玩家实际发现的新线索，去重追加到 `campaign_state.clues`，并补 `found_at` / `is_new`。
- `scene_vibe`：当前地点、时间和紧张度，写入 `session.game_state.scene_vibe`。

`services.campaign_delta.normalize_campaign_delta` 会先修复坏类型和缺字段，`StateApplicator` 再调用 `apply_campaign_delta` 合并入 session。旧版 `state_delta.clues_add` 和 `state_delta.scene_vibe` 仍被兼容读取。

前端 Adventure 底部 HUD 会读取最近任务、线索、NPC 关系和关键决定，让玩家能感到 DM 正在记住故事。

## 5. Multiplayer DM 桌面裁决

多人探索阶段在 `/game/action` 进入基础 DM Agent 前，会先经过 `services.graphs.multiplayer_dm_agent.run_multiplayer_dm_agent`。

```mermaid
flowchart TD
  A["多人 /game/action"] --> B["发言权 / 角色绑定校验"]
  B --> C["build_multiplayer_dm_context"]
  C --> D{"是否复杂桌面局面?"}
  D -->|否| E["v1 确定性聚合同组 pending actions"]
  D -->|是| F["v2 table decision"]
  F -->|process_actor_group / process_active_group| G["组装 effective_action_text"]
  F -->|switch_focus / wait_for_group| H["返回 multiplayer_table，不调用基础 DM"]
  F -->|解析失败 / LLM 失败| E
  E --> G
  G --> I["基础 DM Agent 四层流程"]
  I --> J["成功后清空对应分队 pending actions / 更新 active_group_id / 广播 RoomStateUpdated"]
  H --> K["应用 active_group_id / 广播 RoomStateUpdated"]
```

### v1 确定性路径

默认路径不调用 LLM，只做三件事：

- 找到行动玩家所在分队，作为当前焦点组。
- 把同组队友的 `pending_actions_by_group[group_id]` 合并进 `effective_action_text`，交给基础 DM。
- 把焦点分队的 `group_readiness[group_id]` 摘要进 `effective_action_text`，让基础 DM 知道哪些玩家已确认、仍在草拟或正在等待。
- 只提示“其他分队有待处理动作”，不把其他分队行动文本喂给基础 DM，避免跨分队泄露信息。

这个路径适合大多数“同组一起行动”的情况，延迟低、行为稳定。

readiness 会参与 v1 / v2 分流：

- 焦点分队已有 pending actions 且该分队成员都 `ready`，而其他有 pending 的分队都未全员 `ready` 时，直接走 v1 处理焦点分队。
- 如果多个分队都全员 `ready` 且都有 pending actions，则进入 v2，只裁决先处理哪一组，不合并不同分队行动。
- `waiting` 表示该分队主动等待补充或回应，除非玩家明确要求切镜头，否则不抢走当前镜头。
- 当前分队被基础 DM 成功处理并清空后，如果另一个分队仍有 pending actions 且全员 `ready`，后端会在同一次 `RoomStateUpdated` 中把 `active_group_id` 推进到该分队，形成“下一镜头建议/自动切镜头”的桌面节奏。

### v2 桌面裁决路径

只有复杂局面才触发 v2：

- 当前焦点组和其他分队同时都有待处理行动。
- 玩家文本包含切镜头、同时行动、秘密行动、分头行动、等待确认等桌面管理意图。

v2 的职责是输出结构化 `MultiplayerTableDecision`：

- `decision`：`process_actor_group`、`process_active_group`、`wait_for_group`、`switch_focus`。
- `focus_group_id`：应该处理或切换到的分队。
- `groups[].readiness`：每个分队成员的桌面确认状态，取值为 `drafting`、`ready`、`waiting`。
- `knowledge_scope` / `visible_to_user_ids`：该桌面信息的可见范围。
- `clear_pending_group_ids`：基础 DM 成功处理后可清空的分队队列。
- `table_message`：不进入基础 DM 时返回给前端的桌面提示。
- `reason`：裁决理由。进入 `MultiplayerDMDecision.table_reason` 后，会随 `multiplayer_table` HTTP 响应和 `DMResponded` 实时事件保留，方便前端解释“为什么切镜头/等待/先处理某分队”。

v2 不写正式剧情，不结算规则，只管理多人桌面流程。它输出坏 JSON 或 LLM 调用失败时会自动回退 v1，保证联机行动不被桌面裁决层卡死。

### 实时可见性

`DMResponded` 支持携带 `visibility`：

- `scope=party` 或没有可见用户列表时，按原方式广播给全房间。
- `scope=group/private` 且有 `visible_to_user_ids` 时，后端通过 `ws_manager.send_to_user` 点对点发送给可见玩家，不做全房间广播。
- 前端 `useDialogueWsSync` 会再次检查 `visible_to_user_ids`，收到不属于自己的事件时不进入剧场，也不触发 `loadSession`。
- `/game/action` 的 HTTP 响应也会返回同一份 `visibility`，因此行动发起者的剧场内容会立即带上“分队/私密”标识，不需要等下一次刷新。
- 可见事件进入剧场队列时会保留 `visibility`，剧场播完落入本地日志后，Adventure 聊天日志会显示“分队”或“私密”标识，避免玩家误以为所有人都看到了同一段内容。
- Adventure 还会基于当前用户已经可见的日志构建“分队时间线”：公共、我的分队、私密三栏只读展示最近 DM 记录。它不绕过后端过滤，不给房主额外视野，只帮助玩家理解当前联机桌面的信息分层。

### 持久化可见性

`GameLog` 也保存同一份 `visibility` JSON。`/game/sessions/{session_id}` 恢复日志时会按当前登录用户过滤：

- 旧日志或没有 `visible_to_user_ids` 的日志默认全队可见。
- 带 `visible_to_user_ids` 的日志只返回给列表中的用户。
- 房主只是技术房主，仍然是玩家；不在 `visible_to_user_ids` 中时也不能恢复其他玩家的分队/私密日志。
- Multiplayer DM 给基础 DM 生成的正式叙事会把本轮 `visibility` 注入 DM 输出，再由 `StateApplicator` 写入 `GameLog`。
- `multiplayer_table` 桌面提示也会以同样的 `visibility` 写入日志。

这样实时 WebSocket 和刷新后的日志恢复使用同一份可见性语义。后续如果需要真正的主持人/旁观 DM 视图，应增加独立角色或显式房间开关，不能默认绑定到房主。

## 6. 自然语言战斗流程

```mermaid
flowchart TD
  A["玩家输入自然语言战斗行动"] --> B["input_guard"]
  B --> C["action_parser 本地常见意图解析"]
  C -->|命中本地规则| D["结构化 actions"]
  C -->|无法确定| E["LLM parser"]
  E -->|失败/超时| F["fallback parser"]
  E --> D
  F --> D
  D --> G["api.game 执行 move / attack / spell / creative"]
  G --> H["combat_service / dnd_rules 结算"]
  H --> I["combat_narrator 叙事包装"]
  I --> J["返回 combat_update / dice_display / action_results"]
```

关键修复：

- 近战目标不可达时，只生成 `move`，不生成同回合假 `attack`。
- 叙事器根据实际执行动作类型选择 `move` / `attack` / `creative` / `out_of_range`，避免“只是移动却讲成攻击失败”。

## 7. 前端架构

### 7.1 页面

```text
frontend/src/pages/
├── Home.jsx
├── Login.jsx
├── CharacterCreate.jsx
├── Adventure.jsx
├── Combat.jsx
├── CharacterSheet.jsx
├── RoomLobby.jsx
├── Room.jsx
└── ClassGallery.jsx
```

### 6.2 Adventure 拆分

```text
components/adventure/
├── AdventureTopBar.jsx
├── AdventureStage.jsx
├── DialoguePanel.jsx
├── DialogueChoices.jsx
├── DialogueFreeSpeak.jsx
├── DialogueLogList.jsx
├── DialoguePendingCheck.jsx
├── DialogueResponseBox.jsx
├── AdventureBottomHud.jsx
├── AdventurePartyHud.jsx
├── AdventureQuestHud.jsx
└── MultiplayerSpeakBar.jsx

hooks/
├── useAdventureSession.js
├── useAdventureActions.js
├── useAdventureMultiplayer.js
├── useDialogueFlow.js
├── useDialogueWsSync.js
└── useSkillCheck.js
```

### 6.3 Combat 拆分

```text
components/combat/
├── CombatStage.jsx
├── IsoBattlefield.jsx
├── IsoBattlefieldCell.jsx
├── IsoUnit.jsx
├── CombatHud.jsx
├── CombatHudSkillBar.jsx
├── CombatHudCombatLog.jsx
├── CombatHudControls.jsx
├── InitiativeRibbon.jsx
├── SpellModal*.jsx
├── ReactionPrompt.jsx
├── SmitePrompt.jsx
└── TurnBanner.jsx

hooks/
├── useCombatLoader.js
├── useCombatDerivedState.js
├── useCombatPlayerActions.js
├── useCombatAttackFlow.js
├── useCombatSpellFlow.js
├── useCombatAiTurns.js
├── useCombatTurnControls.js
├── useCombatSkillBar.js
├── useCombatPrediction.js
└── useCombatRoom.js
```

## 7. 数据模型概览

主要 ORM：

- `User`
- `Module`
- `Character`
- `Session`
- `CombatState`
- `GameLog`
- `SessionMember`

重要 JSON 字段：

- `Session.game_state`
- `Session.campaign_state`
- `CombatState.entity_positions`
- `CombatState.turn_order`
- `CombatState.turn_states`
- `Character.derived`
- `Character.spell_slots`
- `Character.conditions`
- `Module.parsed_content`
- `GameLog.dice_result`

修改 JSON 字段必须遵守 [docs/json-field-convention.md](/Users/qft/Desktop/ai-dnd-5e/docs/json-field-convention.md)，必要时调用 `flag_modified`。

## 8. API 概览

| 模块 | 路径 |
|------|------|
| 认证 | `/auth/register`, `/auth/login`, `/auth/me` |
| 模组 | `/modules/`, `/modules/upload`, `/modules/{id}` |
| 角色 | `/characters/options`, `/characters/create`, `/characters/generate-party`, `/characters/{id}` |
| 游戏 | `/game/sessions`, `/game/action`, `/game/skill-check`, `/game/sessions/{id}/rest` |
| 战斗 | `/game/combat/{session_id}`, `/attack-roll`, `/damage-roll`, `/spell-roll`, `/spell-confirm`, `/move`, `/end-turn`, `/ai-turn` |
| 多人 | `/game/rooms/create`, `/join`, `/start`, `/claim-character`, `/fill-ai` |
| WebSocket | `/ws/sessions/{session_id}?token=...` |

## 9. 测试

后端测试：

```bash
cd backend
python -m pytest tests/ -q
```

前端测试：

```bash
cd frontend
npm test
npm run build
```

当前重点测试覆盖：

- `backend/tests/unit/test_action_parser.py`
- `backend/tests/unit/test_input_guard.py`
- `backend/tests/unit/test_dm_agent_layers.py`
- `backend/tests/integration/test_combat_endpoints.py`
- `backend/tests/smoke/test_imports.py`
- `frontend/src/pages/__tests__/Adventure.smoke.test.jsx`
- `frontend/src/pages/__tests__/Combat.smoke.test.jsx`
- `frontend/src/hooks/__tests__/useCombat*.test.js`

## 10. 已知技术债

- `npm run lint` 会扫到 `frontend/public/design-preview-*` 旧设计稿和部分 React Compiler 风格规则报错；当前发布以 `npm test` 和 `npm run build` 为准。
- 前端 chunk 较大，Dice / world 资源后续适合动态 import。
- DM Agent prompt 和规则层还可以继续拆成更小的 prompt 模板和 policy 文件。
- 部分 5e 子职业/反应/召唤物等高级规则仍为近似实现。
- 多人 WebSocket 仍是进程内管理，横向扩容需要 Redis pub/sub 或外部消息层。
