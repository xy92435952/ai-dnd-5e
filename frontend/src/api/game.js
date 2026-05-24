import { api } from './http'

/** @typedef {import('../types/api-responses').SessionListItem} SessionListItem */
/** @typedef {import('../types/api-responses').SessionDetail} SessionDetail */
/** @typedef {import('../types/api-responses').PlayerActionResponse} PlayerActionResponse */
/** @typedef {import('../types/api-responses').SkillCheckResult} SkillCheckResult */
/** @typedef {import('../types/api-responses').SavingThrowResult} SavingThrowResult */
/** @typedef {import('../types/api-responses').RestResponse} RestResponse */
/** @typedef {import('../types/api-responses').CombatStateResponse} CombatStateResponse */
/** @typedef {import('../types/api-responses').SkillBarResponse} SkillBarResponse */

export const gameApi = {
  createSession: (data) => api.post('/game/sessions', data),

  /** @returns {Promise<SessionListItem[]>} */
  listSessions: () => api.get('/game/sessions'),

  /**
   * @param {string} id
   * @returns {Promise<SessionDetail>}
   */
  getSession: (id) => api.get(`/game/sessions/${id}`),

  deleteSession: (id) => api.delete(`/game/sessions/${id}`),

  /**
   * @param {{session_id: string, action_text: string, action_source?: 'human_input'|'ai_generated_choice'|'system_action'|'ai_takeover'}} data
   * @returns {Promise<PlayerActionResponse>}
   */
  action: (data) => api.post('/game/action', data),

  /**
   * @param {{session_id: string, action_text: string, action_source?: 'human_input'|'ai_generated_choice'|'system_action'|'ai_takeover'}} data
   * @param {{onNarrativeDelta?: (text:string) => void, onEvent?: (event:{event:string,data:any}) => void}=} handlers
   * @returns {Promise<PlayerActionResponse>}
   */
  actionStream: (data, handlers = {}) => actionStream(data, handlers),

  /**
   * @param {{session_id:string, character_id:string, skill:string, dc:number, d20_value?:number, advantage?:boolean, disadvantage?:boolean}} data
   * @returns {Promise<SkillCheckResult>}
   */
  skillCheck: (data) => api.post('/game/skill-check', data),

  /**
   * @param {{session_id:string, character_id:string, ability:'str'|'dex'|'con'|'int'|'wis'|'cha', dc:number, d20_value?:number, advantage?:boolean, disadvantage?:boolean}} data
   * @returns {Promise<SavingThrowResult>}
   */
  savingThrow: (data) => api.post('/game/saving-throw', data),

  /**
   * @param {string} sessionId
   * @param {'long'|'short'} restType
   * @returns {Promise<RestResponse>}
   */
  rest: (sessionId, restType = 'long') =>
    api.post(`/game/sessions/${sessionId}/rest?rest_type=${restType}`),

  saveCheckpoint: (sessionId) => api.post(`/game/sessions/${sessionId}/checkpoint`),
  getCheckpoint: (sessionId) => api.get(`/game/sessions/${sessionId}/checkpoint`),
  generateJournal: (sessionId) => api.post(`/game/sessions/${sessionId}/journal`),
  aiTakeover: (sessionId) => api.post(`/game/sessions/${sessionId}/ai-takeover`),

  /**
   * @param {string} sessionId
   * @returns {Promise<CombatStateResponse>}
   */
  getCombat: (sessionId) => api.get(`/game/combat/${sessionId}`),
  combatAction: (sessionId, actionText, targetId = null, isRanged = false, isOffhand = false) =>
    api.post(`/game/combat/${sessionId}/action`, {
      action_text: actionText,
      target_id: targetId,
      is_ranged: isRanged,
      is_offhand: isOffhand,
    }),
  attackRoll: (sessionId, entityId, targetId, actionType = 'melee', isOffhand = false, d20Value = null) =>
    api.post(`/game/combat/${sessionId}/attack-roll`, {
      entity_id: entityId,
      target_id: targetId,
      action_type: actionType,
      is_offhand: isOffhand,
      ...(d20Value != null ? { d20_value: d20Value } : {}),
    }),
  damageRoll: (sessionId, pendingAttackId, damageValues = null) =>
    api.post(`/game/combat/${sessionId}/damage-roll`, {
      pending_attack_id: pendingAttackId,
      ...(damageValues ? { damage_values: damageValues } : {}),
    }),
  aiTurn: (sessionId) => api.post(`/game/combat/${sessionId}/ai-turn`),
  endCombat: (sessionId) => api.post(`/game/combat/${sessionId}/end`),
  move: (sessionId, entityId, toX, toY) =>
    api.post(`/game/combat/${sessionId}/move`, { entity_id: entityId, to_x: toX, to_y: toY }),
  castSpell: (sessionId, casterId, spellName, spellLevel, targetIds) =>
    api.post(`/game/combat/${sessionId}/spell`, {
      caster_id: casterId,
      spell_name: spellName,
      spell_level: spellLevel,
      target_id: Array.isArray(targetIds) ? targetIds[0] : targetIds,
      target_ids: Array.isArray(targetIds) ? targetIds : (targetIds ? [targetIds] : []),
    }),
  spellRoll: (sessionId, casterId, spellName, spellLevel, targetId, targetIds) =>
    api.post(`/game/combat/${sessionId}/spell-roll`, {
      caster_id: casterId,
      spell_name: spellName,
      spell_level: spellLevel,
      target_id: targetId || null,
      target_ids: targetIds || [],
    }),
  spellConfirm: (sessionId, pendingSpellId, damageValues = null) =>
    api.post(`/game/combat/${sessionId}/spell-confirm`, {
      pending_spell_id: pendingSpellId,
      ...(damageValues ? { damage_values: damageValues } : {}),
    }),
  addCondition: (sessionId, entityId, condition, isEnemy = false, rounds = null) =>
    api.post(`/game/combat/${sessionId}/condition/add`, {
      entity_id: entityId,
      condition,
      is_enemy: isEnemy,
      ...(rounds != null ? { rounds } : {}),
    }),
  removeCondition: (sessionId, entityId, condition, isEnemy = false) =>
    api.post(`/game/combat/${sessionId}/condition/remove`, { entity_id: entityId, condition, is_enemy: isEnemy }),
  deathSave: (sessionId, characterId, d20Value = null) =>
    api.post(`/game/combat/${sessionId}/death-save`, {
      character_id: characterId,
      ...(d20Value != null ? { d20_value: d20Value } : {}),
    }),
  endTurn: (sessionId) =>
    api.post(`/game/combat/${sessionId}/end-turn`),
  smite: (sessionId, slotLevel, targetIsUndead = false, damageValues = null, targetId = null) =>
    api.post(`/game/combat/${sessionId}/smite`, {
      slot_level: slotLevel,
      target_is_undead: targetIsUndead,
      ...(damageValues ? { damage_values: damageValues } : {}),
      ...(targetId ? { target_id: targetId } : {}),
    }),
  classFeature: (sessionId, featureName, params = {}) =>
    api.post(`/game/combat/${sessionId}/class-feature`, {
      feature_name: featureName,
      ...params,
    }),
  maneuver: (sessionId, maneuverName, targetId) =>
    api.post(`/game/combat/${sessionId}/maneuver`, {
      maneuver_name: maneuverName,
      target_id: targetId,
    }),
  useReaction: (sessionId, reactionType, targetId = null) =>
    api.post(`/game/combat/${sessionId}/reaction`, {
      reaction_type: reactionType,
      ...(targetId ? { target_id: targetId } : {}),
    }),
  grappleShove: (sessionId, actionType, targetId, shoveType = 'prone') =>
    api.post(`/game/combat/${sessionId}/grapple-shove`, {
      action_type: actionType,
      target_id: targetId,
      shove_type: shoveType,
    }),
  getSpells: () => api.get('/game/spells'),
  getSpellsByClass: (cls) => api.get(`/game/spells/class/${cls}`),

  /**
   * @param {string} sessionId
   * @param {string=} entityId
   * @returns {Promise<SkillBarResponse>}
   */
  getSkillBar: (sessionId, entityId) =>
    api.get(`/game/combat/${sessionId}/skill-bar`, entityId ? { params: { entity_id: entityId } } : undefined),
  predict: (sessionId, attackerId, targetId, actionKey = 'atk', isRanged = false) =>
    api.post(`/game/combat/${sessionId}/predict`, {
      attacker_id: attackerId,
      target_id: targetId,
      action_key: actionKey,
      is_ranged: isRanged,
    }),
}

export function createSseParser(onEvent) {
  let buffer = ''

  const emitFrame = (frame) => {
    const lines = frame.replace(/\r\n/g, '\n').split('\n')
    let event = 'message'
    const dataLines = []
    for (const line of lines) {
      if (line.startsWith('event:')) {
        event = line.slice('event:'.length).trim() || 'message'
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice('data:'.length).trimStart())
      }
    }
    if (!event && dataLines.length === 0) return
    const rawData = dataLines.join('\n')
    let parsed = rawData
    if (rawData) {
      try {
        parsed = JSON.parse(rawData)
      } catch {
        parsed = rawData
      }
    } else {
      parsed = {}
    }
    onEvent({ event, data: parsed })
  }

  return {
    feed(chunk) {
      buffer += chunk
      buffer = buffer.replace(/\r\n/g, '\n')
      let sep = buffer.indexOf('\n\n')
      while (sep !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        if (frame.trim()) emitFrame(frame)
        sep = buffer.indexOf('\n\n')
      }
    },
    flush() {
      if (buffer.trim()) emitFrame(buffer)
      buffer = ''
    },
  }
}

async function actionStream(data, handlers = {}) {
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  const token = localStorage.getItem('token')
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch('/api/game/action/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })

  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    if (window.location.pathname !== '/login') window.location.href = '/login'
  }

  if (!res.ok) {
    let detail = `请求失败 (${res.status})`
    try {
      const body = await res.text()
      if (body) detail = JSON.parse(body).detail || body
    } catch {
      // Keep the status-based fallback.
    }
    const error = new Error(detail)
    error.status = res.status
    throw error
  }

  if (!res.body?.getReader) {
    throw new Error('当前浏览器不支持流式响应')
  }

  let finalPayload = null
  let streamError = null
  const parser = createSseParser((event) => {
    handlers.onEvent?.(event)
    if (event.event === 'narrative_delta') {
      const text = typeof event.data === 'string' ? event.data : event.data?.text
      if (text) handlers.onNarrativeDelta?.(text)
    } else if (event.event === 'final') {
      finalPayload = event.data
    } else if (event.event === 'error') {
      streamError = event.data
    }
  })

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    parser.feed(decoder.decode(value, { stream: true }))
    if (streamError) {
      await reader.cancel?.()
      break
    }
  }
  parser.feed(decoder.decode())
  parser.flush()

  if (streamError) {
    throw new Error(streamError.detail || streamError.message || 'AI响应失败')
  }
  if (!finalPayload) {
    throw new Error('流式响应缺少最终结果')
  }
  return finalPayload
}
