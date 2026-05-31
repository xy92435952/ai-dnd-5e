export function buildSpellRuleBadges(spell = {}, { isCantrip = false } = {}) {
  if (!spell) return []

  const badges = [
    { key: 'level', label: isCantrip ? 'Cantrip' : `L${spell.level ?? 1}` },
  ]

  const type = String(spell.type || '').toLowerCase()
  if (type === 'heal') badges.push({ key: 'type', label: 'Heal' })
  else if (type === 'control') badges.push({ key: 'type', label: 'Control' })
  else if (type === 'damage') badges.push({ key: 'type', label: 'Damage' })

  if (spell.aoe) badges.push({ key: 'aoe', label: 'AoE' })

  const target = targetLabel(spell)
  if (target) badges.push({ key: 'target', label: target })

  const save = spell.save || spell.saving_throw || spell.save_ability
  if (save) badges.push({ key: 'save', label: `Save ${String(save).toUpperCase()}` })
  else if (requiresAttackRoll(spell)) badges.push({ key: 'attack', label: 'Attack roll' })

  if (spell.concentration || /concentration|专注/i.test(`${spell.desc || ''} ${spell.description || ''}`)) {
    badges.push({ key: 'concentration', label: 'Concentration' })
  }

  return dedupeBadges(badges).slice(0, 6)
}

export function buildSpellRulePreview(spell = {}) {
  if (!spell) return []

  const rows = []
  const effect = effectPreview(spell)
  if (effect) rows.push({ key: 'effect', label: 'Effect', value: effect })

  const resolve = resolvePreview(spell)
  if (resolve) rows.push({ key: 'resolve', label: 'Resolve', value: resolve })

  const timing = timingPreview(spell)
  if (timing) rows.push({ key: 'timing', label: 'Timing', value: timing })

  return rows.slice(0, 3)
}

function targetLabel(spell = {}) {
  const raw = String(spell.target_type || spell.targetType || spell.target || spell.targets || '').toLowerCase()
  if (!raw) return ''
  if (raw.includes('self') || raw.includes('自身')) return 'Self'
  if (raw.includes('ally') || raw.includes('队友')) return 'Ally'
  if (raw.includes('enemy') || raw.includes('creature') || raw.includes('目标')) return 'Target'
  if (raw.includes('point') || raw.includes('ground')) return 'Point'
  return ''
}

function requiresAttackRoll(spell = {}) {
  if (spell.attack_roll || spell.requires_attack_roll) return true
  const text = `${spell.name || ''} ${spell.name_en || ''} ${spell.desc || ''} ${spell.description || ''}`.toLowerCase()
  if (/spell attack|ranged attack|melee attack|法术攻击|远程攻击|近战攻击/.test(text)) return true
  return String(spell.type || '').toLowerCase() === 'damage' && !spell.aoe
}

function effectPreview(spell = {}) {
  if (spell.damage) return `Damage ${spell.damage}`
  if (spell.heal) return `Heal ${spell.heal}`
  const conditions = Array.isArray(spell.conditions) ? spell.conditions.join('/') : spell.condition || spell.conditions
  if (conditions) return `Condition ${conditions}`
  const type = String(spell.type || '').trim()
  return type ? capitalize(type) : ''
}

function resolvePreview(spell = {}) {
  const save = spell.save || spell.saving_throw || spell.save_ability
  if (save) {
    return `${String(save).toUpperCase()} save${spell.half_on_save ? ' · half on save' : ''}`
  }
  if (requiresAttackRoll(spell)) return 'Spell attack roll'
  if (spell.aoe) return 'Confirm area before cast'
  return ''
}

function timingPreview(spell = {}) {
  const parts = [
    spell.casting_time || spell.action_type || '',
    spell.range ? `Range ${spell.range}` : '',
    spell.duration ? `Duration ${spell.duration}` : '',
  ].filter(Boolean)
  if (spell.concentration && !parts.some(part => /concentration/i.test(String(part)))) {
    parts.push('Concentration')
  }
  return parts.slice(0, 2).join(' · ')
}

function capitalize(value) {
  const text = String(value || '')
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : ''
}

function dedupeBadges(badges) {
  const seen = new Set()
  return badges.filter(badge => {
    const key = `${badge.key}:${badge.label}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
