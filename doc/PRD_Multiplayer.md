# PRD — 多人联机功能（v0.9-multiplayer）

> 版本：v0.1（初稿）
> 起草日期：2026-04-17
> 目标版本号：v0.9
> 阶段：阶段 A（MVP）→ B（DM 协作）→ C（体验打磨）
> 依赖：v0.8（PostgreSQL + 53 子职业 + NL 战斗）

---

## 1. 背景与目标

### 1.1 现状
当前 v0.8 是**单人跑团**：一个 user 创建 session、生成 4 个 AI 队友、独自体验冒险。数据层 PostgreSQL + JWT + LangGraph PostgresSaver 已就绪，但交互层是"单客户端 → 单服务端"的请求-响应模式。

### 1.2 目标
让 **2-4 个真人玩家** 同处一个战役房间，共享同一个 DM Agent 和战斗状态，实现"和朋友一起跑团"的体验。

### 1.3 非目标（本期不做）
- 6+ 人房间
- 跨服务器联机（单实例即可，不引入 Redis）
- 观战模式
- 同步播放他人的 3D 骰子动画
- 语音聊天（接 Discord 即可）
- 完整的协作地图绘制

---

## 2. 关键决策（已与用户对齐）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 房间规模 | 2-4 人 | FastAPI 内存广播，无需 Redis |
| DM 输入模式 | 轮流发言制（Round-Robin）| 比队长制公平，比自由发言简单 |
| 角色归属 | 1 人 1 角色 + AI 托管空位 | 复用现有 `ai_combat_agent` |
| 探索行动 | 发言自由 + 检定串行 | 防止两人同时投同一检定 |
| 观战模式 | 不支持 | 加入即必须创角，模型简化 |
| 骰子展示 | 只看结果 | 节省带宽 |
| 加入方式 | 6 位房间码 | 简单、无需公开列表 |
| 房主权限 | 单房主 | 房主退出需转移或解散 |
| 断线处理 | AI 立即托管 | 复用 `ai_combat_agent` |
| 通信库 | 原生 WebSocket | 轻量 |
| DB 迁移 | alembic | 标准方式 |
| 向后兼容 | 单/多人并存 | 旧战役不破坏 |

---

## 3. 数据模型变更

### 3.1 新增 `SessionMember` 表

```python
class SessionMember(Base):
    __tablename__ = "session_members"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id   = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    user_id      = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(String, ForeignKey("characters.id"), nullable=True)
    role         = Column(String(20), default="player")  # host / player
    joined_at    = Column(DateTime, server_default=func.now())
    last_seen_at = Column(DateTime, server_default=func.now())  # 用于断线检测

    # 同一 session 内 user 只能有一条记录
    __table_args__ = (UniqueConstraint("session_id", "user_id"),)
```

### 3.2 修改 `Session` 表

```python
# 新增字段
room_code   = Column(String(6), nullable=True, unique=True, index=True)
is_multiplayer = Column(Boolean, default=False)
host_user_id   = Column(String, ForeignKey("users.id"), nullable=True)
max_players    = Column(Integer, default=4)

# player_character_id 在多人模式下作废，由 SessionMember.character_id 取代
# user_id 字段保留用于"创建者"，但不再是唯一所有者
```

### 3.3 修改 `Character` 表

```python
# 新增字段
user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
# is_player=True 且 user_id 非空 → 真人玩家角色
# is_player=True 且 user_id 为空 → 单人模式的玩家角色（向后兼容）
# is_player=False                → AI 队友（user_id 必为空）
```

### 3.4 房间码生成

```python
def generate_room_code() -> str:
    """生成 6 位数字房间码，避免 0 和 O 等易混淆字符（纯数字本身无此问题）"""
    while True:
        code = "".join(random.choices("23456789", k=6))  # 8 进制减少误读
        # 检查唯一性
        if not await db.scalar(select(Session).where(Session.room_code == code)):
            return code
```

---

## 4. 后端 API 变更

### 4.1 新增端点 `/game/rooms/`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/game/rooms/create` | 创建多人房间，返回 room_code |
| POST | `/game/rooms/join` | 用 room_code 加入房间 |
| POST | `/game/rooms/{session_id}/leave` | 离开房间（房主离开则解散） |
| POST | `/game/rooms/{session_id}/start` | 房主：所有人选完角色后开始游戏 |
| POST | `/game/rooms/{session_id}/kick` | 房主：踢出成员 |
| POST | `/game/rooms/{session_id}/transfer` | 房主：转让房主权限 |
| GET | `/game/rooms/{session_id}/members` | 获取成员列表（含在线状态） |
| POST | `/game/rooms/{session_id}/claim-character` | 玩家认领一个角色 |
| POST | `/game/rooms/{session_id}/fill-ai` | 房主：补满 AI 队友（按 max_players - 真人数 - 已有AI数 生成缺口） |

#### 创建房间请求

```json
POST /game/rooms/create
{
  "module_id": "abc-123",
  "max_players": 4,
  "save_name": "周五跑团团"
}

Response:
{
  "session_id": "...",
  "room_code": "234567",
  "host_user_id": "..."
}
```

#### 加入房间流程

```
1. POST /game/rooms/join {room_code: "234567"}
   → 服务端验证：码存在 + 房间未满 + 游戏未开始
   → 创建 SessionMember 记录（character_id=None）
   → 通过 WS 广播 "member_joined" 事件给房间所有人

2. POST /characters (创建角色，user_id=本人, session_id=房间id)
   → 角色入库
   → 前端角色创建向导检测 URL 中 ?roomSession=xxx 查询参数，
     判定为"多人创建"模式：完成向导后不再生成 AI 队伍，而是
     调用 /claim-character 并 navigate 回 /room/:sessionId

3. POST /game/rooms/{id}/claim-character {character_id: ...}
   → 设置 SessionMember.character_id
   → 广播 "character_claimed"

4. （可选）房主 POST /game/rooms/{id}/fill-ai
   → 校验：房主权限 + 游戏未开始 + 至少 1 位玩家已认领角色
   → 以第一位已认领角色作为参考，调用 langgraph_client.generate_party
     生成 max_players - 真人数 - 已有AI数 个互补 Character
     （is_player=False, user_id=None, session_id=房间id）
   → 广播 "ai_companions_filled"，所有客户端 refresh 房间

5. 房主 POST /game/rooms/{id}/start
   → 验证：至少 1 位 SessionMember 已认领角色
     （其余真人空位 → AI 托管；额外 AI 队友已通过 fill-ai 预先生成）
   → 广播 "game_started"
   → 触发 DM Agent 第一轮叙事
```

### 4.2 修改现有战斗端点

所有 `/game/combat/*` 端点新增中间件校验：

```python
async def assert_can_act(session: Session, user: User, entity_id: str, db):
    """校验当前 user 是否有权操作 entity_id 这个角色"""
    if not session.is_multiplayer:
        return  # 单人模式跳过
    char = await db.get(Character, entity_id)
    # AI 队友：任何人都可触发（通过 ai-turn 端点）
    if not char.is_player:
        return
    # 真人角色：必须本人操作
    if char.user_id != user.id:
        raise HTTPException(403, "Not your character")
    # 战斗中：必须是当前回合
    if session.combat_active:
        cs = await get_combat_state(session.id, db)
        current = cs.turn_order[cs.current_turn_index]
        if current["character_id"] != entity_id:
            raise HTTPException(403, "Not your turn")
```

涉及修改的端点（10 个）：
- `/game/combat/{id}/action`（attack-roll / damage-roll）
- `/game/combat/{id}/spell` 及 spell-confirm
- `/game/combat/{id}/move`
- `/game/combat/{id}/end-turn`
- `/game/combat/{id}/death-save`
- `/game/combat/{id}/condition/add` `condition/remove`
- `/game/combat/{id}/smite`（含 target_id）
- `/game/action`（探索阶段）
- 所有子职业能力端点（maneuver / ki / portent / lay_on_hands 等）

### 4.3 新增 WebSocket 端点

```
GET /ws/sessions/{session_id}?token=<jwt>
```

**协议**：JSON 消息

```typescript
// 服务端 → 客户端
type ServerEvent =
  | { type: "member_joined", member: SessionMember }
  | { type: "member_left",   user_id: string }
  | { type: "character_claimed", user_id: string, character_id: string }
  | { type: "ai_companions_filled", generated: number, ai_companions: AiCompanionInfo[] }
  | { type: "game_started" }
  | { type: "dm_speak_turn", user_id: string }    // 轮到谁发言
  | { type: "combat_update", state: CombatState }
  | { type: "log_appended",  log: GameLog }
  | { type: "dice_result",   user_id: string, dice: DiceResult }
  | { type: "turn_changed",  current_entity_id: string, current_user_id: string|null }
  | { type: "ping" }                              // 服务端心跳

// 客户端 → 服务端
type ClientEvent =
  | { type: "pong" }                              // 响应心跳
  | { type: "speak_done" }                        // 轮流发言：我说完了
  | { type: "typing", is_typing: boolean }
```

**广播实现**（不引入 Redis，单实例内存）：

```python
# backend/services/ws_manager.py
class WSManager:
    def __init__(self):
        self.rooms: dict[str, set[WebSocket]] = {}  # session_id -> WSs
        self.user_ws: dict[tuple[str, str], WebSocket] = {}  # (sid, uid) -> ws

    async def connect(self, session_id, user_id, ws):
        self.rooms.setdefault(session_id, set()).add(ws)
        self.user_ws[(session_id, user_id)] = ws

    async def broadcast(self, session_id, event):
        for ws in self.rooms.get(session_id, []):
            try: await ws.send_json(event)
            except: pass  # 断线由心跳协程清理
```

每个修改状态的端点（如 `/move`、`/attack-roll`）在事务提交后调用 `await ws_manager.broadcast(session_id, {"type": "combat_update", ...})`。

---

## 5. DM Agent 多人输入（轮流发言制）

### 5.1 机制
- 探索阶段维护一个"发言队列"：按 SessionMember.joined_at 顺序循环
- 服务端记录 `current_speaker_user_id` 在 `Session.game_state.multiplayer.current_speaker`
- 当前发言者通过 `/game/action` 提交一句话 → 服务端把话累积进 `pending_actions[]`
- 当前发言者按"我说完了" 按钮 → `current_speaker` 切到下一人 + WS 广播 `dm_speak_turn`
- 当所有人都说完一轮（pending_actions 长度 == 在线玩家数）→ 自动打包发给 DM Agent

### 5.2 数据结构

```python
# Session.game_state.multiplayer
{
    "current_speaker_user_id": "uuid-of-user-a",
    "speak_round": 3,                    # 当前是第几轮发言
    "pending_actions": [
        {"user_id": "...", "character_id": "...", "text": "我朝酒馆走去"},
        {"user_id": "...", "character_id": "...", "text": "我跟在他后面"},
    ],
    "online_user_ids": ["...", "...", "..."]
}
```

### 5.3 跳过机制
- 当前发言者 30 秒未行动 → 自动跳过（广播 `dm_speak_turn` 给下一人）
- 离线/AI 托管的成员自动跳过

---

## 6. 战斗回合制

### 6.1 严格按 turn_order 串行
- 当前回合归属于 `turn_order[current_turn_index].character_id`
- 该 character 的 user_id 决定"现在轮到哪个真人"
- 后端在 `assert_can_act` 中校验
- 前端按钮根据 `currentEntity.user_id === myUserId` 启用/禁用

### 6.2 AI 托管
- AI 队友（`is_player=False`）→ 调用 `/ai-turn`，复用现有逻辑
- 真人玩家断线（`last_seen_at` 超过 30 秒无心跳）→ 标记为 offline，本轮自动调用 `/ai-turn` 并传入该角色的 character_id

### 6.3 反应窗口（如借机攻击）
- 当事件触发反应（如敌人攻击），向所有相关玩家广播 `reaction_prompt` 事件
- 玩家在 5 秒内响应或放弃
- 多人同时持有反应资源时按 SessionMember.joined_at 顺序询问

> 注：本期 MVP 简化为"反应自动放弃"，反应窗口的完整实现放到阶段 B。

---

## 7. 前端变更

### 7.1 新增页面
- `pages/RoomLobby.jsx` —— 房间大厅
  - 创建房间按钮（输入模组、max_players、save_name）
  - 加入房间按钮（输入 6 位码）
  - 我的房间列表（显示房间码、成员数、状态）

- `pages/Room.jsx` —— 房间内（游戏未开始）
  - 顶部：房间码 + 复制按钮
  - 成员列表：头像、昵称、角色（未选时显示"创建角色"按钮）
  - **AI 队友分区**（紫色 ✦ AI 标签）：展示 `room.ai_companions`，含种族/职业/等级
  - 房主独占按钮：
    - 开始游戏 / 踢人 / 转让房主
    - **召唤 N 位 AI 队友**（N = `max_players - 真人数 - 已有AI数`，>0 且已有玩家认领时可见）
  - 退出房间按钮

### 7.2 改造现有页面
- `pages/Adventure.jsx`
  - 顶部增加"当前发言者"指示器
  - 自己回合时显示"我说完了"按钮
  - 输入框只在自己回合启用
  - 多人模式下不显示单人特有 UI

- `pages/Combat.jsx`
  - 增加"当前回合：玩家昵称"显示
  - 操作按钮按 `currentEntity.user_id === myUserId` 启用
  - 增加在线状态指示器（每个角色头像旁加绿/灰点）

### 7.3 WebSocket Hook

```javascript
// frontend/src/hooks/useWebSocket.js
export function useWebSocket(sessionId) {
  useEffect(() => {
    if (!sessionId) return;
    const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sessionId}?token=${token}`);
    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      // 分发到 gameStore 对应 reducer
      handleServerEvent(event);
    };
    // 心跳
    const heartbeat = setInterval(() => ws.send(JSON.stringify({type: "pong"})), 15000);
    return () => { clearInterval(heartbeat); ws.close(); };
  }, [sessionId]);
}
```

---

## 8. 安全与边界

### 8.1 权限校验三层
1. **API 层**：JWT 解析 user_id → assert_can_act
2. **WebSocket 层**：连接时验证 token + SessionMember 关系
3. **数据库层**：所有查询必带 session_id + user_id 过滤

### 8.2 房间码安全
- 6 位数字，约 100 万组合，配合 `is_multiplayer + 游戏未开始` 过滤可降低暴力枚举价值
- 游戏开始后房间码失效（无法再加入）
- 房间空置 24 小时自动归档（Session.is_multiplayer=False）

### 8.3 并发控制
- WebSocket 广播在事务提交后进行（`await db.commit()` 后再 broadcast）
- 战斗状态用 PostgreSQL 行锁防止并发修改：
  ```python
  cs = await db.execute(
      select(CombatState).where(CombatState.session_id==sid).with_for_update()
  )
  ```

---

## 9. 迁移与兼容

### 9.1 alembic 迁移脚本
新建 `backend/alembic/versions/0001_multiplayer.py`：
1. 创建 `session_members` 表
2. `sessions` 加 `room_code`, `is_multiplayer`, `host_user_id`, `max_players`
3. `characters` 加 `user_id` 外键

### 9.2 旧数据兼容
- 现有 session 默认 `is_multiplayer=False`
- 单人模式所有逻辑保持不变（路由通过 `is_multiplayer` 字段分流）
- 现有玩家角色 `user_id` 留 NULL，运行时按 `Session.user_id` 兜底

---

## 10. 实施分解（阶段 A）

| # | 任务 | 工时 |
|---|---|---|
| A1 | alembic 迁移 + 模型字段 | 0.5d |
| A2 | 房间 CRUD API（create/join/leave/start/kick/transfer/members/claim） | 1.5d |
| A3 | WebSocket 层 + WSManager + 事件协议 | 1.5d |
| A4 | 战斗端点 owner 校验 + 广播事件 | 2d |
| A5 | 前端 RoomLobby + Room 页面 | 1.5d |
| A6 | 前端 useWebSocket + Combat/Adventure 页适配 | 2d |
| A7 | 轮流发言机制（探索阶段）+ 跳过 | 1d |
| A8 | 断线检测（心跳）+ AI 托管降级 | 1d |
| A9 | 联调测试（2-4 人） | 1d |
| A10 | 文档更新（CLAUDE.md / Technical_Architecture.md / MVP_Report） | 0.5d |
| | **合计** | **12.5d** |

---

## 11. 验收标准

### 11.1 阶段 A 完成定义
- [ ] 4 人能进入同一房间，各自创建角色
- [ ] 房主开始游戏后，所有人收到第一条 DM 叙事
- [ ] 探索阶段轮流发言，DM 能正确接收所有人的输入
- [ ] 战斗中，A 投骰子的结果 B/C/D 同步看到日志和血量变化
- [ ] B 在 A 的回合点击攻击按钮被禁用 / 后端拒绝
- [ ] A 掉线 30 秒后，A 的角色由 AI 托管推进
- [ ] 房主退出后，房主转给下一位（或解散房间）
- [ ] 单人战役不受影响，所有功能正常

### 11.2 性能目标
- WebSocket 广播延迟 < 200ms
- 单实例支持 50+ 并发房间（200+ WebSocket 连接）
- 房间内事件吞吐 > 10 events/s

---

## 12. 风险与开放问题

### 12.1 已知风险
| 风险 | 缓解 |
|---|---|
| WebSocket 在 Nginx 后需配置 upgrade header | 部署文档新增 nginx WS 配置段 |
| 多人共享 LangGraph thread_id 导致记忆混乱 | 仍用 session_id 作为 thread_id（DM 视角下"队伍"是一个整体） |
| 玩家频繁加入/退出污染 messages 列表 | 加入/退出仅广播 system 事件，不进入 DM messages |
| 浏览器关闭时 WS 不主动断开 | 服务端心跳 30s 无 pong 强制清理 |

### 12.2 待阶段 B 决策
- 反应窗口 UI（借机攻击/Shield 法术等）
- 多人投票：自由探索的创造性行动是否需要队伍同意
- 队长（房主）是否拥有"重骰/跳过/长休"特权
- 队员之间的私聊（whisper）

### 12.3 待阶段 C 决策
- 房间公开列表（是否引入"找团"功能）
- 战役邀请链接（带 token，免输码）
- 文字聊天 + 表情
- 房间录像/回放

---

## 13. 依赖文件预览（即将新增/修改）

### 新增
- `doc/PRD_Multiplayer.md`（本文）
- `backend/alembic/versions/0001_multiplayer.py`
- `backend/api/rooms.py`
- `backend/api/ws.py`
- `backend/services/ws_manager.py`
- `backend/services/room_service.py`
- `frontend/src/pages/RoomLobby.jsx`
- `frontend/src/pages/Room.jsx`
- `frontend/src/hooks/useWebSocket.js`
- `frontend/src/store/wsStore.js`

### 修改
- `backend/models/session.py` — 新增字段
- `backend/models/character.py` — 加 user_id
- `backend/models/__init__.py` — 导出 SessionMember
- `backend/api/combat.py` — assert_can_act + 广播
- `backend/api/game.py` — 多人探索分流
- `backend/main.py` — 注册 rooms_router + ws_router
- `frontend/src/App.jsx` — 新增路由
- `frontend/src/api/client.js` — 新增 roomsApi
- `frontend/src/store/gameStore.js` — 多人状态字段
- `frontend/src/pages/Combat.jsx` — owner 检查 + 在线指示器
- `frontend/src/pages/Adventure.jsx` — 发言权指示器

---

## 附录 A：典型时序图（4 人战斗）

```
玩家A          玩家B          玩家C          玩家D          服务端          DM Agent
  │              │              │              │              │              │
  │── attack-roll ───────────────────────────────→             │              │
  │              │              │              │              │              │
  │←─ combat_update（dice_result, attack_total=18, hit）       │              │
  │              ←─ combat_update ─────────────────             │              │
  │                            ←─ combat_update ───             │              │
  │                                          ←─ combat_update ──             │
  │                                                            │              │
  │── damage-roll ────────────────────────────────→             │              │
  │←─ combat_update（damage=12, target_hp=8）─────              │              │
  │              ←─ combat_update ─────────────────             │              │
  │                            ←─ combat_update ───             │              │
  │                                          ←─ combat_update ──             │
  │                                                            │              │
  │── end-turn ──────────────────────────────────→              │              │
  │←─ turn_changed（current_user_id=B）────────────             │              │
  │              ←─ turn_changed ──────────────────             │              │
  │                            ←─ turn_changed ────             │              │
  │                                          ←─ turn_changed ──             │
  │                                                            │              │
  │              │── attack-roll ───────────────→               │              │
  │              ↑ 现在 B 是当前回合，按钮启用                   │              │
```

---

**PRD v0.1 完成。下一步：A1 — alembic 迁移 + 模型字段。**

---

## 修订记录

### v0.2 — 2026-04-21（多人流程打磨 / v0.10.1）

**新增**

- **POST `/game/rooms/{session_id}/fill-ai`**：房主一键按 `max_players - 真人数 - 已有AI数` 补满 AI 队友。
  - 校验：房主权限 + 游戏未开始 + ≥1 位玩家已认领角色（取其职业/种族/等级作为 party 生成参考）。
  - 实现：`services/room_service.py:fill_with_ai_companions()`，调用 `langgraph_client.generate_party`，生成的 Character 写入 DB（`is_player=False`, `user_id=None`, `session_id=房间id`）。
  - 广播：`ai_companions_filled` WS 事件，所有客户端 refresh 房间。
- **`RoomInfo.ai_companions: List[AiCompanionInfo]`**：房间信息接口额外返回该房间的 AI 队友简要信息（id/name/race/char_class/level/hp_max）。
- **`roomsApi.fillAi(sessionId)`**：前端 API 客户端方法。
- **Room.jsx** 新增"❧ AI 队友 ❧"分区 + 房主可见的"召唤 N 位 AI 队友"按钮。

**修复**

- **多人模式下角色创建向导完成后不再生成 AI 队伍**。`CharacterCreate.jsx` 通过 `useSearchParams` 读取 URL 中的 `?roomSession=xxx`，若存在则：
  - STEPS 最后一步改为"加入房间"（单人仍为"确认队伍"）。
  - 保存角色后调 `roomsApi.claimChar(sessionId, charId)` → `navigate('/room/:sessionId')`，跳过 `handleGenerateParty`。
  - 按钮文案切换为 `✦ 确认并返回房间 ✦`。
