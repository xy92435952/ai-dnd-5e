/**
 * frontend/src/types/ws.d.ts
 *
 * WebSocket 事件的 TypeScript 类型声明。
 * 和后端 schemas/ws_events.py 严格一一对应，**改一处必改两处**。
 *
 * 用法（在 .jsx 文件里吃到类型提示）：
 *   \@param {import('../types/ws').WSEvent} event
 *   function onWsEvent(event) { ... }
 *
 * VSCode / IDE 看到 JSDoc 就会根据这里的类型做 switch 穷举检查。
 */

// ─── 房间成员 ───────────────────────────────────────────

export interface Member {
  user_id: string
  username?: string
  display_name?: string
  role?: 'host' | 'player' | string
  character_id?: string | null
  character_name?: string | null
  is_online?: boolean
}

// ─── 房间管理 ───────────────────────────────────────────

export interface MemberJoined {
  type: 'member_joined'
  user_id: string
  members: Member[]
}

export interface MemberLeft {
  type: 'member_left'
  user_id: string
  host_transferred_to: string | null
  members: Member[]
}

export interface RoomDissolved {
  type: 'room_dissolved'
  by_user_id: string
}

export interface GameStarted {
  type: 'game_started'
  current_speaker_user_id: string | null
}

export interface AiCompanionsFilled {
  type: 'ai_companions_filled'
  generated: number
  ai_companions: unknown[]
}

export interface MemberKicked {
  type: 'member_kicked'
  user_id: string
  by_user_id: string
  members: Member[]
}

export interface HostTransferred {
  type: 'host_transferred'
  new_host_user_id: string
}

export interface CharacterClaimed {
  type: 'character_claimed'
  user_id: string
  character_id: string
  members: Member[]
}

// ─── 在线 / 打字 ─────────────────────────────────────────

export interface MemberOnline {
  type: 'member_online'
  user_id: string
}

export interface MemberOffline {
  type: 'member_offline'
  user_id: string
}

export interface Typing {
  type: 'typing'
  user_id: string
  is_typing: boolean
}

// ─── DM 流程 ─────────────────────────────────────────────

export interface DMThinkingStart {
  type: 'dm_thinking_start'
  by_user_id: string
  action_text: string
}

export interface DMResponded {
  type: 'dm_responded'
  by_user_id: string
  action_type: string
  narrative: string
  companion_reactions: string
  dice_display: unknown[]
  combat_triggered: boolean
  combat_ended: boolean
}

export interface DMSpeakTurn {
  type: 'dm_speak_turn'
  user_id: string
  auto: boolean
}

// ─── 战斗 ────────────────────────────────────────────────

export interface CombatUpdate {
  type: 'combat_update'
  combat: unknown | null
  current_entity_id: string | null
}

export interface TurnChanged {
  type: 'turn_changed'
  combat: unknown | null
  current_entity_id: string | null
  round_number: number
  next_turn_index: number
}

export interface EntityMoved {
  type: 'entity_moved'
  combat: unknown | null
  current_entity_id: string | null
  entity_id: string
  position: { x: number; y: number }
}

// ─── 判别联合（tagged union） ────────────────────────────

export type WSEvent =
  | MemberJoined
  | MemberLeft
  | RoomDissolved
  | GameStarted
  | AiCompanionsFilled
  | MemberKicked
  | HostTransferred
  | CharacterClaimed
  | MemberOnline
  | MemberOffline
  | Typing
  | DMThinkingStart
  | DMResponded
  | DMSpeakTurn
  | CombatUpdate
  | TurnChanged
  | EntityMoved

/** 所有可能出现的 WSEvent['type'] 字面量。 */
export type WSEventType = WSEvent['type']
