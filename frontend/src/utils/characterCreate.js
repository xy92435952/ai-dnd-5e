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
const FULL_CASTER_CLASSES = new Set(['Wizard', 'Cleric', 'Druid', 'Sorcerer', 'Bard'])
const HALF_CASTER_CLASSES = new Set(['Paladin', 'Ranger'])
const PACT_CASTER_CLASSES = new Set(['Warlock'])

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

export function getFeatPrerequisiteFailure(feat, context = {}) {
  const featName = typeof feat === 'string' ? feat : feat?.name
  const prereq = String((typeof feat === 'string' ? '' : feat?.prereq) || '')
  const normalizedName = String(featName || '').trim().toLowerCase()
  const normalizedPrereq = prereq.trim().toLowerCase()
  const abilityScores = context.abilityScores || context.ability_scores || {}

  if (
    normalizedName === 'ritual caster'
    || normalizedPrereq.includes('intelligence or wisdom 13')
  ) {
    const intScore = Number(abilityScores.int || 0)
    const wisScore = Number(abilityScores.wis || 0)
    if (intScore < 13 && wisScore < 13) {
      return 'Requires INT or WIS 13+'
    }
  }

  if (normalizedName === 'war caster' || normalizedPrereq === 'spellcasting') {
    const spellSlots = context.spellSlots || context.spell_slots || context.derived?.spell_slots_max || {}
    const hasSlots = Object.values(spellSlots || {}).some(value => Number(value || 0) > 0)
    const hasSpells = (context.knownSpells || context.known_spells || []).length > 0
      || (context.cantrips || []).length > 0
    if (!context.isSpellcaster && !hasSlots && !hasSpells) {
      return 'Requires spellcasting'
    }
  }

  return ''
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

function spellName(spell) {
  return typeof spell === 'string' ? spell : spell?.name
}

function spellLevel(spell) {
  if (typeof spell === 'string') return null
  const level = Number(spell?.level)
  return Number.isFinite(level) ? level : null
}

function uniqueSpellNames(spells = []) {
  const seen = new Set()
  const names = []
  ;(spells || []).forEach((spell) => {
    const name = spellName(spell)
    if (!name || seen.has(name)) return
    seen.add(name)
    names.push(name)
  })
  return names
}

function normalizeSubclassSpellKey(subclass) {
  return String(subclass || '')
    .trim()
    .toLowerCase()
    .replace(/^the\s+/, '')
    .replace(/\s+domain$/, '')
}

function subclassSpellDetailsForLevel(options = {}, subclass = '', level = 1) {
  const detailsBySubclass = options?.subclass_bonus_spell_details || {}
  const details = detailsBySubclass[subclass]
    || detailsBySubclass[Object.keys(detailsBySubclass).find(
      key => normalizeSubclassSpellKey(key) === normalizeSubclassSpellKey(subclass),
    )]
  if (!details) return []
  if (Array.isArray(details)) return details

  return Object.entries(details || {})
    .filter(([threshold]) => Number(threshold) <= level)
    .flatMap(([, spells]) => spells || [])
}

function maxSpellLevelForClassLevel(classEnKey, level) {
  if (PACT_CASTER_CLASSES.has(classEnKey)) {
    if (level >= 9) return 5
    if (level >= 7) return 4
    if (level >= 5) return 3
    if (level >= 3) return 2
    if (level >= 1) return 1
    return 0
  }

  if (HALF_CASTER_CLASSES.has(classEnKey)) {
    if (level >= 17) return 5
    if (level >= 13) return 4
    if (level >= 9) return 3
    if (level >= 5) return 2
    if (level >= 2) return 1
    return 0
  }

  if (FULL_CASTER_CLASSES.has(classEnKey)) {
    if (level >= 17) return 9
    if (level >= 15) return 8
    if (level >= 13) return 7
    if (level >= 11) return 6
    if (level >= 9) return 5
    if (level >= 7) return 4
    if (level >= 5) return 3
    if (level >= 3) return 2
    if (level >= 1) return 1
  }

  return 0
}

function isAvailableAtSpellLevel(spell, maxSpellLevel) {
  const level = spellLevel(spell)
  return level === null || (level > 0 && level <= maxSpellLevel)
}

export function pruneUnavailableChoices(choices = [], available = [], limit = Infinity) {
  const availableSet = new Set(available || [])
  const seen = new Set()
  const pruned = []
  for (const choice of choices || []) {
    if (!availableSet.has(choice) || seen.has(choice)) continue
    seen.add(choice)
    pruned.push(choice)
    if (pruned.length >= limit) break
  }
  return pruned
}

function choicesAreValid(choices = [], available = [], expectedCount = 0) {
  const selected = (choices || []).filter(Boolean)
  if (selected.length !== expectedCount) return false
  return pruneUnavailableChoices(selected, available, expectedCount).length === expectedCount
}

export function buildStartingSpellOptions(options = {}, classEnKey = '', subclass = '', level = 1) {
  const characterLevel = Number(level) || 1
  const maxSpellLevel = maxSpellLevelForClassLevel(classEnKey, characterLevel)
  const classSpells = options?.class_spell_details?.[classEnKey] || options?.class_spells?.[classEnKey] || []
  const subclassSpells = subclassSpellDetailsForLevel(options, subclass, characterLevel)
  return uniqueSpellNames(
    [...classSpells, ...subclassSpells].filter(spell => isAvailableAtSpellLevel(spell, maxSpellLevel)),
  )
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
  const availableSpells = buildStartingSpellOptions(
    options,
    classEnKey,
    form?.subclass,
    form?.level || 1,
  )

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
  const step4Valid = choicesAreValid(chosenCantrips, availableCantrips, cantripCount)
    && choicesAreValid(chosenSpells, availableSpells, spellCount)

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
