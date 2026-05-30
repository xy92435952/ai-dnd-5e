import {
  CLASS_INFO,
  CLASS_ZH_TO_EN,
  RACE_INFO,
  MULTICLASS_REQUIREMENTS,
} from '../data/dnd5e.js'

export const POINT_BUY_TOTAL = 27
export const SCORE_COSTS = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 }
export const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
export const ABILITY_KEYS = ['str', 'dex', 'con', 'int', 'wis', 'cha']

export function modifier(score) {
  return Math.floor((score - 10) / 2)
}

export function modStr(n) {
  return n >= 0 ? `+${n}` : `${n}`
}

export function getHitDieValue(hitDie, fallback = 8) {
  const parsed = typeof hitDie === 'number'
    ? hitDie
    : Number(String(hitDie || '').replace(/^d/i, ''))
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export function formatHitDieLabel(hitDie, fallback = '') {
  const value = getHitDieValue(hitDie, null)
  return value ? `d${value}` : fallback
}

export function getClassEnKey(charClass) {
  return CLASS_ZH_TO_EN[charClass] || charClass || ''
}

export function getRaceEnKey(race) {
  return Object.keys(RACE_INFO).find((k) => k === race || RACE_INFO[k]?.zh === race) || ''
}

export function buildStandardScores(standardAssigned = {}) {
  const scores = {}
  for (const key of ABILITY_KEYS) {
    const idx = standardAssigned[key]
    scores[key] = idx !== undefined ? STANDARD_ARRAY[idx] : 8
  }
  return scores
}

export function applyRacialBonuses(baseScores = {}, racialBonuses = {}) {
  const scores = { ...baseScores }
  for (const [key, value] of Object.entries(racialBonuses || {})) {
    scores[key] = (scores[key] || 8) + (Number(value) || 0)
  }
  return scores
}

export function normalizeCharacterOptions(options = {}) {
  const racialBonuses = options.racial_bonuses || options.racial_ability_bonuses || {}
  const racialAbilityBonuses = options.racial_ability_bonuses || options.racial_bonuses || {}
  return {
    ...options,
    racial_bonuses: racialBonuses,
    racial_ability_bonuses: racialAbilityBonuses,
  }
}

export function getStepLabels({ isSpellcaster, needsASI, isMultiplayerCreate }) {
  const steps = ['基础信息', '能力值', '技能熟练', '装备选择']
  if (isSpellcaster) steps.push('法术选择')
  if (needsASI) steps.push('专长/属性提升')
  if (isMultiplayerCreate) steps.push('加入房间')
  else steps.push('确认队伍', 'DM风格')
  return steps
}

export function buildCharacterCreateModel({
  form,
  options,
  scoreMethod,
  scores,
  standardAssigned,
  chosenSkills,
  chosenCantrips,
  chosenSpells,
  isMultiplayerCreate = false,
}) {
  const classEnKey = getClassEnKey(form?.char_class)
  const classInfo = CLASS_INFO[classEnKey] || null
  const raceEnKey = getRaceEnKey(form?.race)

  const racialBonuses = options?.racial_bonuses?.[form?.race]
    || options?.racial_bonuses?.[raceEnKey]
    || options?.racial_ability_bonuses?.[form?.race]
    || options?.racial_ability_bonuses?.[raceEnKey]
    || {}

  const baseScores = scoreMethod === 'pointbuy'
    ? { ...scores }
    : buildStandardScores(standardAssigned)

  const finalScores = applyRacialBonuses(baseScores, racialBonuses)

  const pointsSpent = Object.values(scores || {}).reduce(
    (sum, value) => sum + (SCORE_COSTS[value] || 0),
    0,
  )
  const pointsLeft = POINT_BUY_TOTAL - pointsSpent

  const skillConfig = (
    options?.class_skill_choices?.[form?.char_class]
    || options?.class_skill_choices?.[classEnKey]
    || { count: 2, options: options?.all_skills || [] }
  )

  const saveProfs = (
    options?.class_save_proficiencies?.[form?.char_class]
    || options?.class_save_proficiencies?.[classEnKey]
    || []
  )

  const isSpellcaster = !!options?.spellcaster_classes?.includes(classEnKey)
  const cantripCount = options?.starting_cantrips_count?.[classEnKey] || 0
  const spellCount = options?.starting_spells_count?.[classEnKey] || 0
  const availableCantrips = options?.class_cantrips?.[classEnKey] || []
  const availableSpells = options?.class_spells?.[classEnKey] || []

  const hasFightingStyle = !!(
    options?.fighting_style_classes?.[classEnKey]
    && form?.level >= (options.fighting_style_classes[classEnKey]?.level || 99)
  )

  const needsASI = (form?.level || 1) >= 4
  const asiLevels = classEnKey === 'Fighter'
    ? (options?.asi_levels_fighter || [4, 6, 8, 12, 14, 16, 19])
    : classEnKey === 'Rogue'
      ? (options?.asi_levels_rogue || [4, 8, 10, 12, 16, 19])
      : (options?.asi_levels || [4, 8, 12, 16, 19])
  const asiCount = asiLevels.filter((level) => (form?.level || 1) >= level).length

  const spellStep = isSpellcaster ? 5 : -1
  const featStep = needsASI ? (isSpellcaster ? 6 : 5) : -1
  const partyStep = (featStep > 0 ? featStep : (spellStep > 0 ? spellStep : 4)) + 1
  const styleStep = isMultiplayerCreate ? -1 : partyStep + 1

  const multiclassEnKey = getClassEnKey(form?.multiclass_class)
  const multiReqs = MULTICLASS_REQUIREMENTS[multiclassEnKey] || {}
  const multiReqMet = Object.entries(multiReqs).every(([ab, min]) => (finalScores[ab] || 0) >= min)

  const step1Valid = !!(
    form?.name?.trim()
    && form?.race
    && form?.char_class
    && (!form?.multiclassEnabled || (form?.multiclass_class && multiReqMet))
  )
  const step2Valid = scoreMethod === 'pointbuy'
    ? true
    : Object.keys(standardAssigned || {}).length === 6
  const step3Valid = (chosenSkills || []).length === skillConfig.count
  const step4Valid = (chosenCantrips || []).length === cantripCount
    && (chosenSpells || []).length === spellCount

  const showSubclass = !!(classInfo && (form?.level || 1) >= classInfo.subclass_unlock)
  const subclassOptions = classInfo?.subclasses || []

  const steps = getStepLabels({
    isSpellcaster,
    needsASI,
    isMultiplayerCreate,
  })

  return {
    classEnKey,
    classInfo,
    raceEnKey,
    racialBonuses,
    baseScores,
    finalScores,
    pointsSpent,
    pointsLeft,
    skillConfig,
    saveProfs,
    isSpellcaster,
    cantripCount,
    spellCount,
    availableCantrips,
    availableSpells,
    hasFightingStyle,
    needsASI,
    asiLevels,
    asiCount,
    spellStep,
    featStep,
    partyStep,
    styleStep,
    multiclassEnKey,
    multiReqs,
    multiReqMet,
    step1Valid,
    step2Valid,
    step3Valid,
    step4Valid,
    showSubclass,
    subclassOptions,
    steps,
  }
}
