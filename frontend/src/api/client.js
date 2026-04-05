import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 请求拦截器：自动附加 JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    // 401 = token 过期或无效 → 跳转登录
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    const msg = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

// ── 认证 ──────────────────────────────────────────────────
export const authApi = {
  register: (username, password, displayName) =>
    api.post('/auth/register', { username, password, display_name: displayName }),
  login: (username, password) =>
    api.post('/auth/login', { username, password }),
}

// ── 模组 ──────────────────────────────────────────────────
export const modulesApi = {
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/modules/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list:   () => api.get('/modules/'),
  get:    (id) => api.get(`/modules/${id}`),
  delete: (id) => api.delete(`/modules/${id}`),
}

// ── 角色 ──────────────────────────────────────────────────
export const charactersApi = {
  options:        () => api.get('/characters/options'),
  create:         (data) => api.post('/characters/create', data),
  generateParty:  (data) => api.post('/characters/generate-party', data),
  get:            (id) => api.get(`/characters/${id}`),
  prepareSpells:  (id, preparedSpells) =>
    api.patch(`/characters/${id}/prepared-spells`, { prepared_spells: preparedSpells }),
}

// ── 游戏 ──────────────────────────────────────────────────
export const gameApi = {
  // 会话管理
  createSession:  (data) => api.post('/game/sessions', data),
  listSessions:   () => api.get('/game/sessions'),
  getSession:     (id) => api.get(`/game/sessions/${id}`),
  deleteSession:  (id) => api.delete(`/game/sessions/${id}`),

  // 主行动（探索 + 战斗统一入口）
  action: (data) => api.post('/game/action', data),

  // 技能检定（本地掷骰，联动 needs_check）
  skillCheck: (data) => api.post('/game/skill-check', data),

  // 休息
  rest: (sessionId, restType = 'long') =>
    api.post(`/game/sessions/${sessionId}/rest?rest_type=${restType}`),

  // 战役档案
  saveCheckpoint: (sessionId) => api.post(`/game/sessions/${sessionId}/checkpoint`),
  getCheckpoint:  (sessionId) => api.get(`/game/sessions/${sessionId}/checkpoint`),

  // 战役日志
  generateJournal: (sessionId) => api.post(`/game/sessions/${sessionId}/journal`),

  // 战斗
  getCombat:    (sessionId) => api.get(`/game/combat/${sessionId}`),
  combatAction: (sessionId, actionText, targetId = null, isRanged = false, isOffhand = false) =>
    api.post(`/game/combat/${sessionId}/action`, {
      action_text: actionText,
      target_id:   targetId,
      is_ranged:   isRanged,
      is_offhand:  isOffhand,
    }),
  attackRoll: (sessionId, entityId, targetId, actionType = 'melee', isOffhand = false, d20Value = null) =>
    api.post(`/game/combat/${sessionId}/attack-roll`, {
      entity_id:   entityId,
      target_id:   targetId,
      action_type: actionType,
      is_offhand:  isOffhand,
      ...(d20Value != null ? { d20_value: d20Value } : {}),
    }),
  damageRoll: (sessionId, pendingAttackId, damageValues = null) =>
    api.post(`/game/combat/${sessionId}/damage-roll`, {
      pending_attack_id: pendingAttackId,
      ...(damageValues ? { damage_values: damageValues } : {}),
    }),
  aiTurn:       (sessionId) => api.post(`/game/combat/${sessionId}/ai-turn`),
  endCombat:    (sessionId) => api.post(`/game/combat/${sessionId}/end`),
  move:         (sessionId, entityId, toX, toY) =>
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
      entity_id: entityId, condition, is_enemy: isEnemy,
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

  // 神圣斩击 (Paladin Divine Smite)
  smite: (sessionId, slotLevel, targetIsUndead = false) =>
    api.post(`/game/combat/${sessionId}/smite`, {
      slot_level: slotLevel,
      target_is_undead: targetIsUndead,
    }),

  // 职业特性 (Class Features)
  classFeature: (sessionId, featureName, params = {}) =>
    api.post(`/game/combat/${sessionId}/class-feature`, {
      feature_name: featureName,
      ...params,
    }),

  // 战技 (Battle Master Maneuvers)
  maneuver: (sessionId, maneuverName, targetId) =>
    api.post(`/game/combat/${sessionId}/maneuver`, {
      maneuver_name: maneuverName,
      target_id: targetId,
    }),

  // 反应 (Reaction)
  useReaction: (sessionId, reactionType, targetId = null) =>
    api.post(`/game/combat/${sessionId}/reaction`, {
      reaction_type: reactionType,
      ...(targetId ? { target_id: targetId } : {}),
    }),

  // 擒抱/推撞 (Grapple/Shove)
  grappleShove: (sessionId, actionType, targetId, shoveType = 'prone') =>
    api.post(`/game/combat/${sessionId}/grapple-shove`, {
      action_type: actionType,
      target_id: targetId,
      shove_type: shoveType,
    }),

  // 法术列表
  getSpells:         () => api.get('/game/spells'),
  getSpellsByClass:  (cls) => api.get(`/game/spells/class/${cls}`),
}

// ── 角色额外操作 ─────────────────────────────────────────
Object.assign(charactersApi, {
  updateEquipment: (charId, equipment) =>
    api.patch(`/characters/${charId}/equipment-bulk`, { equipment }),
  levelUp: (charId, choices = {}) =>
    api.post(`/characters/${charId}/level-up`, choices),
  updateGold: (charId, amount, reason = '') =>
    api.patch(`/characters/${charId}/gold`, { amount, reason }),
  updateExhaustion: (charId, change = 1) =>
    api.patch(`/characters/${charId}/exhaustion`, { change }),
  updateAmmo: (charId, weaponName, change = -1) =>
    api.patch(`/characters/${charId}/ammo`, { weapon_name: weaponName, change }),
})
