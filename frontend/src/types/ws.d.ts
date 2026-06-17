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
  seconds_since_seen?: number | null
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

export interface WSError {
  type: 'error'
  code: string
  message: string
}

// ─── DM 流程 ─────────────────────────────────────────────

export interface DMThinkingStart {
  type: 'dm_thinking_start'
  by_user_id: string
  action_text: string
  redacted?: boolean
  visibility?: 'other_group' | string
  group_id?: string | null
  started_at?: string
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
  table_reason?: string
  table_decision?: {
    decision?: string
    reason_code?: string
    target_group_id?: string | null
    waiting_group_id?: string | null
    actor_group_id?: string | null
    focus_group_id?: string | null
    knowledge_scope?: string
  }
  visibility?: {
    scope?: 'party' | 'group' | 'private' | string
    group_id?: string | null
    visible_to_user_ids?: string[]
  }
}

export interface DMSpeakTurn {
  type: 'dm_speak_turn'
  user_id: string
  auto: boolean
}

export interface RoomStateUpdated {
  type: 'room_state_updated'
  room: unknown
}

export interface ExplorationReactionPrompt {
  type: 'exploration_reaction_prompt'
  prompt: Record<string, unknown>
}

// ─── 战斗 ────────────────────────────────────────────────

export interface CombatUpdate {
  type: 'combat_update'
  combat: unknown | null
  current_entity_id: string | null
  combat_over?: boolean | null
  outcome?: string | null
  actor_id?: string | null
  actor_name?: string | null
  narration?: string | null
  action?: string | null
  reaction_type?: string | null
  reaction_effect?: Record<string, unknown> | null
  next_turn_index?: number | null
  round_number?: number | null
  target_id?: string | null
  target_name?: string | null
  target_new_hp?: number | null
  target_state?: Record<string, unknown> | null
  condition?: string | null
  condition_action?: string | null
  condition_result?: Record<string, unknown> | null
  inspect_result?: Record<string, unknown> | null
  actor_state?: Record<string, unknown> | null
  caster_state?: Record<string, unknown> | null
  entity_positions?: Record<string, unknown> | null
  player_targeted?: boolean
  attack_result?: Record<string, unknown> | null
  damage?: number | null
  heal?: number | null
  total_damage?: number | null
  damage_roll?: Record<string, unknown> | null
  damage_type?: string | null
  damage_before_resistance?: number | null
  damage_after_resistance?: number | null
  resistance_applied?: boolean | null
  resistance_sources?: string[]
  crit_extra?: number | null
  sneak_attack?: boolean | null
  sneak_attack_damage?: number | null
  extra_damage_notes?: string[]
  defender_interception?: Record<string, unknown> | null
  weapon_resource?: Record<string, unknown> | null
  weapon_resources?: Record<string, unknown>[]
  enemy_action?: Record<string, unknown> | null
  enemy_actions?: Record<string, unknown>[]
  tactical_decision?: Record<string, unknown> | null
  dice_result?: Record<string, unknown> | null
  spell_result?: Record<string, unknown> | null
  special_action?: Record<string, unknown> | null
  ready_action?: Record<string, unknown> | null
  save?: Record<string, unknown> | null
  target_results?: Record<string, unknown>[]
  aoe_results?: Record<string, unknown>[]
  resurrection_results?: Record<string, unknown>[]
  concentration_effect_updates?: Record<string, unknown>[]
  concentration_started?: boolean | null
  concentration_ended?: boolean | null
  ready_action_failed?: Record<string, unknown> | null
  remaining_slots?: Record<string, unknown> | null
  dc_source?: Record<string, unknown> | null
  concentration_check?: Record<string, unknown> | null
  concentration_checks?: Record<string, unknown>[]
  wild_magic_surge?: Record<string, unknown> | null
  wild_magic_check?: Record<string, unknown> | null
  skirmisher_reposition?: Record<string, unknown> | null
  confusion_turn?: Record<string, unknown> | null
  player_can_react?: boolean
  reaction_prompt?: Record<string, unknown> | null
  lair_action_prompt?: Record<string, unknown> | null
  legendary_action_prompt?: Record<string, unknown> | null
  lair_action?: Record<string, unknown> | null
  legendary_action?: Record<string, unknown> | null
  ready_action_results?: Record<string, unknown>[]
  opportunity_attacks?: Record<string, unknown>[]
  expired_ready_action?: Record<string, unknown> | null
  ready_action_expired_log?: string | null
  confusion_end_save?: Record<string, unknown> | null
  condition_end_saves?: Record<string, unknown>[]
  turn_start_hazard?: Record<string, unknown> | null
  turn_start_hazard_log?: string | null
}

export interface TurnChanged {
  type: 'turn_changed'
  combat: unknown | null
  current_entity_id: string | null
  round_number: number
  next_turn_index: number
  player_can_react?: boolean
  reaction_prompt?: Record<string, unknown> | null
  lair_action_prompt?: Record<string, unknown> | null
  legendary_action_prompt?: Record<string, unknown> | null
  turn_order_delayed?: boolean
  delayed_turn?: Record<string, unknown> | null
}

export interface EntityMoved {
  type: 'entity_moved'
  combat: unknown | null
  current_entity_id: string | null
  entity_id: string
  position: { x: number; y: number }
  narration?: string | null
  movement?: Record<string, unknown> | null
  dice_result?: Record<string, unknown> | null
  special_action?: Record<string, unknown> | null
  combat_over?: boolean | null
  outcome?: string | null
  ready_action_results?: Record<string, unknown>[]
  opportunity_attacks?: Record<string, unknown>[]
  hazard_result?: Record<string, unknown> | null
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
  | WSError
  | DMThinkingStart
  | DMResponded
  | DMSpeakTurn
  | RoomStateUpdated
  | ExplorationReactionPrompt
  | CombatUpdate
  | TurnChanged
  | EntityMoved

/** 所有可能出现的 WSEvent['type'] 字面量。 */
export type WSEventType = WSEvent['type']
