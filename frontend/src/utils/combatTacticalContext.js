import { getGridTerrainKind } from './combat'

const WALL_KINDS = new Set(['wall', 'cover', 'half_cover', 'three_quarters_cover', 'total_cover', 'blocking', 'blocker', 'opaque'])
const HAZARD_KINDS = new Set(['hazard'])
const DIFFICULT_KINDS = new Set(['difficult', 'difficult_terrain'])

export function buildCombatTacticalContext({ combat, session } = {}) {
  const gridData = combat?.grid_data || {}
  const template = gridData?._encounter_template || {}
  const gameState = session?.game_state || {}
  const encounterBalance = gameState.encounter_balance || {}
  const templateBalance = gameState.last_encounter_template_balance || {}
  const rosterTuning = templateBalance.roster_tuning || null
  const counts = summarizeGridTerrain(gridData)

  const objectives = featureLabels(template.objectives)
  const terrain = featureLabels(template.terrain)
  const cover = featureLabels(template.cover)
  const hazards = featureLabels(template.hazards)
  const detailGroups = buildDetailGroups({ objectives, terrain, cover, hazards, counts })

  const title = String(template.name || session?.module_name || 'Encounter')
  const difficulty = String(encounterBalance.difficulty || templateBalance.estimated_difficulty || '')
  const environmentPressure = String(templateBalance.environment_pressure?.pressure || '')
  const environmentAdjustedDifficulty = String(templateBalance.environment_adjusted_difficulty || '')
  const targetDifficulty = String(templateBalance.target_difficulty || '')
  const stagedCount = Number(
    rosterTuning?.staged_count
    ?? gameState.last_encounter_template_staged_enemies?.length
    ?? 0,
  )

  return {
    hasContext: Boolean(
      template.name
      || objectives.length
      || terrain.length
      || cover.length
      || hazards.length
      || difficulty
      || environmentPressure
      || stagedCount
      || counts.cover
      || counts.hazard
      || counts.difficult
      || counts.objective
    ),
    title,
    difficulty,
    environmentPressure,
    environmentAdjustedDifficulty,
    targetDifficulty,
    adjustedXp: encounterBalance.adjusted_xp ?? templateBalance.estimate?.adjusted_xp ?? null,
    stagedCount,
    objectives,
    terrain,
    cover,
    hazards,
    detailGroups,
    counts,
  }
}

export function summarizeGridTerrain(gridData = {}) {
  const counts = { cover: 0, difficult: 0, hazard: 0, objective: 0 }
  for (const [key, value] of Object.entries(gridData || {})) {
    if (key.startsWith('_')) continue
    const terrain = getGridTerrainKind(value)
    if (WALL_KINDS.has(terrain)) counts.cover += 1
    else if (HAZARD_KINDS.has(terrain)) counts.hazard += 1
    else if (DIFFICULT_KINDS.has(terrain)) counts.difficult += 1
    else if (terrain === 'objective') counts.objective += 1
  }
  return counts
}

function featureLabels(values) {
  return asArray(values)
    .map(featureLabel)
    .filter(Boolean)
    .slice(0, 4)
}

function buildDetailGroups({ objectives, terrain, cover, hazards, counts }) {
  return [
    detailGroup('objective', '目标', objectives, counts.objective, '已标记目标'),
    detailGroup('cover', '掩护', cover, counts.cover, '已标记掩护'),
    detailGroup('terrain', '地形', terrain, counts.difficult, '困难地形'),
    detailGroup('hazard', '危险', hazards, counts.hazard, '已标记危险'),
  ].filter(Boolean)
}

function detailGroup(key, label, items = [], count = 0, fallback = '') {
  const visibleItems = items.slice(0, 3)
  const valueParts = visibleItems.length ? visibleItems : (count ? [fallback] : [])
  if (!valueParts.length) return null

  const extraItems = Math.max(items.length - visibleItems.length, 0)
  const meta = []
  if (extraItems > 0) meta.push(`+${extraItems}`)
  if (count > 0) meta.push(`${count} 格`)

  return {
    key,
    label,
    value: [valueParts.join(' / '), ...meta].join(' · '),
    title: items.length ? items.join(' / ') : fallback,
  }
}

function featureLabel(value) {
  if (typeof value === 'string') return value.trim()
  if (!value || typeof value !== 'object') return ''
  return String(
    value.label
    || value.name
    || value.description
    || value.terrain
    || value.type
    || value.kind
    || value.category
    || value.cover_level
    || '',
  ).trim()
}

function asArray(value) {
  if (Array.isArray(value)) return value
  return value ? [value] : []
}
