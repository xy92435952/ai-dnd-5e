import { describe, expect, it } from 'vitest'
import {
  ABILITY_KEYS,
  POINT_BUY_TOTAL,
  SCORE_COSTS,
  STANDARD_ARRAY,
  applyRacialBonuses,
  buildCharacterCreateModel,
  buildStandardScores,
  formatHitDieLabel,
  getClassEnKey,
  getHitDieValue,
  getRaceEnKey,
  normalizeCharacterOptions,
  pruneUnavailableChoices,
} from '../characterCreate'

function makeOptions(overrides = {}) {
  return normalizeCharacterOptions({
    races: ['人类'],
    classes: ['战士'],
    backgrounds: ['士兵'],
    alignments: ['中立善良'],
    racial_bonuses: {
      Human: { str: 1, wis: 1 },
    },
    class_skill_choices: {
      Fighter: { count: 2, options: ['运动', '察觉'] },
    },
    class_save_proficiencies: {
      Fighter: ['str', 'con'],
    },
    all_skills: ['运动', '察觉', '洞察'],
    class_cantrips: {},
    class_spells: {},
    starting_cantrips_count: {},
    starting_spells_count: {},
    spellcaster_classes: [],
    fighting_style_classes: {
      Fighter: { level: 1, styles: ['Defense'] },
    },
    starting_equipment: {
      Fighter: [{ label: '默认方案', items: [] }],
    },
    background_features: {},
    racial_languages: {
      人类: { fixed: ['Common'], bonus: 1 },
    },
    all_languages: ['Common', 'Elvish'],
    feats: {},
    asi_levels: [4, 8, 12, 16, 19],
    ...overrides,
  })
}

function makeForm(overrides = {}) {
  return {
    name: '阿尔法',
    race: '人类',
    char_class: '战士',
    subclass: '',
    level: 4,
    background: '士兵',
    alignment: '中立善良',
    multiclassEnabled: false,
    multiclass_class: '',
    multiclass_level: 1,
    ...overrides,
  }
}

function makeScores(overrides = {}) {
  return {
    str: 8,
    dex: 8,
    con: 8,
    int: 8,
    wis: 8,
    cha: 8,
    ...overrides,
  }
}

describe('characterCreate helpers', () => {
  it('normalizes legacy option keys for racial bonuses', () => {
    const opts = normalizeCharacterOptions({
      racial_bonuses: { Human: { str: 1 } },
    })

    expect(opts.racial_bonuses.Human).toEqual({ str: 1 })
    expect(opts.racial_ability_bonuses.Human).toEqual({ str: 1 })
  })

  it('buildStandardScores maps assigned indices to the standard array', () => {
    const assigned = { str: 0, dex: 1, con: 2, int: 3, wis: 4, cha: 5 }
    expect(buildStandardScores(assigned)).toEqual({
      str: STANDARD_ARRAY[0],
      dex: STANDARD_ARRAY[1],
      con: STANDARD_ARRAY[2],
      int: STANDARD_ARRAY[3],
      wis: STANDARD_ARRAY[4],
      cha: STANDARD_ARRAY[5],
    })
  })

  it('applyRacialBonuses adds bonuses without mutating the base scores', () => {
    const base = makeScores()
    const out = applyRacialBonuses(base, { str: 2, wis: 1 })

    expect(out.str).toBe(10)
    expect(out.wis).toBe(9)
    expect(base.str).toBe(8)
  })

  it('resolves zh/en class and race keys', () => {
    expect(getClassEnKey('战士')).toBe('Fighter')
    expect(getRaceEnKey('人类')).toBe('Human')
  })

  it('parses and formats hit dice from SRD class metadata', () => {
    expect(getHitDieValue('d10')).toBe(10)
    expect(getHitDieValue(12)).toBe(12)
    expect(getHitDieValue('bad', 8)).toBe(8)
    expect(formatHitDieLabel('d10')).toBe('d10')
    expect(formatHitDieLabel(6)).toBe('d6')
  })

  it('builds the expected derived state for a level 4 fighter', () => {
    const options = makeOptions()
    const form = makeForm()
    const model = buildCharacterCreateModel({
      form,
      options,
      scoreMethod: 'pointbuy',
      scores: makeScores(),
      standardAssigned: {},
      chosenSkills: ['运动', '察觉'],
      chosenCantrips: [],
      chosenSpells: [],
      isMultiplayerCreate: false,
    })

    expect(model.classEnKey).toBe('Fighter')
    expect(model.raceEnKey).toBe('Human')
    expect(model.pointsSpent).toBe(0)
    expect(model.pointsLeft).toBe(POINT_BUY_TOTAL)
    expect(model.baseScores).toEqual(makeScores())
    expect(model.finalScores.str).toBe(9)
    expect(model.finalScores.wis).toBe(9)
    expect(model.saveProfs).toEqual(['str', 'con'])
    expect(model.skillConfig.count).toBe(2)
    expect(model.isSpellcaster).toBe(false)
    expect(model.hasFightingStyle).toBe(true)
    expect(model.needsASI).toBe(true)
    expect(model.asiCount).toBe(1)
    expect(model.partyStep).toBe(6)
    expect(model.styleStep).toBe(7)
    expect(model.steps).toEqual([
      '基础信息',
      '能力值',
      '技能熟练',
      '装备选择',
      '专长/属性提升',
      '确认队伍',
      'DM风格',
    ])
    expect(model.step1Valid).toBe(true)
    expect(model.step2Valid).toBe(true)
    expect(model.step3Valid).toBe(true)
    expect(model.step4Valid).toBe(true)
    expect(model.showSubclass).toBe(true)
  })

  it('merges current-level subclass expanded spells into starting spell choices', () => {
    const options = makeOptions({
      spellcaster_classes: ['Warlock'],
      starting_cantrips_count: { Warlock: 2 },
      starting_spells_count: { Warlock: 2 },
      class_cantrips: { Warlock: ['Eldritch Blast', 'Mage Hand'] },
      class_spell_details: {
        Warlock: [
          { name: 'Hex', level: 1 },
          { name: 'Armor of Agathys', level: 1 },
          { name: 'Misty Step', level: 2 },
        ],
      },
      subclass_bonus_spell_details: {
        'The Fiend': {
          1: [
            { name: 'Burning Hands', level: 1 },
            { name: 'Command', level: 1 },
          ],
          3: [{ name: 'Scorching Ray', level: 2 }],
        },
      },
    })
    const model = buildCharacterCreateModel({
      form: makeForm({
        char_class: 'Warlock',
        subclass: 'Fiend',
        level: 1,
      }),
      options,
      scoreMethod: 'pointbuy',
      scores: makeScores(),
      standardAssigned: {},
      chosenSkills: [],
      chosenCantrips: ['Eldritch Blast', 'Mage Hand'],
      chosenSpells: ['Hex', 'Command'],
      isMultiplayerCreate: false,
    })

    expect(model.availableSpells).toEqual([
      'Hex',
      'Armor of Agathys',
      'Burning Hands',
      'Command',
    ])
    expect(model.availableSpells).not.toContain('Scorching Ray')
    expect(model.availableSpells).not.toContain('Misty Step')
    expect(model.step4Valid).toBe(true)
  })

  it('rejects and prunes stale starting spell choices after subclass options change', () => {
    const options = makeOptions({
      spellcaster_classes: ['Warlock'],
      starting_cantrips_count: { Warlock: 2 },
      starting_spells_count: { Warlock: 2 },
      class_cantrips: { Warlock: ['Eldritch Blast', 'Mage Hand'] },
      class_spell_details: {
        Warlock: [
          { name: 'Hex', level: 1 },
          { name: 'Armor of Agathys', level: 1 },
        ],
      },
      subclass_bonus_spell_details: {
        'The Fiend': {
          1: [{ name: 'Command', level: 1 }],
        },
        'The Great Old One': {
          1: [{ name: 'Dissonant Whispers', level: 1 }],
        },
      },
    })

    const model = buildCharacterCreateModel({
      form: makeForm({
        char_class: 'Warlock',
        subclass: 'Great Old One',
        level: 1,
      }),
      options,
      scoreMethod: 'pointbuy',
      scores: makeScores(),
      standardAssigned: {},
      chosenSkills: [],
      chosenCantrips: ['Eldritch Blast', 'Mage Hand'],
      chosenSpells: ['Hex', 'Command'],
      isMultiplayerCreate: false,
    })

    expect(model.availableSpells).toEqual(['Hex', 'Armor of Agathys', 'Dissonant Whispers'])
    expect(model.step4Valid).toBe(false)
    expect(pruneUnavailableChoices(['Hex', 'Command', 'Hex', 'Armor of Agathys'], model.availableSpells, 2)).toEqual([
      'Hex',
      'Armor of Agathys',
    ])
  })
})
