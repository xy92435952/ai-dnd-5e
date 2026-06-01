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
      value: visible('cr') ? displayValue(entity.cr ?? entity.challenge_rating ?? entity.challenge) : '未知',
      hidden: !visible('cr'),
    },
    {
      label: '速度',
      value: visible('speed') ? displayValue(entity.speed) : '未知',
      hidden: !visible('speed'),
    },
    {
      label: '抗性',
      value: visible('resistances') ? displayList(entity.resistances) : '未知',
      hidden: !visible('resistances'),
    },
    {
      label: '免疫',
      value: visible('immunities') ? displayList(entity.immunities) : '未知',
      hidden: !visible('immunities'),
    },
    {
      label: '易伤',
      value: visible('vulnerabilities') ? displayList(entity.vulnerabilities) : '未知',
      hidden: !visible('vulnerabilities'),
    },
    {
      label: '状态免疫',
      value: visible('condition_immunities') ? displayList(entity.condition_immunities) : '未知',
      hidden: !visible('condition_immunities'),
    },
  ]

  return {
    revealLabel: fullyIdentified ? '已识别' : '部分',
    rows,
    actions: visible('actions') ? displayActions(entity.actions) : '未知',
    traits: visible('special_abilities') ? displayTraits(entity.special_abilities) : '未知',
    tactics: visible('tactics') ? displayValue(entity.tactics) : '未知',
    actionsHidden: !visible('actions'),
    traitsHidden: !visible('special_abilities'),
    tacticsHidden: !visible('tactics'),
  }
}

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '无'
  return String(value)
}

function displayList(value) {
  if (!Array.isArray(value) || value.length === 0) return '无'
  return value.map(item => String(item)).join(' / ')
}

function displayActions(actions) {
  if (!Array.isArray(actions) || actions.length === 0) return '无'
  return actions
    .map(action => typeof action === 'string' ? action : action?.name)
    .filter(Boolean)
    .slice(0, 3)
    .join(' / ') || '无'
}

function displayTraits(traits) {
  if (!Array.isArray(traits) || traits.length === 0) return '无'
  return traits
    .map(trait => typeof trait === 'string' ? trait : trait?.name)
    .filter(Boolean)
    .slice(0, 3)
    .join(' / ') || '无'
}
