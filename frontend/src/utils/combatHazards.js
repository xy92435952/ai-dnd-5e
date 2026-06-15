const SAVE_ABILITY_LABELS = {
  str: '力量',
  strength: '力量',
  dex: '敏捷',
  dexterity: '敏捷',
  con: '体质',
  constitution: '体质',
  int: '智力',
  intelligence: '智力',
  wis: '感知',
  wisdom: '感知',
  cha: '魅力',
  charisma: '魅力',
}

const DAMAGE_TYPE_LABELS = {
  acid: '强酸',
  bludgeoning: '钝击',
  cold: '寒冷',
  fire: '火焰',
  force: '力场',
  lightning: '闪电',
  necrotic: '黯蚀',
  piercing: '穿刺',
  poison: '毒素',
  psychic: '心灵',
  radiant: '光耀',
  slashing: '挥砍',
  thunder: '雷鸣',
  environmental: '环境',
}

export function localizedSaveAbility(ability = '') {
  const key = String(ability || '').trim().toLowerCase()
  return SAVE_ABILITY_LABELS[key] || ability
}

export function localizedDamageType(type = '') {
  const key = String(type || '').trim().toLowerCase()
  return DAMAGE_TYPE_LABELS[key] || type
}

function finiteNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function uniqueList(values = []) {
  return [...new Set(values.filter(Boolean))]
}

function formatHazardSaveText(save = null) {
  if (!save || typeof save !== 'object') return ''
  const ability = localizedSaveAbility(save.ability)
  const total = finiteNumber(save.total)
  const dc = finiteNumber(save.dc)
  const outcome = save.success === true
    ? '成功'
    : save.success === false
      ? '失败'
      : ''
  const rollText = total !== null && dc !== null
    ? `${total} vs DC${dc}`
    : total !== null
      ? `${total}`
      : ''
  const detail = [ability ? `${ability}豁免` : '豁免', rollText, outcome]
    .filter(Boolean)
    .join(' ')
  return detail ? `，${detail}` : ''
}

function compactObject(value = {}) {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined),
  )
}

function hazardDcTrigger(hazard = {}) {
  const trigger = String(hazard.trigger || hazard.trigger_type || '').trim().toLowerCase()
  if (['turn_start', 'turn-start', 'turn_start_hazard', 'start_of_turn', 'start-of-turn'].includes(trigger)) {
    return 'turn_start_hazard'
  }
  return 'movement_hazard'
}

export function formatHazardLog(hazard = {}) {
  const target = hazard.target_name || hazard.target_id || '目标'
  const label = hazard.label || '危险地形'
  const damage = finiteNumber(hazard.final_damage ?? hazard.damage) ?? 0
  const damageType = localizedDamageType(hazard.damage_type)
  const saveText = formatHazardSaveText(hazard.saving_throw)
  const hpBefore = hazard.hp_before
  const hpAfter = hazard.hp_after
  const hpText = hpBefore != null && hpAfter != null ? `（HP ${hpBefore}→${hpAfter}）` : ''
  return `${target} 触发 ${label}${saveText}，受到 ${damage}${damageType ? ` ${damageType}` : ''}伤害${hpText}`
}

export function buildHazardDiceResult(hazard = null) {
  if (!hazard || typeof hazard !== 'object') return null
  const save = hazard.saving_throw && typeof hazard.saving_throw === 'object'
    ? hazard.saving_throw
    : null
  const rolledDamage = finiteNumber(hazard.rolled_damage ?? hazard.damage_roll?.total ?? hazard.damage)
  const finalDamage = finiteNumber(hazard.final_damage ?? hazard.damage ?? rolledDamage)
  const beforeResistance = finiteNumber(
    hazard.damage_before_resistance
      ?? hazard.damage_after_save
      ?? rolledDamage
      ?? finalDamage,
  )
  const afterResistance = finiteNumber(hazard.damage_after_resistance ?? finalDamage)
  const resistanceApplied = Boolean(hazard.resistance_applied)
    || (
      beforeResistance !== null
      && afterResistance !== null
      && beforeResistance !== afterResistance
      && hazard.damage_after_save !== undefined
    )
  const resistanceSources = uniqueList(
    Array.isArray(hazard.resistance_sources)
      ? hazard.resistance_sources
      : resistanceApplied && hazard.damage_type
        ? [hazard.damage_type]
        : [],
  )
  const targetState = compactObject({
    target_id: hazard.target_id,
    target_name: hazard.target_name,
    hp_before: hazard.hp_before,
    hp_after: hazard.hp_after,
    hp_current: hazard.hp_after,
    damage: finalDamage ?? 0,
    save: save || undefined,
  })

  return compactObject({
    type: 'hazard',
    label: hazard.label,
    trigger: hazardDcTrigger(hazard),
    terrain: hazard.terrain || 'hazard',
    cell: hazard.cell,
    damage: rolledDamage ?? finalDamage ?? 0,
    total_damage: finalDamage ?? rolledDamage ?? 0,
    damage_type: hazard.damage_type,
    damage_roll: hazard.damage_roll,
    damage_before_resistance: resistanceApplied ? beforeResistance : undefined,
    damage_after_resistance: resistanceApplied ? afterResistance : undefined,
    resistance_applied: resistanceApplied || undefined,
    resistance_sources: resistanceSources.length ? resistanceSources : undefined,
    saving_throw: save || undefined,
    save_success: hazard.save_success ?? save?.success,
    dc_source: save?.dc || hazard.save_dc ? compactObject({
      type: 'environment',
      label: hazard.label || '危险地形',
      ability: save?.ability || hazard.save_ability,
      dc: save?.dc || hazard.save_dc,
      trigger: hazardDcTrigger(hazard),
    }) : undefined,
    hazard,
    target_state: Object.keys(targetState).length ? targetState : undefined,
  })
}
