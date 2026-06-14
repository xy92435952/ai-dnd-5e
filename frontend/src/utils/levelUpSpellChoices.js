import {
  featRequiresAbilityChoice,
  getClassEnKey,
  getFeatPrerequisiteFailure,
} from './characterCreate'

const ABILITY_KEYS = ['str', 'dex', 'con', 'int', 'wis', 'cha']

const ASI_LEVELS = [4, 8, 12, 16, 19]
const ASI_LEVELS_FIGHTER = [4, 6, 8, 12, 14, 16, 19]
const ASI_LEVELS_ROGUE = [4, 8, 10, 12, 16, 19]

const CANTRIPS_KNOWN = {
  Wizard: { 1: 3, 4: 4, 10: 5 },
  Cleric: { 1: 3, 4: 4, 10: 5 },
  Druid: { 1: 2, 4: 3, 10: 4 },
  Sorcerer: { 1: 4, 4: 5, 10: 6 },
  Bard: { 1: 2, 4: 3, 10: 4 },
  Warlock: { 1: 2, 4: 3, 10: 4 },
}

const SPELLS_KNOWN = {
  Bard: {
    1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11, 9: 12, 10: 14,
    11: 15, 13: 16, 14: 18, 15: 19, 17: 20, 18: 22,
  },
  Ranger: {
    2: 2, 3: 3, 5: 4, 7: 5, 9: 6, 11: 7, 13: 8, 15: 9, 17: 10, 19: 11,
  },
  Sorcerer: {
    1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 11,
    11: 12, 13: 13, 15: 14, 17: 15,
  },
  Warlock: {
    1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 10,
    11: 11, 12: 11, 13: 12, 14: 12, 15: 13, 16: 13, 17: 14, 18: 14, 19: 15, 20: 15,
  },
}

const SLOT_LEVELS = {
  '1st': 1,
  '2nd': 2,
  '3rd': 3,
  '4th': 4,
  '5th': 5,
  '6th': 6,
  '7th': 7,
  '8th': 8,
  '9th': 9,
}

const FULL_CASTER_CLASSES = new Set(['Wizard', 'Cleric', 'Druid', 'Sorcerer', 'Bard'])
const HALF_CASTER_CLASSES = new Set(['Paladin', 'Ranger'])
const PACT_CASTER_CLASSES = new Set(['Warlock'])

function countFromProgressionTable(table, level) {
  let count = 0
  Object.entries(table || {}).forEach(([threshold, value]) => {
    if (level >= Number(threshold)) count = Number(value) || 0
  })
  return count
}

function cantripCountForClass(classKey, level) {
  return countFromProgressionTable(CANTRIPS_KNOWN[classKey], level)
}

function spellsKnownForClass(classKey, level) {
  return countFromProgressionTable(SPELLS_KNOWN[classKey], level)
}

function unique(values = []) {
  return [...new Set((values || []).filter(Boolean))]
}

function availableNew(existing = [], available = []) {
  const known = new Set(existing || [])
  return unique(available).filter(item => !known.has(item))
}

function getSpellName(spell) {
  return typeof spell === 'string' ? spell : spell?.name
}

function getSpellLevel(spell) {
  if (typeof spell === 'string') return null
  const level = Number(spell?.level)
  return Number.isFinite(level) ? level : null
}

function maxSlotLevelFromSlots(slots = {}) {
  return Object.entries(slots || {}).reduce((maxLevel, [slotKey, count]) => {
    if ((Number(count) || 0) <= 0) return maxLevel
    return Math.max(maxLevel, SLOT_LEVELS[slotKey] || Number.parseInt(slotKey, 10) || 0)
  }, 0)
}

function maxSpellLevelForClassLevel(classKey, level) {
  if (PACT_CASTER_CLASSES.has(classKey)) {
    if (level >= 9) return 5
    if (level >= 7) return 4
    if (level >= 5) return 3
    if (level >= 3) return 2
    if (level >= 1) return 1
    return 0
  }

  if (HALF_CASTER_CLASSES.has(classKey)) {
    if (level >= 17) return 5
    if (level >= 13) return 4
    if (level >= 9) return 3
    if (level >= 5) return 2
    if (level >= 2) return 1
    return 0
  }

  if (FULL_CASTER_CLASSES.has(classKey)) {
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

function eligibleLeveledSpellNames(spells = [], maxSpellLevel = 9) {
  return unique((spells || [])
    .filter(spell => {
      const level = getSpellLevel(spell)
      return level === null || (level > 0 && level <= maxSpellLevel)
    })
    .map(getSpellName))
}

function subclassSpellDetailsForLevel(options = {}, subclass = '', level = 1) {
  const subclassKey = (subclass || '').trim()
  if (!subclassKey) return []
  const spellDetails = options?.subclass_bonus_spell_details?.[subclassKey]
  if (!spellDetails) return []

  if (Array.isArray(spellDetails)) return spellDetails

  return Object.entries(spellDetails || {})
    .filter(([threshold]) => Number(threshold) <= level)
    .flatMap(([, spells]) => spells || [])
}

function classAndSubclassSpellDetails(character, options = {}, classKey, nextLevel) {
  const classSpells = options?.class_spell_details?.[classKey] || options?.class_spells?.[classKey] || []
  const subclassSpells = subclassSpellDetailsForLevel(options, character?.subclass, nextLevel)
  return [...classSpells, ...subclassSpells]
}

function asiLevelsForClass(classKey, options = {}) {
  if (classKey === 'Fighter') return options?.asi_levels_fighter || ASI_LEVELS_FIGHTER
  if (classKey === 'Rogue') return options?.asi_levels_rogue || ASI_LEVELS_ROGUE
  return options?.asi_levels || ASI_LEVELS
}

function featName(feat) {
  return typeof feat === 'string' ? feat : feat?.name
}

function normalizeFeatOptions(feats = {}) {
  if (Array.isArray(feats)) {
    return feats
      .map((feat) => (typeof feat === 'string' ? { name: feat } : feat))
      .filter(feat => feat?.name)
  }
  return Object.entries(feats || {}).map(([name, data]) => ({
    name,
    ...(data || {}),
  }))
}

function countFromLevelTable(table = {}, level) {
  return countFromProgressionTable(table, level)
}

function normalizeManeuverOptions(maneuvers = {}) {
  return Object.entries(maneuvers || {}).map(([id, data]) => ({
    id,
    ...(data || {}),
  }))
}

export function buildLevelUpAbilityChoicePlan(character, options = {}) {
  const classKey = getClassEnKey(character?.char_class)
  const currentLevel = Number(character?.level) || 1
  const nextLevel = currentLevel + 1
  const abilityScores = character?.ability_scores || {}
  const isAsiLevel = asiLevelsForClass(classKey, options).includes(nextLevel)
  const abilityOptions = {}

  ABILITY_KEYS.forEach((ability) => {
    const score = Number(abilityScores?.[ability] ?? 10)
    abilityOptions[ability] = {
      score,
      maxIncrease: isAsiLevel ? Math.max(0, Math.min(2, 20 - score)) : 0,
    }
  })
  const abilityCapacity = isAsiLevel
    ? Math.min(2, Object.values(abilityOptions).reduce((sum, item) => sum + item.maxIncrease, 0))
    : 0

  return {
    classKey,
    currentLevel,
    nextLevel,
    isAsiLevel,
    abilityCapacity,
    abilityOptions,
    needsChoices: abilityCapacity > 0,
  }
}

export function buildLevelUpFeatChoicePlan(character, options = {}) {
  const abilityPlan = buildLevelUpAbilityChoicePlan(character, options)
  const existingFeatNames = new Set((character?.feats || []).map(featName).filter(Boolean))
  const featOptions = abilityPlan.isAsiLevel
    ? normalizeFeatOptions(options?.feats)
      .filter(feat => !existingFeatNames.has(feat.name))
      .map(feat => ({
        ...feat,
        choiceType: featRequiresAbilityChoice(feat) ? 'ability' : null,
        unavailableReason: getFeatPrerequisiteFailure(feat, {
          abilityScores: character?.ability_scores,
          derived: character?.derived,
          knownSpells: character?.known_spells,
          cantrips: character?.cantrips,
          spellSlots: character?.spell_slots,
        }),
      }))
    : []

  return {
    classKey: abilityPlan.classKey,
    currentLevel: abilityPlan.currentLevel,
    nextLevel: abilityPlan.nextLevel,
    isFeatChoiceLevel: abilityPlan.isAsiLevel,
    featOptions,
    needsChoices: abilityPlan.isAsiLevel && featOptions.length > 0,
  }
}

export function buildLevelUpSubclassChoicePlan(character, options = {}) {
  const classKey = getClassEnKey(character?.char_class)
  const currentLevel = Number(character?.level) || 1
  const nextLevel = currentLevel + 1
  const unlockLevel = Number(options?.subclass_unlock_levels?.[classKey] || 3)
  const currentSubclass = character?.subclass || ''
  const rawOptions = options?.subclass_options?.[classKey] || []
  const subclassOptions = (rawOptions || [])
    .map((option) => (typeof option === 'string' ? { name: option } : option))
    .filter(option => option?.name)

  return {
    classKey,
    currentLevel,
    nextLevel,
    unlockLevel,
    isSubclassChoiceLevel: !currentSubclass && nextLevel >= unlockLevel,
    subclassOptions,
    needsChoices: !currentSubclass && nextLevel >= unlockLevel && subclassOptions.length > 0,
  }
}

export function buildLevelUpFightingStyleChoicePlan(character, options = {}) {
  const classKey = getClassEnKey(character?.char_class)
  const currentLevel = Number(character?.level) || 1
  const nextLevel = currentLevel + 1
  const currentStyle = character?.fighting_style || ''
  const styleConfig = options?.fighting_style_classes?.[classKey]
    || options?.fighting_style_classes?.[character?.char_class]
  const unlockLevel = Number(styleConfig?.level || 0)
  const styleNames = Array.isArray(styleConfig?.styles) ? styleConfig.styles : []
  const fightingStyles = options?.fighting_styles || {}
  const styleOptions = unique(styleNames)
    .map((name) => {
      const style = fightingStyles?.[name] || {}
      return {
        name,
        ...(typeof style === 'string' ? { zh: style } : style),
      }
    })
    .filter(style => style?.name)
  const isFightingStyleChoiceLevel = Boolean(styleConfig) && !currentStyle && unlockLevel > 0 && nextLevel >= unlockLevel

  return {
    classKey,
    currentLevel,
    nextLevel,
    unlockLevel,
    currentStyle,
    isFightingStyleChoiceLevel,
    styleOptions,
    needsChoices: isFightingStyleChoiceLevel && styleOptions.length > 0,
  }
}

export function buildLevelUpManeuverChoicePlan(character, options = {}, pendingSubclassName = '') {
  const classKey = getClassEnKey(character?.char_class)
  const currentLevel = Number(character?.level) || 1
  const nextLevel = currentLevel + 1
  const subclass = character?.subclass || pendingSubclassName || ''
  const isBattleMaster = classKey === 'Fighter' && subclass.toLowerCase() === 'battle master'
  const currentKnown = unique(character?.class_resources?.maneuvers_known || [])
  const requiredCount = isBattleMaster
    ? countFromLevelTable(options?.battle_master_maneuvers_known_by_level || { 3: 3, 7: 5, 10: 7, 15: 9 }, nextLevel)
    : 0
  const maneuverOptions = normalizeManeuverOptions(options?.maneuvers)
    .filter(option => !currentKnown.includes(option.id))
  const requiredChoices = Math.max(0, requiredCount - currentKnown.length)

  return {
    classKey,
    currentLevel,
    nextLevel,
    subclass,
    isBattleMaster,
    currentKnown,
    requiredCount,
    requiredChoices,
    maneuverOptions,
    needsChoices: requiredChoices > 0 && maneuverOptions.length > 0,
  }
}

export function buildLevelUpSpellChoicePlan(character, options = {}) {
  const classKey = getClassEnKey(character?.char_class)
  const currentLevel = Number(character?.level) || 1
  const nextLevel = currentLevel + 1
  const preparationType = options?.spell_preparation_type?.[classKey] || character?.preparation_type || ''
  const knownSpells = character?.known_spells || []
  const cantrips = character?.cantrips || []
  const classSpells = classAndSubclassSpellDetails(character, options, classKey, nextLevel)
  const classCantrips = options?.class_cantrips?.[classKey] || []
  const nextSpellSlotsMax = options?.spell_slots_by_class_level?.[classKey]?.[nextLevel]
    || character?.next_level_spell_slots_max
    || character?.derived_next?.spell_slots_max
    || character?.derived?.next_spell_slots_max
    || {}
  const maxSpellLevel = maxSlotLevelFromSlots(nextSpellSlotsMax) || maxSpellLevelForClassLevel(classKey, nextLevel)

  const spellCapacity = preparationType === 'spellbook' && classKey === 'Wizard'
    ? 2
    : preparationType === 'known'
      ? Math.max(0, spellsKnownForClass(classKey, nextLevel) - spellsKnownForClass(classKey, currentLevel))
      : 0
  const canReplaceSpell = preparationType === 'known' && knownSpells.length > 0
  const cantripCapacity = Math.max(
    0,
    cantripCountForClass(classKey, nextLevel) - cantripCountForClass(classKey, currentLevel),
  )
  const eligibleSpellOptions = eligibleLeveledSpellNames(classSpells, maxSpellLevel)

  return {
    classKey,
    currentLevel,
    nextLevel,
    preparationType,
    spellCapacity,
    cantripCapacity,
    canReplaceSpell,
    maxSpellLevel,
    spellOptions: spellCapacity > 0 ? availableNew(knownSpells, eligibleSpellOptions) : [],
    replacementKnownOptions: canReplaceSpell ? unique(knownSpells) : [],
    replacementNewOptions: canReplaceSpell ? availableNew(knownSpells, eligibleSpellOptions) : [],
    cantripOptions: cantripCapacity > 0 ? availableNew(cantrips, classCantrips) : [],
    needsChoices: spellCapacity > 0 || cantripCapacity > 0,
  }
}
