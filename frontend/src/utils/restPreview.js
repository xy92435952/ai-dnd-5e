const LONG_REST_REDUCED_CONDITIONS = new Set([
  'exhaustion',
  'poisoned',
  'frightened',
  'charmed',
  'unconscious',
  'stunned',
  'restrained',
  'grappled',
  'prone',
  'incapacitated',
  'paralyzed',
])

const PACT_CLASSES = ['warlock', '邪术师']

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function toClassKey(value = '') {
  return String(value || '').trim().toLowerCase()
}

function getHpMax(character) {
  const derived = asObject(character?.derived)
  return character?.hp_max ?? derived.hp_max ?? character?.hp_current ?? 0
}

function getSlotRestores(character, restType) {
  const derived = asObject(character?.derived)
  const maxSlots = asObject(derived.spell_slots_max)
  const currentSlots = asObject(character?.spell_slots)
  if (Object.keys(maxSlots).length === 0) return []

  const classKey = toClassKey(character?.char_class)
  const isPactCaster = PACT_CLASSES.some(cls => classKey.includes(cls)) || derived.caster_type === 'pact'
  if (restType === 'short' && !isPactCaster) return []

  return Object.entries(maxSlots)
    .map(([level, maxValue]) => {
      const max = Number(maxValue || 0)
      const current = Number(currentSlots[level] ?? max)
      const restore = Math.max(0, max - current)
      return restore > 0 ? `${level}+${restore}` : null
    })
    .filter(Boolean)
}

function getLongRestConditionChanges(character) {
  const conditions = Array.isArray(character?.conditions) ? character.conditions : []
  return conditions.filter(condition => LONG_REST_REDUCED_CONDITIONS.has(condition))
}

function hasDeathSaves(character) {
  const saves = asObject(character?.death_saves)
  return Object.keys(saves).length > 0
}

export function buildRestPreview(characters = [], restType = 'long') {
  return (Array.isArray(characters) ? characters : []).map(character => {
    const hpCurrent = Number(character?.hp_current ?? 0)
    const hpMax = Number(getHpMax(character) || 0)
    const hitDiceRemaining = character?.hit_dice_remaining ?? character?.level ?? null
    const hitDiceTotal = character?.level ?? hitDiceRemaining
    const missingHp = Math.max(0, hpMax - hpCurrent)
    const slotRestores = getSlotRestores(character, restType)
    const conditionChanges = restType === 'long' ? getLongRestConditionChanges(character) : []

    const effects = []
    if (restType === 'long') {
      if (missingHp > 0) {
        effects.push(`HP 恢复到 ${hpMax}/${hpMax}`)
      } else {
        effects.push('HP 已满')
      }
      if (slotRestores.length > 0) effects.push(`法术位 ${slotRestores.join('/')}`)
      if (hitDiceRemaining != null && hitDiceTotal != null && Number(hitDiceRemaining) < Number(hitDiceTotal)) {
        effects.push('恢复部分生命骰')
      }
      if (conditionChanges.length > 0) effects.push(`尝试移除 ${conditionChanges.join('/')}`)
      if (hasDeathSaves(character)) effects.push('重置濒死豁免')
    } else {
      if (missingHp > 0 && Number(hitDiceRemaining || 0) > 0) {
        effects.push(`可消耗生命骰恢复 HP（缺 ${missingHp}）`)
      } else if (missingHp > 0) {
        effects.push(`HP 缺 ${missingHp}，但生命骰不足`)
      } else {
        effects.push('HP 已满，通常不消耗生命骰')
      }
      if (slotRestores.length > 0) effects.push(`魔契法术位 ${slotRestores.join('/')}`)
    }

    if (effects.length === 0) effects.push('暂无明显恢复项')

    return {
      id: character?.id || character?.name,
      name: character?.name || '未知角色',
      hpCurrent,
      hpMax,
      missingHp,
      hitDiceRemaining,
      hitDiceTotal,
      slotRestores,
      conditionChanges,
      effects,
    }
  })
}

export function summarizeRestPreview(characters = [], restType = 'long') {
  const previews = buildRestPreview(characters, restType)
  const wounded = previews.filter(item => item.missingHp > 0).length
  const slotUsers = previews.filter(item => item.slotRestores.length > 0).length
  const conditions = previews.reduce((sum, item) => sum + item.conditionChanges.length, 0)
  const hitDiceRisk = restType === 'short'
    ? previews.filter(item => item.missingHp > 0 && Number(item.hitDiceRemaining || 0) <= 0).length
    : 0

  return {
    previews,
    wounded,
    slotUsers,
    conditions,
    hitDiceRisk,
  }
}
