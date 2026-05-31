const CONDITION_RULES = {
  blinded: 'Cannot see; attacks against it have advantage, its attacks have disadvantage.',
  charmed: 'Cannot attack the charmer; charmer has advantage on social checks.',
  deafened: 'Cannot hear and fails hearing-based checks.',
  frightened: 'Disadvantage while source is visible; cannot willingly move closer.',
  grappled: 'Speed becomes 0 until the grapple ends.',
  incapacitated: 'Cannot take actions or reactions.',
  invisible: 'Unseen; attacks have advantage and attacks against it have disadvantage.',
  paralyzed: 'Incapacitated; melee hits can become critical hits.',
  petrified: 'Incapacitated and resistant to damage; many saves/checks fail.',
  poisoned: 'Disadvantage on attack rolls and ability checks.',
  prone: 'Disadvantage on attacks; melee attacks against it have advantage.',
  restrained: 'Speed 0; attacks against it have advantage; its attacks and Dex saves have disadvantage.',
  stunned: 'Incapacitated; attacks against it have advantage; Str/Dex saves fail.',
  unconscious: 'Incapacitated, prone, unaware; nearby hits can become critical hits.',
  exhaustion: 'Exhaustion penalties are active; level determines severity.',
  hexed: 'Cursed by a hostile effect; check the combat log for the chosen ability.',
  slowed: 'Speed and action options are reduced; Dex saves may be penalized.',
  marked: 'Marked by a hostile effect; attacks or follow-up effects may prefer this target.',
  burning: 'Taking ongoing fire or heat pressure; check the combat log for damage timing.',
  webbed: 'Restrained by webbing or sticky terrain until freed.',
}

const BENEFICIAL_RULES = {
  blessed: 'Adds a bonus die to attacks and saves while active.',
  bless: 'Adds a bonus die to attacks and saves while active.',
  fire_resistance: 'Fire damage is reduced while this protection lasts.',
  cold_resistance: 'Cold damage is reduced while this protection lasts.',
  acid_resistance: 'Acid damage is reduced while this protection lasts.',
  lightning_resistance: 'Lightning damage is reduced while this protection lasts.',
  thunder_resistance: 'Thunder damage is reduced while this protection lasts.',
  rage: 'Rage-style protection is active; check logs for damage and action limits.',
  concentrating: 'Maintaining concentration; damage may force a concentration check.',
}

const CONDITION_IMPACTS = {
  blinded: [
    impact('hit_adv', 'Hit adv', 'Attacks against this creature have advantage.'),
    impact('attack_disadv', 'Atk disadv', 'This creature attacks with disadvantage.'),
  ],
  charmed: [
    impact('social_adv', 'Social adv', 'The charmer has advantage on social checks against this creature.', 'warning'),
  ],
  deafened: [
    impact('hearing_fail', 'Hearing fail', 'Hearing-based checks fail or are blocked.', 'warning'),
  ],
  frightened: [
    impact('attack_disadv', 'Atk disadv', 'Attack rolls and checks are disadvantaged while the source is visible.'),
    impact('move_block', 'Move block', 'Cannot willingly move closer to the source.'),
  ],
  grappled: [
    impact('speed_0', 'Speed 0', 'Movement speed is reduced to 0.'),
  ],
  incapacitated: [
    impact('no_actions', 'No actions', 'Cannot take actions or reactions.'),
  ],
  invisible: [
    impact('attack_adv', 'Atk adv', 'This creature attacks with advantage while unseen.', 'good'),
    impact('hit_disadv', 'Hit disadv', 'Attacks against this creature have disadvantage.', 'good'),
  ],
  paralyzed: [
    impact('no_actions', 'No actions', 'Cannot take actions or reactions.'),
    impact('speed_0', 'Speed 0', 'Movement speed is reduced to 0.'),
    impact('hit_adv', 'Hit adv', 'Attacks against this creature have advantage.'),
    impact('crit_risk', 'Crit risk', 'Nearby hits can become critical hits.'),
    impact('save_fail', 'Save fail', 'Strength and Dexterity saves fail automatically.'),
  ],
  petrified: [
    impact('no_actions', 'No actions', 'Cannot take actions or reactions.'),
    impact('speed_0', 'Speed 0', 'Movement speed is reduced to 0.'),
    impact('hit_adv', 'Hit adv', 'Attacks against this creature have advantage.'),
    impact('save_fail', 'Save fail', 'Strength and Dexterity saves fail automatically.'),
    impact('resist', 'Resist', 'Damage resistance is active.', 'good'),
  ],
  poisoned: [
    impact('attack_disadv', 'Atk disadv', 'Attack rolls and ability checks have disadvantage.'),
  ],
  prone: [
    impact('attack_disadv', 'Atk disadv', 'This creature attacks with disadvantage.'),
    impact('melee_hit_adv', 'Melee adv', 'Nearby melee attacks against this creature have advantage.'),
  ],
  restrained: [
    impact('speed_0', 'Speed 0', 'Movement speed is reduced to 0.'),
    impact('hit_adv', 'Hit adv', 'Attacks against this creature have advantage.'),
    impact('attack_disadv', 'Atk disadv', 'This creature attacks with disadvantage.'),
    impact('dex_disadv', 'DEX disadv', 'Dexterity saves have disadvantage.'),
  ],
  stunned: [
    impact('no_actions', 'No actions', 'Cannot take actions or reactions.'),
    impact('speed_0', 'Speed 0', 'Movement speed is reduced to 0.'),
    impact('hit_adv', 'Hit adv', 'Attacks against this creature have advantage.'),
    impact('save_fail', 'Save fail', 'Strength and Dexterity saves fail automatically.'),
  ],
  unconscious: [
    impact('no_actions', 'No actions', 'Cannot take actions or reactions.'),
    impact('speed_0', 'Speed 0', 'Movement speed is reduced to 0.'),
    impact('hit_adv', 'Hit adv', 'Attacks against this creature have advantage.'),
    impact('crit_risk', 'Crit risk', 'Nearby hits can become critical hits.'),
  ],
  exhaustion: [
    impact('penalty', 'Penalty', 'Exhaustion level determines active penalties.', 'warning'),
  ],
  hexed: [
    impact('check_disadv', 'Check disadv', 'A chosen ability check may have disadvantage.'),
  ],
  slowed: [
    impact('action_limit', 'Action limit', 'Action options are reduced.'),
    impact('dex_disadv', 'DEX disadv', 'Dexterity saves may have disadvantage.'),
  ],
  marked: [
    impact('focus_fire', 'Focus fire', 'This target is marked for follow-up pressure.', 'warning'),
  ],
  burning: [
    impact('ongoing_damage', 'Ongoing dmg', 'Ongoing damage or hazard pressure may apply.'),
  ],
  webbed: [
    impact('speed_0', 'Speed 0', 'Movement speed is reduced to 0.'),
    impact('hit_adv', 'Hit adv', 'Attacks against this creature have advantage.'),
    impact('attack_disadv', 'Atk disadv', 'This creature attacks with disadvantage.'),
  ],
}

export function buildConditionSummaries(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return []

  return conditions
    .map(condition => conditionSummary(condition, durations))
    .filter(Boolean)
}

export function buildConditionImpactTags(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return []

  const tagsByKey = new Map()
  for (const condition of conditions) {
    const key = conditionKey(condition)
    if (!key) continue
    const label = conditionImpactSourceLabel(condition, key, durations)
    const impacts = conditionImpacts(key)
    for (const item of impacts) {
      const existing = tagsByKey.get(item.key)
      if (existing) {
        existing.sources.push(label)
        continue
      }
      tagsByKey.set(item.key, {
        ...item,
        sources: [label],
      })
    }
  }

  return Array.from(tagsByKey.values())
    .map(tag => ({
      key: tag.key,
      label: tag.label,
      tone: tag.tone,
      title: `${tag.title} Source: ${tag.sources.join(' / ')}.`,
    }))
    .slice(0, 6)
}

function conditionSummary(condition, durations = {}) {
  const key = conditionKey(condition)
  if (!key) return null
  const duration = durations?.[key] ?? durations?.[condition] ?? null
  const beneficial = Object.prototype.hasOwnProperty.call(BENEFICIAL_RULES, key)
  const label = conditionLabel(key)
  const rule = BENEFICIAL_RULES[key] || CONDITION_RULES[key] || 'Condition is active; check logs for exact source and duration.'
  const durationText = duration ? ` Duration: ${duration} round${Number(duration) === 1 ? '' : 's'}.` : ''

  return {
    key,
    label,
    tone: beneficial ? 'buff' : 'harm',
    summary: rule,
    title: `${label}: ${rule}${durationText}`,
    duration,
  }
}

function conditionImpacts(key) {
  if (CONDITION_IMPACTS[key]) return CONDITION_IMPACTS[key]
  if (key.endsWith('_resistance')) {
    return [impact('resist', 'Resist', 'Damage resistance is active.', 'good')]
  }
  if (Object.prototype.hasOwnProperty.call(BENEFICIAL_RULES, key)) {
    return [impact('buff_active', 'Buff', BENEFICIAL_RULES[key], 'good')]
  }
  return []
}

function impact(key, label, title, tone = 'bad') {
  return { key, label, title, tone }
}

function conditionImpactSourceLabel(condition, key, durations = {}) {
  const label = conditionLabel(key)
  const duration = conditionDuration(condition, key, durations)
  return duration ? `${label} (${formatShortDuration(duration)})` : label
}

function conditionDuration(condition, key, durations = {}) {
  const raw = typeof condition === 'string'
    ? condition
    : condition?.name || condition?.condition || condition?.type || condition?.id || ''
  return durations?.[key] ?? durations?.[raw] ?? null
}

function formatShortDuration(duration) {
  const numeric = Number(duration)
  if (!Number.isNaN(numeric)) return `${duration}r`
  return String(duration)
}

function conditionKey(condition) {
  if (typeof condition === 'string') return normalize(condition)
  if (!condition || typeof condition !== 'object') return ''
  return normalize(condition.name || condition.condition || condition.type || condition.id || '')
}

function normalize(value) {
  return String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
}

function conditionLabel(key) {
  return key
    .split('_')
    .filter(Boolean)
    .map(part => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(' ')
}
