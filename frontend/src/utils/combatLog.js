import { buildHazardDiceResult, localizedDamageType, localizedSaveAbility } from './combatHazards'

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
  const hasOutcome = attack.is_crit || attack.is_fumble || attack.hit === true || attack.hit === false
  if (!hasOutcome && total === null && targetAc === null) return null
  const outcome = attack.is_crit
    ? '暴击命中'
    : attack.is_fumble
      ? '大失手'
      : attack.hit === true
        ? '命中'
        : attack.hit === false
          ? '未命中'
          : null
  const compare = total !== null && targetAc !== null ? `${total} vs AC${targetAc}` : ''
  return compact([outcome, compare]).join(' · ')
}

function formatDefenderInterception(interception = null) {
  if (!interception || typeof interception !== 'object') return null
  const defenderName = interception.defender_name || interception.defender_id || '敌方护卫'
  const protectedName = interception.protected_target_name || interception.protected_target_id
  const targetText = protectedName ? `保护 ${protectedName}，` : ''
  return `${defenderName} 护卫干扰：${targetText}本次攻击劣势`
}

function formatCuttingWordsRule(source = null) {
  if (!source || typeof source !== 'object') return null
  const effect = source
  const cutting = effect.cutting_words || effect
  const hasCuttingWords = (
    cutting?.type === 'cutting_words'
    || cutting?.die !== undefined
    || cutting?.roll !== undefined
    || effect.attack_total_before !== undefined
    || effect.damage_roll_before !== undefined
    || effect.check_total_before !== undefined
  )
  if (!hasCuttingWords) return null

  const die = cutting?.die
  const roll = cutting?.roll
  const rollText = die && roll !== undefined
    ? `${die}=${roll}`
    : roll !== undefined
      ? `roll ${roll}`
      : 'applied'
  const prefix = `Cutting Words ${rollText}:`

  const attackBefore = asNumber(effect.attack_total_before)
  const attackAfter = asNumber(effect.attack_total_after)
  if (attackBefore !== null && attackAfter !== null) {
    const targetAc = asNumber(effect.target_ac)
    const blocked = effect.blocked_attack ? '; hit blocked' : effect.hit_after === false ? '; now misses' : ''
    return `${prefix} attack ${attackBefore} -> ${attackAfter}${targetAc !== null ? ` vs AC${targetAc}` : ''}${blocked}`
  }

  const damageBefore = asNumber(effect.damage_roll_before ?? effect.original_damage)
  const damageAfter = asNumber(effect.damage_roll_after ?? effect.reduced_damage)
  if (damageBefore !== null && damageAfter !== null) {
    const prevented = asNumber(effect.damage_prevented)
    return `${prefix} damage ${damageBefore} -> ${damageAfter}${prevented !== null ? `; prevented ${prevented}` : ''}`
  }

  const checkBefore = asNumber(effect.check_total_before)
  const checkAfter = asNumber(effect.check_total_after)
  if (checkBefore !== null && checkAfter !== null) {
    const prevented = asNumber(effect.check_prevented)
    return `${prefix} check ${checkBefore} -> ${checkAfter}${prevented !== null ? `; prevented ${prevented}` : ''}`
  }

  return null
}

function formatReactionPreventionRule(effect = null) {
  if (!effect || typeof effect !== 'object') return null
  const cutting = formatCuttingWordsRule(effect)
  if (cutting) return cutting
  const prevented = asNumber(effect.damage_prevented)
  const restored = asNumber(effect.hp_restored)
  if (prevented === null) return null
  return compact([
    `prevented ${prevented} damage`,
    restored !== null && restored > 0 ? `restored ${restored} HP` : null,
  ]).join('; ').replace(/^/, 'Reaction: ')
}

function formatContestRule(dice = {}) {
  if (!dice || typeof dice !== 'object') return null
  if (!['grapple', 'shove', 'grapple_escape'].includes(dice.type)) return null
  const attackRoll = dice.type === 'grapple_escape'
    ? asNumber(dice.actor_roll?.total)
    : asNumber(dice.attacker_roll?.total)
  const targetRoll = dice.type === 'grapple_escape'
    ? asNumber(dice.source_roll?.total)
    : asNumber(dice.target_roll?.total)
  if (attackRoll === null || targetRoll === null) return null
  const label = dice.type === 'shove'
    ? 'Shove'
    : dice.type === 'grapple_escape'
      ? 'Grapple escape'
      : 'Grapple'
  const outcome = dice.success === true ? 'success' : dice.success === false ? 'failure' : ''
  const actorLabel = dice.type === 'grapple_escape' ? 'actor' : 'attacker'
  const targetLabel = dice.type === 'grapple_escape' ? 'source' : 'target'
  return compact([`${label} contest: ${actorLabel} ${attackRoll} vs ${targetLabel} ${targetRoll}`, outcome]).join('; ')
}

function normalizeHazardTrigger(trigger = '') {
  const key = String(trigger || '').trim().toLowerCase()
  if (['turn_start', 'turn-start', 'turn_start_hazard', 'start_of_turn', 'start-of-turn'].includes(key)) {
    return 'turn_start_hazard'
  }
  if (['movement_hazard', 'enter', 'enter_hazard', 'movement', 'move'].includes(key)) {
    return 'movement_hazard'
  }
  return key || 'movement_hazard'
}

function hazardTriggerLabel(trigger = '') {
  return normalizeHazardTrigger(trigger) === 'turn_start_hazard'
    ? '回合开始触发'
    : '进入触发'
}

function normalizeHazardDice(dice = null) {
  if (!dice || typeof dice !== 'object') return null
  if (dice.type === 'hazard') return dice
  if (!dice.hazard || typeof dice.hazard !== 'object') return null
  return buildHazardDiceResult(dice.hazard)
}

function formatHazardDcRule(dice = null) {
  const hazard = normalizeHazardDice(dice)
  if (!hazard) return null
  const source = hazard.dc_source || {}
  const save = hazard.saving_throw || {}
  const dc = asNumber(source.dc ?? save.dc)
  if (dc === null) return null
  const label = source.label || hazard.label || '危险地形'
  const ability = localizedSaveAbility(source.ability || save.ability || hazard.save_ability)
  return compact([
    '环境DC',
    label,
    ability ? `${ability}豁免` : '豁免',
    `DC${dc}`,
    hazardTriggerLabel(source.trigger || hazard.trigger),
  ]).join(' · ')
}

function formatHazardDamageAdjustmentRule(dice = null) {
  const hazard = normalizeHazardDice(dice)
  if (!hazard?.resistance_applied) return null
  const before = asNumber(hazard.damage_before_resistance)
  const after = asNumber(hazard.damage_after_resistance ?? hazard.total_damage)
  if (before === null || after === null || before === after) return null
  const damageType = localizedDamageType(hazard.damage_type) || '伤害'
  const label = after === 0 && before > after
    ? `${damageType}免疫伤害`
    : after < before
      ? `${damageType}抗性减伤`
      : `${damageType}易伤增伤`
  return compact([label, damageType, `${before} -> ${after}`]).join(' · ')
}

function formatHazardRules(dice = null) {
  return compact([
    formatHazardDamageAdjustmentRule(dice),
    formatHazardDcRule(dice),
  ])
}

function formatHazardSaveDice(dice = null) {
  const hazard = normalizeHazardDice(dice)
  const save = hazard?.saving_throw
  if (!save || typeof save !== 'object') return null
  const target = hazard.target_state?.target_name || hazard.target_name || hazard.target_id || '目标'
  const ability = localizedSaveAbility(save.ability || hazard.save_ability)
  const d20 = asNumber(save.d20)
  const total = asNumber(save.total)
  const explicitModifier = asNumber(save.modifier ?? save.bonus)
  const modifier = explicitModifier !== null
    ? explicitModifier
    : d20 !== null && total !== null
      ? total - d20
      : null
  const dc = asNumber(save.dc ?? hazard.dc_source?.dc)
  const rollText = d20 !== null && total !== null
    ? `d20 ${d20}${modifier !== null ? ` ${formatSigned(modifier)}` : ''} = ${total}`
    : total !== null
      ? `${total}`
      : null
  const outcome = save.success === true
    ? '成功'
    : save.success === false
      ? '失败'
      : ''
  return compact([
    target,
    ability ? `${ability}豁免` : '豁免',
    rollText,
    dc !== null ? `vs DC${dc}` : null,
    outcome ? `→ ${outcome}` : null,
  ]).join(' ')
}

function formatHazardDamageRollDice(dice = null) {
  const hazard = normalizeHazardDice(dice)
  const roll = hazard?.damage_roll
  if (!roll || typeof roll !== 'object') return null
  const total = asNumber(roll.total)
  if (total === null) return null
  const notation = roll.notation || hazard.damage_dice || '伤害骰'
  const damageType = localizedDamageType(hazard.damage_type)
  return `伤害骰 ${notation} = ${total}${damageType ? ` ${damageType}` : ''}`
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
  const displayDice = normalizeHazardDice(dice) || dice
  const entries = []
  const hazardSave = formatHazardSaveDice(displayDice)
  if (hazardSave) entries.push(hazardSave)

  const hazardDamageRoll = formatHazardDamageRollDice(displayDice)
  if (hazardDamageRoll) entries.push(hazardDamageRoll)

  const attackDice = formatAttackDice(displayDice.attack)
  if (attackDice) entries.push(attackDice)

  const damage = formatDamageValue(displayDice.damage)
  if (damage !== null) entries.push(`伤害 ${damage}`)

  const totalDamage = formatDamageValue(displayDice.total_damage)
  if (totalDamage !== null && totalDamage !== damage) {
    entries.push(`实际伤害 ${totalDamage}`)
  }

  return [...entries, ...formatGenericDice(displayDice)]
}

function buildAttackFeedback(attack = {}) {
  if (!attack || typeof attack !== 'object') return null
  if (attack.is_crit) return { kind: 'crit', label: '暴击' }
  if (attack.is_fumble) return { kind: 'miss', label: '大失手' }
  if (attack.hit === false) return { kind: 'miss', label: '未命中' }
  if (attack.hit === true) return { kind: 'hit', label: '命中' }
  return null
}

function readSaveSuccess(dice = {}) {
  if (!dice || typeof dice !== 'object') return null
  if (dice.save_success !== undefined) return Boolean(dice.save_success)
  if (dice.save_result?.success !== undefined) return Boolean(dice.save_result.success)
  if (dice.saving_throw?.success !== undefined) return Boolean(dice.saving_throw.success)
  if (dice.save?.success !== undefined) return Boolean(dice.save.success)
  return null
}

function buildSaveFeedback(dice = {}) {
  const success = readSaveSuccess(dice)
  if (success === null) return null
  return success
    ? { kind: 'save-success', label: '豁免成功' }
    : { kind: 'save-failure', label: '豁免失败' }
}

function buildDeathSaveFeedback(dice = {}) {
  if (dice?.type !== 'death_save') return null
  const outcome = String(dice.outcome || '').toLowerCase()
  if (dice.revived || dice.stable || ['success', 'stable', 'revive'].includes(outcome)) {
    return { kind: 'death-save-success', label: dice.revived || outcome === 'revive' ? '死亡豁免复苏' : '死亡豁免成功' }
  }
  if (dice.dead || ['failure', 'dead'].includes(outcome)) {
    return { kind: 'death-save-failure', label: dice.dead || outcome === 'dead' ? '死亡豁免死亡' : '死亡豁免失败' }
  }
  return { kind: 'death-save', label: '死亡豁免' }
}

function buildConcentrationFeedback(state = []) {
  return state.some(item => String(item || '').includes('专注中断'))
    ? { kind: 'concentration-break', label: '专注中断' }
    : null
}

function buildDefenderInterceptionFeedback(attack = {}, state = []) {
  if (attack?.defender_interception) return { kind: 'defender-interception', label: '护卫干扰' }
  return state.some(item => String(item || '').includes('护卫干扰'))
    ? { kind: 'defender-interception', label: '护卫干扰' }
    : null
}

function buildCombatFeedback({ dice, state }) {
  const attack = dice?.attack || {}
  const feedback = [
    buildAttackFeedback(attack),
    buildDefenderInterceptionFeedback(attack, state),
    buildSaveFeedback(dice),
    buildDeathSaveFeedback(dice),
    buildConcentrationFeedback(state),
  ]
  const seen = new Set()
  return compact(feedback).filter(item => {
    if (seen.has(item.kind)) return false
    seen.add(item.kind)
    return true
  })
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

function summarizeConditions(conditions = null, targetName = null) {
  if (!Array.isArray(conditions) || !conditions.length) return null
  const summary = `状态 ${conditions.join('、')}`
  return targetName ? `${targetName} ${summary}` : summary
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
    ?? result.new_hp
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

function summarizeReactionHpResult(result = {}, options = {}) {
  const effect = result.reaction_effect || {}
  const before = effect.hp_before_reaction
  const after = effect.hp_after_reaction
  if (before === null || before === undefined || after === null || after === undefined) return []

  const restored = effect.hp_restored ?? 0
  if (before === after && restored <= 0) return []
  const label = targetLabelFrom(result, options)
  const suffix = restored > 0 ? `（反应恢复 ${restored}）` : ''
  const entries = [`${label} HP ${before} -> ${after}${suffix}`]

  if (
    effect.temporary_hp_before_reaction !== undefined
    && effect.temporary_hp_after_reaction !== undefined
    && effect.temporary_hp_before_reaction !== effect.temporary_hp_after_reaction
  ) {
    entries.push(`${label} 临时HP ${effect.temporary_hp_before_reaction} -> ${effect.temporary_hp_after_reaction}`)
  }
  if (
    effect.wild_shape_hp_before_reaction !== undefined
    && effect.wild_shape_hp_after_reaction !== undefined
    && effect.wild_shape_hp_before_reaction !== effect.wild_shape_hp_after_reaction
  ) {
    entries.push(`${label} 野性变身HP ${effect.wild_shape_hp_before_reaction} -> ${effect.wild_shape_hp_after_reaction}`)
  }
  return entries
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

function summarizeSkirmisherReposition(reposition = null) {
  if (!reposition || typeof reposition !== 'object') return null
  const steps = asNumber(reposition.steps)
  const distance = steps !== null ? `${steps * 5}ft` : ''
  const from = reposition.from
  const to = reposition.to
  const fromText = from && from.x !== undefined && from.y !== undefined ? `${from.x},${from.y}` : ''
  const toText = to && to.x !== undefined && to.y !== undefined ? `${to.x},${to.y}` : ''
  const route = fromText && toText ? `：${fromText} -> ${toText}` : ''
  return compact(['游击撤步', distance]).join(' ') + route
}

function resultGroupsFrom(result = {}) {
  return [
    result.aoe_results,
    result.target_results,
    result.resurrection_results,
  ]
}

function resultTargetKey(item = {}) {
  return String(
    item.target_id
    || item.character_id
    || item.id
    || item.target_name
    || item.character_name
    || item.name
    || '',
  )
}

function uniqueResultTargets(result = {}) {
  const seen = new Map()
  resultGroupsFrom(result).forEach(group => {
    if (!Array.isArray(group)) return
    group.forEach(item => {
      if (!item || typeof item !== 'object') return
      const key = resultTargetKey(item) || `target-${seen.size}`
      seen.set(key, { ...(seen.get(key) || {}), ...item })
    })
  })

  if (result.target_state && typeof result.target_state === 'object') {
    const key = resultTargetKey(result.target_state) || resultTargetKey(result) || `target-${seen.size}`
    seen.set(key, { ...(seen.get(key) || {}), ...result.target_state })
  } else if (hpAfterFrom(result) !== null || result.damage !== undefined || result.heal !== undefined) {
    const key = resultTargetKey(result) || `target-${seen.size}`
    seen.set(key, { ...(seen.get(key) || {}), ...result })
  }

  return [...seen.values()]
}

function targetNamesTitle(items = []) {
  return items
    .map(item => targetLabelFrom(item))
    .filter(Boolean)
    .join('、')
}

function saveSuccessFromTarget(item = {}) {
  const save = item.save || item.save_result || item.saving_throw
  if (!save || typeof save !== 'object' || save.success === undefined) return null
  return Boolean(save.success)
}

function sideFromTarget(item = {}) {
  const raw = String(item.side || item.target_side || item.allegiance || '').toLowerCase()
  if (['enemy', 'foe', 'hostile'].includes(raw)) return 'enemy'
  if (['ally', 'friend', 'friendly', 'self', 'player', 'companion'].includes(raw)) return 'ally'
  if (item.is_enemy === true) return 'enemy'
  if (item.is_enemy === false || item.is_ally === true || item.is_player === true || item.is_companion === true) return 'ally'
  return ''
}

function numberSum(items = [], field) {
  return items.reduce((sum, item) => {
    const value = asNumber(item?.[field])
    return value === null ? sum : sum + value
  }, 0)
}

function normalizeImpactSummary(items = []) {
  const seen = new Set()
  return compact(items.map((item, index) => {
    if (typeof item === 'string') {
      return { key: `impact-${index}`, label: item, tone: '', title: item }
    }
    if (!item || typeof item !== 'object' || !item.label) return null
    return {
      key: item.key || `impact-${index}`,
      label: item.label,
      tone: item.tone || '',
      title: item.title || item.label,
    }
  })).filter(item => {
    const key = `${item.key}:${item.label}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function buildCombatResultImpactSummary(result = {}) {
  if (!result || typeof result !== 'object') return []

  const targets = uniqueResultTargets(result)
  if (targets.length <= 1) return []

  const chips = []
  const title = targetNamesTitle(targets)
  chips.push({
    key: 'targets',
    label: `影响 ${targets.length} 个`,
    tone: 'info',
    title,
  })

  const enemies = targets.filter(item => sideFromTarget(item) === 'enemy')
  const allies = targets.filter(item => sideFromTarget(item) === 'ally')
  if (enemies.length > 0 || allies.length > 0) {
    if (enemies.length > 0) {
      chips.push({
        key: 'enemies',
        label: `敌方 ${enemies.length}`,
        tone: 'good',
        title: targetNamesTitle(enemies),
      })
    }
    if (allies.length > 0) {
      chips.push({
        key: 'allies',
        label: `友方 ${allies.length}`,
        tone: 'warning',
        title: targetNamesTitle(allies),
      })
    }
  }

  const damage = numberSum(targets, 'damage')
  if (damage > 0) {
    chips.push({
      key: 'damage',
      label: `总伤害 ${damage}`,
      tone: 'bad',
      title,
    })
  }

  const heal = numberSum(targets, 'heal')
  if (heal > 0) {
    chips.push({
      key: 'heal',
      label: `治疗 ${heal}`,
      tone: 'good',
      title,
    })
  }

  const saves = targets.map(saveSuccessFromTarget).filter(value => value !== null)
  if (saves.length > 0) {
    const failed = saves.filter(success => !success).length
    const succeeded = saves.length - failed
    if (failed > 0) chips.push({ key: 'save-failed', label: `豁免失败 ${failed}`, tone: 'bad', title })
    if (succeeded > 0) chips.push({ key: 'save-succeeded', label: `成功 ${succeeded}`, tone: 'good', title })
  }

  const downed = targets.filter(item => {
    const hp = hpAfterFrom(item)
    return hp !== null && hp <= 0
  }).length
  if (downed > 0) {
    chips.push({
      key: 'downed',
      label: `倒下 ${downed}`,
      tone: 'bad',
      title: targetNamesTitle(targets.filter(item => {
        const hp = hpAfterFrom(item)
        return hp !== null && hp <= 0
      })),
    })
  }

  return normalizeImpactSummary(chips)
}

export function buildCombatLogImpactSummary(log = {}) {
  if (Array.isArray(log.impact_summary) && log.impact_summary.length > 0) {
    return normalizeImpactSummary(log.impact_summary)
  }

  const result = log.result || log.action_result
  const fromResult = buildCombatResultImpactSummary(result)
  if (fromResult.length > 0) return fromResult

  const state = normalizeStateChanges(log.state_changes)
  const hpLines = state.filter(item => /\bHP\b/.test(String(item)) && /(?:->|→)/.test(String(item)))
  if (hpLines.length <= 1) return []

  const downed = hpLines.filter(item => /(?:->|→)\s*0(?:\D|$)/.test(String(item))).length
  return normalizeImpactSummary([
    {
      key: 'hp-updates',
      label: `HP变化 ${hpLines.length} 项`,
      tone: 'info',
      title: hpLines.join('；'),
    },
    downed > 0 ? {
      key: 'downed',
      label: `倒下 ${downed}`,
      tone: 'bad',
      title: hpLines.filter(item => /(?:->|→)\s*0(?:\D|$)/.test(String(item))).join('；'),
    } : null,
  ])
}

export function buildCombatStateChangeSummary(result = {}, options = {}) {
  if (!result || typeof result !== 'object') return []

  const reactionEffect = result.reaction_effect || {}
  const hasReactionHpRollback = (
    reactionEffect.hp_before_reaction !== undefined
    && reactionEffect.hp_after_reaction !== undefined
  )
  const entries = [
    ...(hasReactionHpRollback ? [] : summarizeTargetResult(result, options)),
    ...summarizeReactionHpResult(result, options),
  ]
  entries.push(formatReactionPreventionRule(reactionEffect))
  entries.push(formatCuttingWordsRule(result.cutting_words))

  resultGroupsFrom(result).forEach(group => {
    if (!Array.isArray(group)) return
    group.forEach(item => {
      entries.push(...summarizeTargetResult(item))
    })
  })

  const saves = result.death_saves || result.target_state?.death_saves
  entries.push(summarizeDeathSaves(saves))
  entries.push(summarizeConditions(
    result.conditions || result.target_state?.conditions,
    options.targetName,
  ))

  const slots = result.remaining_slots ? formatSlots(result.remaining_slots) : ''
  if (slots) entries.push(`法术位剩余 ${slots}`)

  entries.push(summarizeWeaponResource(result.weapon_resource))
  entries.push(summarizeSkirmisherReposition(result.skirmisher_reposition))
  entries.push(summarizeTurnState(result.turn_state))

  if (options.includeDefenderInterception !== false) {
    entries.push(formatDefenderInterception(
      result.defender_interception
      || result.attack_result?.defender_interception
      || result.dice_result?.attack?.defender_interception,
    ))
  }

  if (result.concentration_check?.broke) {
    entries.push(`专注中断${result.concentration_check.spell_name ? `：${result.concentration_check.spell_name}` : ''}`)
  }
  if (result.combat_over) entries.push('战斗结束')

  return [...new Set(compact(entries))]
}

export function buildCombatLogView(log = {}) {
  const rawDice = log.dice_result || null
  const dice = normalizeHazardDice(rawDice) || rawDice
  const attack = dice?.attack || {}
  const rules = compact([
    log.rule_result,
    formatAttackRule(attack),
    formatDefenderInterception(attack.defender_interception),
    formatContestRule(dice),
    ...formatHazardRules(dice),
    formatReactionPreventionRule(log.reaction_effect || (dice?.type === 'reaction' ? dice : null)),
    formatCuttingWordsRule(dice?.cutting_words),
  ])
  const diceEntries = buildDiceSections(dice)
  const state = normalizeStateChanges(log.state_changes)
  const narration = log.content ? [log.content] : []
  const feedback = buildCombatFeedback({ dice, state })

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
    feedback,
    impact: buildCombatLogImpactSummary(log),
    roleLabel: resolveRoleLabel(log.role),
    sections: compact([
      rules.length ? { kind: 'rules', label: '规则', items: rules } : null,
      diceEntries.length ? { kind: 'dice', label: '骰子', items: diceEntries } : null,
      narration.length ? { kind: 'narration', label: '叙事', items: narration } : null,
      state.length ? { kind: 'state', label: '状态', items: state } : null,
    ]),
  }
}
