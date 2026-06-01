export function buildSpellRuleBadges(spell = {}, { isCantrip = false } = {}) {
  if (!spell) return []

  const badges = [
    { key: 'level', label: isCantrip ? '戏法' : `${spell.level ?? 1}环` },
  ]

  const type = String(spell.type || '').toLowerCase()
  if (type === 'heal') badges.push({ key: 'type', label: '治疗' })
  else if (type === 'control') badges.push({ key: 'type', label: '控制' })
  else if (type === 'damage') badges.push({ key: 'type', label: '伤害' })

  if (spell.aoe) badges.push({ key: 'aoe', label: '范围' })

  const target = targetLabel(spell)
  if (target) badges.push({ key: 'target', label: target })

  const save = spell.save || spell.saving_throw || spell.save_ability
  if (save) badges.push({ key: 'save', label: `${abilityLabel(save)}豁免` })
  else if (requiresAttackRoll(spell)) badges.push({ key: 'attack', label: '法术攻击' })

  if (spell.concentration || /concentration|专注/i.test(`${spell.desc || ''} ${spell.description || ''}`)) {
    badges.push({ key: 'concentration', label: '专注' })
  }

  return dedupeBadges(badges).slice(0, 6)
}

export function buildSpellRulePreview(spell = {}, context = {}) {
  if (!spell) return []

  const rows = []
  const effect = effectPreview(spell)
  if (effect) rows.push({ key: 'effect', label: '效果', value: effect })

  const resolve = resolvePreview(spell, context)
  if (resolve) rows.push({ key: 'resolve', label: '结算', value: resolve })

  const timing = timingPreview(spell)
  if (timing) rows.push({ key: 'timing', label: '时机', value: timing })

  return rows.slice(0, 3)
}

function targetLabel(spell = {}) {
  const raw = String(spell.target_type || spell.targetType || spell.target || spell.targets || '').toLowerCase()
  if (!raw) return ''
  if (raw.includes('self') || raw.includes('自身')) return '自身'
  if (raw.includes('ally') || raw.includes('队友')) return '友方'
  if (raw.includes('enemy') || raw.includes('creature') || raw.includes('目标')) return '目标'
  if (raw.includes('point') || raw.includes('ground')) return '地点'
  return ''
}

function requiresAttackRoll(spell = {}) {
  if (spell.attack_roll || spell.requires_attack_roll) return true
  const text = `${spell.name || ''} ${spell.name_en || ''} ${spell.desc || ''} ${spell.description || ''}`.toLowerCase()
  if (/spell attack|ranged attack|melee attack|法术攻击|远程攻击|近战攻击/.test(text)) return true
  return String(spell.type || '').toLowerCase() === 'damage' && !spell.aoe
}

function effectPreview(spell = {}) {
  if (spell.damage) return `伤害 ${spell.damage}`
  if (spell.heal) return `治疗 ${spell.heal}`
  const conditions = Array.isArray(spell.conditions) ? spell.conditions.join('/') : spell.condition || spell.conditions
  if (conditions) return `状态 ${conditions}`
  const type = String(spell.type || '').trim()
  return type ? typeLabel(type) : ''
}

function resolvePreview(spell = {}, { caster = null } = {}) {
  const save = spell.save || spell.saving_throw || spell.save_ability
  const derived = caster?.derived || caster || {}
  if (save) {
    const dc = readFiniteNumber(spell.save_dc ?? spell.dc ?? derived.spell_save_dc)
    return [
      `${abilityLabel(save)}豁免`,
      dc !== null ? `DC ${dc}` : '',
      spell.half_on_save ? '成功减半' : '',
    ].filter(Boolean).join(' · ')
  }
  if (requiresAttackRoll(spell)) {
    const attackBonus = readFiniteNumber(spell.spell_attack_bonus ?? spell.attack_bonus ?? derived.spell_attack_bonus)
    return attackBonus !== null ? `法术攻击检定 · ${formatSignedNumber(attackBonus)}` : '法术攻击检定'
  }
  if (spell.aoe) return '施放前确认范围'
  return ''
}

function timingPreview(spell = {}) {
  const parts = [
    timingText(spell.casting_time || spell.action_type || ''),
    spell.range ? `射程 ${spell.range}` : '',
    spell.duration ? `持续 ${spell.duration}` : '',
  ].filter(Boolean)
  if (spell.concentration && !parts.some(part => /concentration/i.test(String(part)))) {
    parts.push('专注')
  }
  return parts.slice(0, 2).join(' · ')
}

function abilityLabel(value) {
  const key = String(value || '').trim().toLowerCase()
  return ({
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
  })[key] || String(value || '').toUpperCase()
}

function typeLabel(value) {
  const key = String(value || '').trim().toLowerCase()
  return ({
    heal: '治疗',
    damage: '伤害',
    control: '控制',
    buff: '增益',
  })[key] || value
}

function timingText(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  return text
    .replace(/^1 action$/i, '1 动作')
    .replace(/^action$/i, '动作')
    .replace(/bonus action/i, '附赠动作')
    .replace(/reaction/i, '反应')
}

function readFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatSignedNumber(value) {
  return value >= 0 ? `+${value}` : String(value)
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
