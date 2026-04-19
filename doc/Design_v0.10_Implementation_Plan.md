# 设计 v0.10 实装计划（含战斗 + 对话冒险 BG3 风格）

**日期**：2026-04-18
**目标版本**：v0.10
**设计来源**：claude.ai/design 第二轮 handoff（iso 战场 + CRPG 对话 + 像素 token）
**Prototype**：`frontend/public/design-preview-v2/index.html`

---

## 1. 范围

**需要实装的页面**：
- **Adventure（对话冒险）** — 完全重写视觉和布局
- **Combat（战斗面板）** — 完全重写视觉和布局
- **PixelSprite 体系** — 像素 token 资源系统（先用 SVG 占位，未来可切 PNG）

**保留不动**：
- 现有视觉基础设施（v0.9 实装的 CSS / 背景层 / Portrait / Crests）
- 已迁移的其他页面（Login / Home / RoomLobby / Room / CharacterCreate / CharacterSheet / ClassGallery）
- 所有核心业务逻辑（CombatService / SpellService / DM Agent / LangGraph / 多人联机 / WebSocket / API 路由骨架）

---

## 2. 设计→后端 字段对齐表

### 2.1 Adventure 场景需要的数据

| 新 UI 数据 | 来源 | 改动类型 |
|---|---|---|
| 当前章节名 | `session.module_name` + `campaign_state.current_scene` | ✅ 已有 |
| 场景信息（地点/时间/氛围） | `session.game_state.scene_vibe` | 🆕 新字段（向后兼容） |
| 顶部队伍 HUD | `GET /game/sessions/{id}` → `player` + `companions` | ✅ 已有 |
| 旁白段 | `narrative` 字段 | ✅ 已有 |
| NPC 发言（含发言者信息） | 前端从 `narrative` 解析 / DM Agent 追加 `speaker` 字段 | 🟡 prompt 微调 |
| 编号对话选项（带 tags + DC） | `player_choices: ChoiceObj[]` | 🟡 schema 扩展（兼容旧） |
| 自由输入 | `/game/action` action_text | ✅ 已有 |
| 目标 + 线索条 | `campaign_state.quest_log` / `campaign_state.clues` | 🟡 clues 字段新增 |
| 快捷按钮（法术/休息/日志） | 现有端点 | ✅ 已有 |

### 2.2 Combat 场景需要的数据

| 新 UI 数据 | 来源 | 改动类型 |
|---|---|---|
| 回合横幅（当前回合 + 轮数） | `combat.round_number` + `turn_order[current_turn_index]` | ✅ 已有 |
| 横向先攻条 | `turn_order` + Character/Enemy HP/conditions | ✅ 已有 |
| 网格位置 | `combat.entity_positions` | ✅ 已有 |
| 墙体 / 危险地形 | `combat.grid_data` | 🟡 hazard 标记新增 |
| 可达格（移动范围） | `turn_states[id].movement_max - movement_used` | 前端 Chebyshev 计算 |
| 路径预览 | 无 | 前端 A* 计算 |
| **命中率 / 预期伤害** 目标卡 | `POST /combat/{id}/predict` | 🆕 **新端点** |
| 技能快捷栏 10 格 | `GET /combat/{id}/skill-bar` | 🆕 **新端点** |
| 行动配额 Pips (动作/附赠/反应) | `turn_states[id]` | ✅ 已有 |
| 法术位宝石 | `character.spell_slots` | ✅ 已有 |
| 条件 buff/debuff 图标 | `character.conditions + condition_durations` | ✅ 已有 |
| 伤害飘字 | `attack-roll` / `damage-roll` 响应 | 前端动画 |
| 像素 token | `enemy.sprite` + `character.cls` → 查表 | 🟡 enemy.sprite 新字段 |

---

## 3. 后端任务清单（Sprint 1）

### B1. DM Agent prompt：支持结构化 player_choices
- 修改 `backend/services/graphs/dm_agent.py` 的 explore prompt
- 新格式：`[{text, tags:[{label, kind, dc?}], skill_check?, action?, ended?}]`
- 旧格式仍兼容（纯字符串数组）
- StateApplicator 直接透传，不解析内容

### B2. scene_vibe + clues 扩展字段（向后兼容）
- `session.game_state.scene_vibe = {location, time_of_day, tension}`
- `session.campaign_state.clues = [{text, is_new, found_at}]`
- DM Agent prompt 鼓励填写（但不强制）
- StateApplicator 新增 delta 处理分支

### B3. GET `/combat/{id}/skill-bar`
- 返回当前玩家可用的 10 格技能栏配置
- 基于 `player.char_class` + `level` + `spell_slots` + `class_resources` 动态生成
- 格式：`[{k, label, glyph, cost, key, kind, available, reason?}]`
- 纯静态表 + 少量动态判断，不调 LLM

### B4. POST `/combat/{id}/predict`
- 输入：`{attacker_id, target_id, action_key}`
- 输出：`{hit_rate, expected_damage, damage_avg, crit_rate, modifiers:[]}`
- 纯算数，不掷骰、不消耗任何资源
- 考虑优势/劣势、条件、命中修正

### B5. grid_data hazard 类型
- `grid_data[x_y] = "hazard"` 新增枚举
- DM Agent 生成敌人时可在 `state_delta.grid_changes` 里产出
- 进入 hazard 格触发伤害（后续实装，本期只做数据层）

### B6. DM Agent prompt：enemy 数据带 sprite 字段
- `initial_enemies[].sprite` 字段
- 从可用 sprite key 列表（约 25 种怪物 + 12 种职业）中选
- 找不到则走 `fallback` 分类（humanoid/beast/undead/...）

---

## 4. 前端任务清单（Sprint 2）

### F1. 资源就位
- 复制 `gamefeel.css` 到 `src/styles/`（CRPG 对话 + iso 战场 + HUD 样式）
- 复制 `crests.jsx` 的最新版覆盖 `src/components/Crests.jsx`（如果有变化）
- 复制 `pixel-sprites.jsx` 的内联 SVG 版本到 `src/components/PixelSprite.jsx`

### F2. Sprite 查表系统
- `public/sprites/_INDEX.json` 写好（暂时所有条目都指向 SVG fallback）
- `src/components/Sprite.jsx`：
  - 尝试 `<img src="sprites/{kind}.png">`
  - `onerror` → 回落到 `<PixelSpriteSVG kind={...} />`（内联 SVG）
  - 这样**未来无缝换 PNG**（放 PNG 进 `public/sprites/` 即自动生效）

### F3. API 封装
- `api/client.js` 追加：
  - `combatApi.getSkillBar(sessionId)`
  - `combatApi.predict(sessionId, attackerId, targetId, actionKey)`
- `data/combat_utils.js`：
  - `chebyshevDistance(a, b)`
  - `reachableCells(pos, movementLeft, walls, gridW, gridH)`
  - `findPath(start, end, walls)` — 简单 A*

### F4. 重写 Adventure.jsx
- **保留**：
  - 所有 API 调用（`gameApi.action`, `getSession`, `handleRest`, `skill-check`, checkpoint, journal）
  - `useWebSocket` 多人联机事件处理
  - `useGameStore` 集成
  - 3D 骰子动画（`rollDice3D` / `DiceRollerOverlay`）
  - `pendingCheck` 技能检定状态
- **重写**：
  - 布局：顶部章节条 / 中部舞台（背景+NPC+玩家 silhouette）/ 对话气泡 / 底部队伍 HUD + 线索条
  - 对话选项渲染：编号 + tags + 自由输入
  - 场景信息角标（location / time / tension）
- **向后兼容**：
  - `player_choices` 可能是 `string[]` 或 `ChoiceObj[]`，两种都渲染

### F5. 重写 Combat.jsx
- **保留**：
  - 所有战斗 API 调用（`attack-roll`, `damage-roll`, `spell-roll`, `spell-confirm`, `smite`, `move`, `end-turn`, `ai-turn`, `death-save`, `reaction`, `class-feature`, `maneuver`）
  - `useWebSocket` 事件处理
  - 两步攻击 / 两步施法 / AI 回合循环逻辑
  - 3D 骰子集成
  - 子职业能力 / 反应 / 神圣斩击 prompt
- **重写**：
  - 布局：顶部回合横幅 / 横向先攻条 / 中间 iso 战场 + 目标卡浮层 / 底部三栏 HUD
  - 技能栏：从 `/skill-bar` 加载，按键 1-0 绑定
  - 目标卡：从 `/predict` 加载命中率
  - 伤害飘字：从 `damage-roll` 响应里抽数字
  - 像素 token：每个单位上方 `<Sprite kind="..." />`
- **渲染窗口**：
  - 原后端 20×20 坐标系不动，前端相机窗口固定渲染 10×7 或 12×8 网格
  - 居中在当前回合角色 / 玩家主角上

---

## 5. 依赖关系与执行顺序

```
B1 ─┐
B2 ─┤
B5 ─┤
B6 ─┤─► F3 ─► F4 (Adventure)
    │
B3 ─┤
B4 ─┘─► F3 ─► F5 (Combat)

F1 ─► F2 ─► F4 & F5
```

执行顺序：**B1-B6 并行 → F1-F3 → F4 → F5 → 验证**

---

## 6. 风险与决策记录

| 风险 | 缓解 |
|---|---|
| DM Agent 可能不按新 schema 输出 | 前端做兼容降级；StateApplicator 容错 |
| `/predict` 计算和实际 `/attack-roll` 存在小偏差 | 作为"参考值"呈现，不保证完全一致 |
| 路径 A* 在复杂地形下可能慢 | 网格 ≤20×20，复杂度 O(N²) 可接受 |
| 像素资源没有 PNG | 先用 SVG 兜底，生产时换 PNG 无需改代码 |
| 20×20 坐标系下 iso 相机窗口切片 | 固定窗口围绕玩家，超出部分显示为空白格 |
| 重写可能破坏多人联机 | 所有 WS 事件处理 / owner 校验保留 |

---

## 7. 验收标准

### Adventure
- [ ] 新 UI 上能正常发言 → DM 回复
- [ ] 编号选项可点击
- [ ] 检定提示可触发 3D 骰子
- [ ] 队伍 HUD 血条实时同步
- [ ] 多人模式发言权指示器显示
- [ ] WebSocket 广播推到日志

### Combat
- [ ] 攻击流程：点技能 → 选目标 → 两步攻击 → 伤害飘字
- [ ] 施法流程：点法术 → 选目标 → 两步施法
- [ ] 移动：点目标格 → 距离检查 → 移动 → 借机攻击处理
- [ ] 目标卡显示命中率
- [ ] 技能栏 1-0 键位绑定可用
- [ ] 像素 token 显示（即使是 SVG 兜底也可见）
- [ ] 多人回合切换正确

---

## 8. 工作量估算（实际执行）

| 阶段 | 范围 | 压缩执行 |
|---|---|---|
| 规划文档 | 本文档 | 完成 |
| 后端 B1-B6 | 6 个任务 | 集中一次性改完 |
| 前端 F1-F3 | 基础设施 | 连续完成 |
| 前端 F4 Adventure 重写 | 含保留业务逻辑 | 单文件 |
| 前端 F5 Combat 重写 | 最大头 | 单文件 |
| 验证 | build + import 检查 | 最后 |

**原则**：重写时**不复制旧文件**，打开旧文件只为复制 API 调用 / hooks 调用，其余从空白开始写。

---

## 9. 文件清单（预期新建 / 修改）

### 新建
- `frontend/src/components/PixelSprite.jsx`（SVG 像素精灵 fallback）
- `frontend/src/components/Sprite.jsx`（查表 + 降级）
- `frontend/src/styles/gamefeel.css`
- `frontend/src/data/combat_utils.js`
- `frontend/public/sprites/_INDEX.json`（初始全部指向 fallback）
- `frontend/public/sprites/.gitkeep`
- `doc/Design_v0.10_Implementation_Plan.md`（本文件）

### 修改
- `backend/services/graphs/dm_agent.py`（B1/B2/B6 prompt 追加）
- `backend/services/state_applicator.py`（B2 clues / scene_vibe 处理）
- `backend/api/combat.py`（B3/B4 新端点 + B5 hazard）
- `backend/schemas/game_schemas.py`（追加可选 Pydantic schema）
- `frontend/src/api/client.js`（B3/B4 API 封装）
- `frontend/src/pages/Adventure.jsx`（完全重写）
- `frontend/src/pages/Combat.jsx`（完全重写）
- `frontend/src/App.jsx`（CSS 引入）

---

**规划完成。现在开始执行。**
