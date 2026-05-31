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
}

const BENEFICIAL_RULES = {
  blessed: 'Adds a bonus die to attacks and saves while active.',
  bless: 'Adds a bonus die to attacks and saves while active.',
  fire_resistance: 'Fire damage is reduced while this protection lasts.',
  cold_resistance: 'Cold damage is reduced while this protection lasts.',
  acid_resistance: 'Acid damage is reduced while this protection lasts.',
  lightning_resistance: 'Lightning damage is reduced while this protection lasts.',
  thunder_resistance: 'Thunder damage is reduced while this protection lasts.',
}

export function buildConditionSummaries(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return []

  return conditions
    .map(condition => conditionSummary(condition, durations))
    .filter(Boolean)
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
