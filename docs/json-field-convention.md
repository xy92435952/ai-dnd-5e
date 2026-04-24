# JSON 字段修改约定

> 如果你改了任何 SQLAlchemy 的 JSON 列（`session.game_state`、`combat_state.turn_states`、`character.derived` 等），**必须** 在 commit 前调用 `flag_modified(obj, "字段名")`。否则 SQLAlchemy 不会检测到字典内容的变更，数据库不会被更新，bug 极难调试。

## 背景

SQLAlchemy 的 JSON 列用的是 mutation tracking——它检测的是 **属性赋值**，不是字典的嵌套修改。以下写法都**不会**触发自动保存：

```python
session.game_state["companion_ids"].append(cid)         # 嵌套 append 不触发
session.game_state["last_turn"]["ts"] = datetime.utcnow()  # 嵌套赋值不触发
combat.turn_states[entity_id]["action_used"] = True      # 同上
character.derived["hp_max"] = 20                         # 同上
```

只有顶层属性赋值才会被追踪：

```python
session.game_state = {**session.game_state, "x": 1}   # ✅ 触发
```

但这种写法不直观，所以项目约定走 `flag_modified` 显式声明。

## 正确姿势

### 场景 A：修改嵌套字段

```python
from sqlalchemy.orm.attributes import flag_modified

gs = dict(session.game_state or {})
gs["last_turn"] = {
    "player_choices": ar.player_choices or [],
    "ts": datetime.utcnow().isoformat(),
}
session.game_state = gs                 # 先赋回去
flag_modified(session, "game_state")    # 再显式标记
```

**两步都不能省**：
- 只赋值不 flag_modified：dict 是同一个引用，SQLAlchemy 仍看不到变化
- 只 flag_modified 不赋值：某些版本可以工作，但依赖内部实现，不可靠

### 场景 B：整个字段替换

```python
session.game_state = {"companion_ids": [...], "scene_index": 0}
# 这种情况不需要 flag_modified，因为是属性赋值
```

### 场景 C：删除嵌套键

```python
ts = dict(combat.turn_states or {})
ts.pop(entity_id, None)
combat.turn_states = ts
flag_modified(combat, "turn_states")
```

## 受约束的字段清单

在这个代码库里，以下字段都是 JSON 列，修改时必须遵守上述约定：

| Model | 字段 | 内容 |
|-------|------|------|
| `Session` | `game_state` | companion_ids / enemies / last_turn / multiplayer / flags |
| `Session` | `campaign_state` | completed_scenes / npc_registry / quest_log / world_flags |
| `CombatState` | `turn_states` | 每实体的 action_used / movement_used / reaction_used |
| `CombatState` | `entity_positions` | {entity_id: {x, y}} |
| `CombatState` | `turn_order` | [{character_id, initiative, is_player, is_enemy}] |
| `CombatState` | `grid_data` | 地形字典 |
| `Character` | `derived` | hp_max / ac / ability_modifiers / spell_save_dc |
| `Character` | `spell_slots` | {1st: 2, 2nd: 1} |
| `Character` | `known_spells` / `prepared_spells` / `cantrips` | list |
| `Character` | `conditions` / `condition_durations` | 状态条件 |
| `Character` | `death_saves` | {successes, failures, stable} |
| `Character` | `equipment` | 背包与装备 |
| `Character` | `class_resources` | 职业特有资源（如狂暴次数） |
| `Character` | `multiclass_info` | 多职业信息 |
| `Module` | `parsed_content` | WF1 解析结果 |
| `GameLog` | `dice_result` | 骰子原始结果 |

## 常见陷阱

### ❌ 只改嵌套键不 flag_modified

```python
# BAD —— 这个改动不会被持久化
session.game_state["multiplayer"]["current_speaker_user_id"] = next_uid
await db.commit()   # commit 但没写库
```

### ❌ 在 `await` 之前忘了 flag_modified

```python
gs = dict(session.game_state or {})
gs["x"] = 1
session.game_state = gs
await some_async_call()          # 期间其他 session 可能 flush
flag_modified(session, "game_state")  # ✅ 只要在最终 commit 前就行
await db.commit()
```
这样是 OK 的。但最佳实践是 **紧跟赋值** 写 `flag_modified`，避免中间代码意外 await 然后因为异常跳过标记。

### ❌ 跨请求共享 JSON 字段引用

```python
# BAD
gs = session.game_state  # 直接拿引用
gs["x"] = 1              # 改了原字典，但 SQLAlchemy 认为对象没变
```

### ✅ 正确做法：`dict(session.game_state or {})` 始终先做浅拷贝

```python
gs = dict(session.game_state or {})   # 浅拷贝
gs["x"] = 1
session.game_state = gs
flag_modified(session, "game_state")
```

## 检查清单（PR Review）

代码审查看到 JSON 列修改时，问自己：

- [ ] 顶层是否 `xxx = dict(xxx or {})` 浅拷贝，再修改？
- [ ] 修改后是否显式 `obj.field = gs`？
- [ ] 是否 `flag_modified(obj, "field")`？
- [ ] commit 前最后一次修改是否都 flag_modified 过了？
- [ ] 如果是嵌套字段（`gs["multiplayer"]["x"]`），内层 dict 也做了拷贝吗？

## 未来方向

这部分约定容易遗漏。可选的长期改进：
1. 把常见的"改 game_state 后持久化"封装为 helper（如 `persist_session_state(session, patch)`），让调用方不必记 flag_modified
2. 用 `MutableDict.as_mutable(JSON)` 替代 plain JSON 列（但会引入性能开销，每次嵌套赋值都 track）
3. 在 CI 中加静态检查：grep `session.game_state\[` 后面 100 行内必须出现 `flag_modified`（粗糙但有效）

目前项目阶段选择"约定 + 文档"，优先保持代码直观。
