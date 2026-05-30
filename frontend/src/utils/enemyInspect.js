const ALL_STATS = 'all'

function collectRevealedStats(entity = {}) {
  const knowledge = entity.knowledge_state || entity.knowledge || entity.inspect || {}
  return new Set([
    ...(Array.isArray(entity.revealed_stats) ? entity.revealed_stats : []),
    ...(Array.isArray(entity.known_stats) ? entity.known_stats : []),
    ...(Array.isArray(knowledge.revealed_stats) ? knowledge.revealed_stats : []),
    ...(Array.isArray(knowledge.known_stats) ? knowledge.known_stats : []),
  ].map(value => String(value || '').toLowerCase()))
}

export function isEnemyDetailVisible(entity = {}, key = '') {
  if (!entity?.is_enemy) return false
  const knowledge = entity.knowledge_state || entity.knowledge || entity.inspect || {}
  if (
    entity.identified === true ||
    entity.stats_revealed === true ||
    knowledge.identified === true ||
    knowledge.stats_revealed === true
  ) {
    return true
  }
  const revealed = collectRevealedStats(entity)
  const normalizedKey = String(key || '').toLowerCase()
  return revealed.has(ALL_STATS) || revealed.has(normalizedKey)
}

export function buildEnemyInspectModel(entity = null) {
  if (!entity?.is_enemy) return null

  const visible = key => isEnemyDetailVisible(entity, key)
  const fullyIdentified = isEnemyDetailVisible(entity, ALL_STATS)
    || entity.identified === true
    || entity.stats_revealed === true
  const rows = [
    {
      label: 'CR',
      value: visible('cr') ? displayValue(entity.cr ?? entity.challenge_rating ?? entity.challenge) : 'Unknown',
      hidden: !visible('cr'),
    },
    {
      label: 'SPD',
      value: visible('speed') ? displayValue(entity.speed) : 'Unknown',
      hidden: !visible('speed'),
    },
    {
      label: 'RES',
      value: visible('resistances') ? displayList(entity.resistances) : 'Unknown',
      hidden: !visible('resistances'),
    },
    {
      label: 'IMM',
      value: visible('immunities') ? displayList(entity.immunities) : 'Unknown',
      hidden: !visible('immunities'),
    },
    {
      label: 'VULN',
      value: visible('vulnerabilities') ? displayList(entity.vulnerabilities) : 'Unknown',
      hidden: !visible('vulnerabilities'),
    },
    {
      label: 'COND',
      value: visible('condition_immunities') ? displayList(entity.condition_immunities) : 'Unknown',
      hidden: !visible('condition_immunities'),
    },
  ]

  return {
    revealLabel: fullyIdentified ? 'IDENTIFIED' : 'PARTIAL',
    rows,
    actions: visible('actions') ? displayActions(entity.actions) : 'Unknown',
    traits: visible('special_abilities') ? displayTraits(entity.special_abilities) : 'Unknown',
    tactics: visible('tactics') ? displayValue(entity.tactics) : 'Unknown',
    actionsHidden: !visible('actions'),
    traitsHidden: !visible('special_abilities'),
    tacticsHidden: !visible('tactics'),
  }
}

function displayValue(value) {
  if (value === null || value === undefined || value === '') return 'None'
  return String(value)
}

function displayList(value) {
  if (!Array.isArray(value) || value.length === 0) return 'None'
  return value.map(item => String(item)).join(' / ')
}

function displayActions(actions) {
  if (!Array.isArray(actions) || actions.length === 0) return 'None'
  return actions
    .map(action => typeof action === 'string' ? action : action?.name)
    .filter(Boolean)
    .slice(0, 3)
    .join(' / ') || 'None'
}

function displayTraits(traits) {
  if (!Array.isArray(traits) || traits.length === 0) return 'None'
  return traits
    .map(trait => typeof trait === 'string' ? trait : trait?.name)
    .filter(Boolean)
    .slice(0, 3)
    .join(' / ') || 'None'
}
