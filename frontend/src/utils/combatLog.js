const ROLE_LABELS = {
  player: '玩家',
  enemy: '敌人',
  system: '系统',
}

const SLOT_LABELS = {
  '1st': '1环',
  '2nd': '2环',
  '3rd': '3环',
  '4th': '4环',
  '5th': '5环',
  '6th': '6环',
  '7th': '7环',
  '8th': '8环',
  '9th': '9环',
}

function isFiniteNumber(value) {
  return Number.isFinite(Number(value))
}

function asNumber(value) {
  return isFiniteNumber(value) ? Number(value) : null
}

function compact(items) {
  return items.filter(item => item !== null && item !== undefined && item !== '')
}

function formatSigned(value) {
  const number = asNumber(value)
  if (number === null) return ''
  return number >= 0 ? `+${number}` : `${number}`
}

function resolveRoleLabel(role = '') {
  if (role?.startsWith('companion_')) return '队友'
  return ROLE_LABELS[role] || '日志'
}

function formatAttackRule(attack = {}) {
  if (!attack || typeof attack !== 'object') return null
  const total = asNumber(attack.attack_total ?? attack.total)
  const targetAc = asNumber(attack.target_ac ?? attack.ac)
  const outcome = attack.is_crit
    ? '暴击命中'
    : attack.is_fumble
      ? '大失手'
      : attack.hit
        ? '命中'
        : '未命中'
  const compare = total !== null && targetAc !== null ? `${total} vs AC${targetAc}` : ''
  return compact([outcome, compare]).join(' · ')
}

function formatAttackDice(attack = {}) {
  if (!attack || typeof attack !== 'object') return null
  const d20 = asNumber(attack.d20 ?? attack.roll)
  const total = asNumber(attack.attack_total ?? attack.total)
  const explicitBonus = asNumber(attack.attack_bonus ?? attack.bonus)
  const inferredBonus = d20 !== null && total !== null ? total - d20 : null
  const bonus = explicitBonus !== null ? explicitBonus : inferredBonus

  if (d20 === null && total === null) return null
  if (d20 !== null && total !== null && bonus !== null) {
    return `d20 ${d20} ${formatSigned(bonus)} = ${total}`
  }
  if (d20 !== null) return `d20 ${d20}`
  return `攻击总值 ${total}`
}

function formatDamageValue(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'object') {
    const total = value.total ?? value.damage ?? value.amount
    return total !== null && total !== undefined ? `${total}` : null
  }
  return `${value}`
}

function formatDeathSaveDice(dice = {}) {
  if (dice?.type !== 'death_save') return null
  const d20 = asNumber(dice.d20)
  return d20 !== null ? `死亡豁免 d20 ${d20}` : null
}

function formatGenericDice(dice = {}) {
  if (!dice || typeof dice !== 'object') return []
  const entries = []

  if (dice.type === 'maneuver' && dice.value !== undefined) {
    entries.push(`战技骰 ${dice.value}${dice.die ? ` (${dice.die})` : ''}`)
  }

  if (dice.type === 'wild_magic_surge' && dice.d20 !== undefined) {
    entries.push(`野蛮魔法 d20 ${dice.d20}`)
  }

  const deathSave = formatDeathSaveDice(dice)
  if (deathSave) entries.push(deathSave)

  if (!entries.length && dice.d20 !== undefined && !dice.attack) {
    entries.push(`d20 ${dice.d20}`)
  }
  if (!entries.length && dice.total !== undefined && !dice.attack) {
    entries.push(`总计 ${dice.total}`)
  }

  return entries
}

function buildDiceSections(dice = null) {
  if (!dice || typeof dice !== 'object') return []
  const entries = []
  const attackDice = formatAttackDice(dice.attack)
  if (attackDice) entries.push(attackDice)

  const damage = formatDamageValue(dice.damage)
  if (damage !== null) entries.push(`伤害 ${damage}`)

  const totalDamage = formatDamageValue(dice.total_damage)
  if (totalDamage !== null && totalDamage !== damage) {
    entries.push(`实际伤害 ${totalDamage}`)
  }

  return [...entries, ...formatGenericDice(dice)]
}

function normalizeStateChanges(raw = null) {
  if (!raw) return []
  if (Array.isArray(raw)) {
    return raw.flatMap(item => normalizeStateChanges(item))
  }
  if (typeof raw === 'string') return [raw]
  if (typeof raw !== 'object') return []

  const entries = []
  if (Array.isArray(raw.entries)) entries.push(...raw.entries)
  if (raw.hp) entries.push(...normalizeHpState(raw.hp))
  if (Array.isArray(raw.hp_updates)) {
    raw.hp_updates.forEach(update => entries.push(...normalizeHpState(update)))
  }
  if (Array.isArray(raw.resources)) {
    raw.resources.forEach(resource => {
      if (typeof resource === 'string') entries.push(resource)
      else if (resource?.label && resource?.value) entries.push(`${resource.label} ${resource.value}`)
    })
  }
  if (Array.isArray(raw.status)) entries.push(...raw.status)
  return compact(entries)
}

function normalizeHpState(hp = {}) {
  if (!hp || typeof hp !== 'object') return []
  const label = hp.target || hp.name || hp.target_id || '目标'
  const before = hp.before ?? hp.hp_before
  const after = hp.after ?? hp.hp_after ?? hp.hp_current
  if (after === null || after === undefined) return []
  if (before !== null && before !== undefined) return [`${label} HP ${before} -> ${after}`]
  return [`${label} HP ${after}`]
}

function formatSlots(slots = {}) {
  return Object.entries(slots)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([level, count]) => `${SLOT_LABELS[level] || level} ${count}`)
    .join('，')
}

function summarizeTurnState(turnState = null) {
  if (!turnState || typeof turnState !== 'object') return null
  const parts = []
  if (turnState.action_used) parts.push('动作已用')
  if (turnState.bonus_action_used) parts.push('附赠动作已用')
  if (turnState.reaction_used) parts.push('反应已用')
  if (turnState.attacks_made !== undefined && turnState.attacks_max !== undefined) {
    parts.push(`攻击 ${turnState.attacks_made}/${turnState.attacks_max}`)
  }
  if (turnState.movement_used !== undefined && turnState.movement_max !== undefined) {
    const remaining = Math.max(0, Number(turnState.movement_max) - Number(turnState.movement_used))
    parts.push(`移动剩余 ${remaining}/${turnState.movement_max}`)
  }
  return parts.length ? parts.join('，') : null
}

function summarizeDeathSaves(saves = null) {
  if (!saves || typeof saves !== 'object') return null
  const successes = saves.successes ?? 0
  const failures = saves.failures ?? 0
  return `死亡豁免 成功 ${successes}/3，失败 ${failures}/3`
}

function summarizeConditions(conditions = null) {
  if (!Array.isArray(conditions) || !conditions.length) return null
  return `状态 ${conditions.join('、')}`
}

function targetLabelFrom(result = {}, options = {}) {
  return options.targetName
    || result.target_name
    || result.character_name
    || result.target_state?.name
    || result.target_state?.target_name
    || result.target_id
    || result.character_id
    || '目标'
}

function hpBeforeFrom(result = {}, options = {}) {
  return options.hpBefore
    ?? result.hp_before
    ?? result.target_hp_before_damage
    ?? result.target_state?.hp_before
    ?? result.target_state?.hp_before_damage
    ?? null
}

function hpAfterFrom(result = {}) {
  return result.target_state?.hp_current
    ?? result.target_state?.new_hp
    ?? result.target_state?.hp_after
    ?? result.hp_after
    ?? result.hp_current
    ?? result.target_new_hp
    ?? null
}

function summarizeTargetResult(result = {}, options = {}) {
  const after = hpAfterFrom(result)
  if (after === null || after === undefined) return []
  return normalizeHpState({
    target: targetLabelFrom(result, options),
    before: hpBeforeFrom(result, options),
    after,
  })
}

function summarizeWeaponResource(resource = null) {
  if (!resource?.consumed || !resource.weapon) return null
  if (resource.resource_type === 'ammunition') {
    const remaining = resource.ammo_remaining ?? resource.ammo
    return remaining !== null && remaining !== undefined
      ? `${resource.weapon} 弹药剩余 ${remaining}`
      : `${resource.weapon} 弹药 -1`
  }
  if (resource.resource_type === 'thrown_weapon') return `投出 ${resource.weapon}`
  return null
}

export function buildCombatStateChangeSummary(result = {}, options = {}) {
  if (!result || typeof result !== 'object') return []

  const entries = [
    ...summarizeTargetResult(result, options),
  ]

  const resultGroups = [
    result.aoe_results,
    result.target_results,
    result.resurrection_results,
  ]
  resultGroups.forEach(group => {
    if (!Array.isArray(group)) return
    group.forEach(item => {
      entries.push(...summarizeTargetResult(item))
    })
  })

  const saves = result.death_saves || result.target_state?.death_saves
  entries.push(summarizeDeathSaves(saves))
  entries.push(summarizeConditions(result.conditions || result.target_state?.conditions))

  const slots = result.remaining_slots ? formatSlots(result.remaining_slots) : ''
  if (slots) entries.push(`法术位剩余 ${slots}`)

  entries.push(summarizeWeaponResource(result.weapon_resource))
  entries.push(summarizeTurnState(result.turn_state))

  if (result.concentration_check?.broke) {
    entries.push(`专注中断${result.concentration_check.spell_name ? `：${result.concentration_check.spell_name}` : ''}`)
  }
  if (result.combat_over) entries.push('战斗结束')

  return [...new Set(compact(entries))]
}

export function buildCombatLogView(log = {}) {
  const dice = log.dice_result || null
  const rules = compact([
    log.rule_result,
    formatAttackRule(dice?.attack),
  ])
  const diceEntries = buildDiceSections(dice)
  const state = normalizeStateChanges(log.state_changes)
  const narration = log.content ? [log.content] : []
  const attack = dice?.attack || {}

  const tone = attack.is_crit
    ? 'crit'
    : attack.is_fumble || attack.hit === false
      ? 'miss'
      : log.log_type === 'combat'
        ? 'dmg'
        : log.log_type === 'dice'
          ? 'dice'
          : log.log_type === 'system'
            ? 'system'
            : 'normal'

  return {
    tone,
    roleLabel: resolveRoleLabel(log.role),
    sections: compact([
      rules.length ? { kind: 'rules', label: '规则', items: rules } : null,
      diceEntries.length ? { kind: 'dice', label: '骰子', items: diceEntries } : null,
      narration.length ? { kind: 'narration', label: '叙事', items: narration } : null,
      state.length ? { kind: 'state', label: '状态', items: state } : null,
    ]),
  }
}
