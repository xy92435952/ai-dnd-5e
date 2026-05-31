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

  const title = String(template.name || session?.module_name || 'Encounter')
  const difficulty = String(encounterBalance.difficulty || templateBalance.estimated_difficulty || '')
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
      || stagedCount
      || counts.cover
      || counts.hazard
      || counts.difficult
      || counts.objective
    ),
    title,
    difficulty,
    targetDifficulty,
    adjustedXp: encounterBalance.adjusted_xp ?? templateBalance.estimate?.adjusted_xp ?? null,
    stagedCount,
    objectives,
    terrain,
    cover,
    hazards,
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
