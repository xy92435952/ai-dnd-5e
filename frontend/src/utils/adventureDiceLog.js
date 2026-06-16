function asNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function hasValue(value) {
  return value !== null && value !== undefined && value !== ''
}

function compact(parts) {
  return parts.filter(part => part !== null && part !== undefined && part !== '')
}

function formatModifier(value) {
  const modifier = asNumber(value)
  if (modifier === null) return ''
  if (modifier < 0) return ` - ${Math.abs(modifier)}`
  return ` + ${modifier}`
}

function formatAgainst(dice) {
  if (hasValue(dice.against)) return dice.against
  if (hasValue(dice.dc)) return `DC${dice.dc}`
  if (hasValue(dice.target_ac)) return `AC${dice.target_ac}`
  return ''
}

function formatOutcome(dice) {
  if (dice.outcome) return dice.outcome
  if (dice.success === true || dice.hit === true) return '成功'
  if (dice.success === false || dice.hit === false) return '失败'
  return ''
}

export function formatAdventureDiceLog(dice = {}) {
  if (Array.isArray(dice)) {
    return dice.map(row => formatAdventureDiceLog(row)).filter(Boolean).join(' | ')
  }
  if (!dice || typeof dice !== 'object') return '骰子'

  if (dice.kind === 'reaction' || dice.reaction_type) {
    return formatReactionDiceLog(dice)
  }

  const label = dice.label || '骰子'
  const raw = dice.raw ?? dice.d20 ?? dice.roll ?? ''
  const total = dice.total ?? ''
  const against = formatAgainst(dice)
  const outcome = formatOutcome(dice)
  const rollText = hasValue(raw)
    ? `${raw}${formatModifier(dice.modifier)}${hasValue(total) ? ` = ${total}` : ''}`
    : hasValue(total)
      ? String(total)
      : ''

  return compact([
    rollText ? `${label}：${rollText}` : label,
    against ? `vs ${against}` : null,
    outcome ? `→ ${outcome}` : null,
  ]).join(' ')
}

export function formatReactionDiceLog(dice = {}) {
  const type = String(dice.reaction_type || dice.type || '').trim().toLowerCase()
  if (type === 'feather_fall') {
    const spellName = dice.spell_name || 'Feather Fall'
    const prevented = asNumber(dice.damage_prevented)
    const slot = dice.slot_level
    const details = compact([
      prevented !== null ? `prevented ${prevented} damage` : null,
      slot ? `spent ${slot} slot` : null,
    ]).join(' · ')
    return details ? `${spellName} reaction：${details}` : `${spellName} reaction`
  }

  const label = dice.label || dice.spell_name || 'Reaction'
  const prevented = asNumber(dice.damage_prevented)
  return compact([
    label,
    prevented !== null ? `prevented ${prevented} damage` : null,
  ]).join('：')
}
