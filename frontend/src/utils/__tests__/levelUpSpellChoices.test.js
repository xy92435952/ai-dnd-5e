import { describe, expect, it } from 'vitest'
import {
  buildLevelUpAbilityChoicePlan,
  buildLevelUpFeatChoicePlan,
  buildLevelUpFightingStyleChoicePlan,
  buildLevelUpManeuverChoicePlan,
  buildLevelUpSpellChoicePlan,
  buildLevelUpSubclassChoicePlan,
} from '../levelUpSpellChoices'

describe('buildLevelUpSpellChoicePlan', () => {
  it('offers wizard spellbook choices and filters spell details by next-level slots', () => {
    const plan = buildLevelUpSpellChoicePlan({
      char_class: 'Wizard',
      level: 2,
      known_spells: ['Magic Missile'],
      cantrips: ['Fire Bolt', 'Mage Hand', 'Light'],
    }, {
      spell_preparation_type: { Wizard: 'spellbook' },
      class_spell_details: {
        Wizard: [
          { name: 'Magic Missile', level: 1 },
          { name: 'Shield', level: 1 },
          { name: 'Shatter', level: 2 },
          { name: 'Fireball', level: 3 },
        ],
      },
      class_cantrips: { Wizard: ['Fire Bolt', 'Mage Hand', 'Light', 'Ray of Frost'] },
    })

    expect(plan.classKey).toBe('Wizard')
    expect(plan.nextLevel).toBe(3)
    expect(plan.spellCapacity).toBe(2)
    expect(plan.maxSpellLevel).toBe(2)
    expect(plan.spellOptions).toEqual(['Shield', 'Shatter'])
    expect(plan.cantripCapacity).toBe(0)
  })

  it('offers cantrip choices when the next level raises cantrip capacity', () => {
    const plan = buildLevelUpSpellChoicePlan({
      char_class: 'Wizard',
      level: 3,
      known_spells: ['Magic Missile'],
      cantrips: ['Fire Bolt', 'Mage Hand', 'Light'],
    }, {
      spell_preparation_type: { Wizard: 'spellbook' },
      class_spells: { Wizard: ['Magic Missile', 'Shield'] },
      class_cantrips: { Wizard: ['Fire Bolt', 'Mage Hand', 'Light', 'Ray of Frost'] },
    })

    expect(plan.cantripCapacity).toBe(1)
    expect(plan.cantripOptions).toEqual(['Ray of Frost'])
  })

  it('does not offer spellbook or known-spell choices for prepared casters', () => {
    const plan = buildLevelUpSpellChoicePlan({
      char_class: 'Cleric',
      level: 2,
      known_spells: [],
      cantrips: ['Sacred Flame'],
    }, {
      spell_preparation_type: { Cleric: 'prepared' },
      class_spells: { Cleric: ['Bless', 'Cure Wounds'] },
      class_cantrips: { Cleric: ['Sacred Flame'] },
    })

    expect(plan.spellCapacity).toBe(0)
    expect(plan.spellOptions).toEqual([])
    expect(plan.canReplaceSpell).toBe(false)
  })

  it('offers known-caster learning and optional replacement lists separately', () => {
    const stableLevel = buildLevelUpSpellChoicePlan({
      char_class: 'Warlock',
      level: 9,
      known_spells: ['Hellish Rebuke'],
      cantrips: ['Eldritch Blast'],
    }, {
      spell_preparation_type: { Warlock: 'known' },
      class_spells: { Warlock: ['Hellish Rebuke', 'Shield'] },
      class_cantrips: { Warlock: ['Eldritch Blast'] },
    })
    const increasingLevel = buildLevelUpSpellChoicePlan({
      char_class: 'Warlock',
      level: 10,
      known_spells: ['Hellish Rebuke'],
      cantrips: ['Eldritch Blast'],
    }, {
      spell_preparation_type: { Warlock: 'known' },
      class_spells: { Warlock: ['Hellish Rebuke', 'Shield'] },
      class_cantrips: { Warlock: ['Eldritch Blast'] },
    })

    expect(stableLevel.spellCapacity).toBe(0)
    expect(stableLevel.spellOptions).toEqual([])
    expect(stableLevel.canReplaceSpell).toBe(true)
    expect(stableLevel.replacementKnownOptions).toEqual(['Hellish Rebuke'])
    expect(stableLevel.replacementNewOptions).toEqual(['Shield'])
    expect(increasingLevel.spellCapacity).toBe(1)
    expect(increasingLevel.spellOptions).toEqual(['Shield'])
  })

  it('merges subclass expanded spell details into known-caster level-up options', () => {
    const plan = buildLevelUpSpellChoicePlan({
      char_class: 'Warlock',
      subclass: 'Fiend',
      level: 2,
      known_spells: ['Hellish Rebuke', 'Hex', 'Armor of Agathys'],
      cantrips: ['Eldritch Blast'],
    }, {
      spell_preparation_type: { Warlock: 'known' },
      class_spell_details: {
        Warlock: [
          { name: 'Hellish Rebuke', level: 1 },
          { name: 'Hex', level: 1 },
          { name: 'Armor of Agathys', level: 1 },
        ],
      },
      subclass_bonus_spell_details: {
        Fiend: {
          1: [
            { name: 'Burning Hands', level: 1 },
            { name: 'Command', level: 1 },
          ],
          3: [
            { name: 'Scorching Ray', level: 2 },
          ],
        },
      },
      class_cantrips: { Warlock: ['Eldritch Blast'] },
    })

    expect(plan.nextLevel).toBe(3)
    expect(plan.spellCapacity).toBe(1)
    expect(plan.maxSpellLevel).toBe(2)
    expect(plan.spellOptions).toEqual(['Burning Hands', 'Command', 'Scorching Ray'])
    expect(plan.replacementNewOptions).toEqual(['Burning Hands', 'Command', 'Scorching Ray'])
  })
})

describe('level-up martial and identity choice plans', () => {
  it('builds ASI capacity and respects class-specific ASI levels and the score cap', () => {
    const fighterPlan = buildLevelUpAbilityChoicePlan({
      char_class: 'Fighter',
      level: 5,
      ability_scores: { str: 18, dex: 20, con: 15, int: 10, wis: 12, cha: 8 },
    })
    const wizardPlan = buildLevelUpAbilityChoicePlan({
      char_class: 'Wizard',
      level: 5,
      ability_scores: { str: 8, dex: 14, con: 14, int: 18, wis: 12, cha: 10 },
    })

    expect(fighterPlan.nextLevel).toBe(6)
    expect(fighterPlan.isAsiLevel).toBe(true)
    expect(fighterPlan.abilityCapacity).toBe(2)
    expect(fighterPlan.abilityOptions.dex).toEqual({ score: 20, maxIncrease: 0 })
    expect(wizardPlan.isAsiLevel).toBe(false)
    expect(wizardPlan.needsChoices).toBe(false)
  })

  it('offers unselected feats only on ASI levels', () => {
    const plan = buildLevelUpFeatChoicePlan({
      char_class: 'Fighter',
      level: 3,
      feats: [{ name: 'Alert' }],
    }, {
      feats: {
        Alert: { desc: '+5 initiative' },
        Tough: { desc: '+2 HP per level' },
      },
    })

    expect(plan.isFeatChoiceLevel).toBe(true)
    expect(plan.featOptions).toEqual([{
      name: 'Tough',
      desc: '+2 HP per level',
      unavailableReason: '',
    }])
  })

  it('marks feat prerequisite failures in level-up feat options', () => {
    const blockedPlan = buildLevelUpFeatChoicePlan({
      char_class: 'Fighter',
      level: 3,
      ability_scores: { str: 16, dex: 14, con: 14, int: 12, wis: 12, cha: 8 },
      derived: { spell_slots_max: {} },
      spell_slots: {},
    }, {
      feats: {
        'Ritual Caster': { prereq: 'Intelligence or Wisdom 13', desc: 'Cast rituals' },
        Tough: { desc: '+2 HP per level' },
      },
    })
    const allowedPlan = buildLevelUpFeatChoicePlan({
      char_class: 'Fighter',
      level: 3,
      ability_scores: { str: 16, dex: 14, con: 14, int: 13, wis: 10, cha: 8 },
      derived: { spell_slots_max: {} },
      spell_slots: {},
    }, {
      feats: {
        'Ritual Caster': { prereq: 'Intelligence or Wisdom 13', desc: 'Cast rituals' },
      },
    })

    expect(blockedPlan.featOptions.find(feat => feat.name === 'Ritual Caster')).toEqual({
      name: 'Ritual Caster',
      prereq: 'Intelligence or Wisdom 13',
      desc: 'Cast rituals',
      unavailableReason: 'Requires INT or WIS 13+',
    })
    expect(blockedPlan.featOptions.find(feat => feat.name === 'Tough').unavailableReason).toBe('')
    expect(allowedPlan.featOptions[0].unavailableReason).toBe('')
  })

  it('offers subclass and fighting-style choices at their unlock levels', () => {
    const subclassPlan = buildLevelUpSubclassChoicePlan({
      char_class: 'Fighter',
      level: 2,
      subclass: '',
    }, {
      subclass_unlock_levels: { Fighter: 3 },
      subclass_options: { Fighter: ['Champion', 'Battle Master'] },
    })
    const fightingStylePlan = buildLevelUpFightingStyleChoicePlan({
      char_class: 'Paladin',
      level: 1,
      fighting_style: '',
    }, {
      fighting_styles: {
        Defense: { desc: 'AC +1' },
        Dueling: { desc: 'Damage +2' },
      },
      fighting_style_classes: {
        Paladin: { level: 2, styles: ['Defense', 'Dueling'] },
      },
    })

    expect(subclassPlan.needsChoices).toBe(true)
    expect(subclassPlan.subclassOptions).toEqual([{ name: 'Champion' }, { name: 'Battle Master' }])
    expect(fightingStylePlan.needsChoices).toBe(true)
    expect(fightingStylePlan.styleOptions).toEqual([
      { name: 'Defense', desc: 'AC +1' },
      { name: 'Dueling', desc: 'Damage +2' },
    ])
  })

  it('calculates Battle Master maneuver deficits from pending or existing subclasses', () => {
    const pendingPlan = buildLevelUpManeuverChoicePlan({
      char_class: 'Fighter',
      level: 2,
      subclass: '',
      class_resources: {},
    }, {
      maneuvers: {
        precision: { desc: 'Add die to attack' },
        trip: { desc: 'Knock prone' },
        disarm: { desc: 'Drop weapon' },
      },
      battle_master_maneuvers_known_by_level: { 3: 3, 7: 5 },
    }, 'Battle Master')
    const existingPlan = buildLevelUpManeuverChoicePlan({
      char_class: 'Fighter',
      level: 6,
      subclass: 'Battle Master',
      class_resources: { maneuvers_known: ['precision', 'trip', 'disarm'] },
    }, {
      maneuvers: {
        precision: { desc: 'Add die to attack' },
        trip: { desc: 'Knock prone' },
        disarm: { desc: 'Drop weapon' },
        riposte: { desc: 'Reaction attack' },
        menacing: { desc: 'Frighten target' },
      },
      battle_master_maneuvers_known_by_level: { 3: 3, 7: 5 },
    })

    expect(pendingPlan.requiredChoices).toBe(3)
    expect(pendingPlan.maneuverOptions.map(option => option.id)).toEqual(['precision', 'trip', 'disarm'])
    expect(existingPlan.requiredChoices).toBe(2)
    expect(existingPlan.maneuverOptions.map(option => option.id)).toEqual(['riposte', 'menacing'])
  })
})
