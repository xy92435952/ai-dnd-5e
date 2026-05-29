import { describe, expect, it } from 'vitest'
import {
  getReactionOptionHpPreview,
  getReactionPromptContext,
  getReactionPromptMeta,
  isReactionPromptForCharacter,
  normalizeReactionOptions,
} from '../combatReactionPrompt'

describe('combatReactionPrompt', () => {
  it('identifies whether a prompt belongs to the controlled character', () => {
    expect(isReactionPromptForCharacter({ reactor_character_id: 'char-1' }, 'char-1')).toBe(true)
    expect(isReactionPromptForCharacter({ reactor_character_id: 'char-1' }, 'char-2')).toBe(false)
    expect(isReactionPromptForCharacter({ reactor_character_id: 'char-1' }, null)).toBe(true)
    expect(isReactionPromptForCharacter({ context: 'legacy prompt' }, 'char-2')).toBe(true)
  })

  it('normalizes backend reaction options and fills target/reactor ids', () => {
    expect(normalizeReactionOptions({
      attacker_id: 'enemy-1',
      reactor_character_id: 'char-1',
      available_reactions: [
        {
          id: 'absorb_elements',
          type: 'absorb_elements',
          name: 'Absorb Elements',
          cost: '1st slot',
          effect: 'Reduce fire damage',
          damage_prevented: 4,
        },
      ],
    })).toEqual([
      {
        type: 'absorb_elements',
        target_id: 'enemy-1',
        character_id: 'char-1',
        label: 'Absorb Elements - Reduce fire damage',
        cost: '1st slot',
        damage_prevented: 4,
        hp_preview: '预计减免 4 伤害',
      },
    ])
  })

  it('previews reaction damage prevention as before and after hp', () => {
    expect(getReactionOptionHpPreview({
      target_hp_before_damage: 12,
      incoming_damage: 9,
    }, {
      damage_prevented: 4,
    })).toBe('HP 12 -> 3，反应后 7')
  })

  it('merges compact prompt options with rich available reaction details', () => {
    expect(normalizeReactionOptions({
      attacker_id: 'enemy-1',
      reactor_character_id: 'char-1',
      target_hp_before_damage: 12,
      incoming_damage: 9,
      available_reactions: [
        {
          id: 'shield',
          type: 'shield',
          name: 'Shield',
          cost: '1st-level spell slot',
          damage_prevented: 9,
        },
      ],
      options: [
        {
          type: 'shield',
          target_id: 'enemy-1',
          character_id: 'char-1',
          label: 'Shield - +5 AC',
        },
      ],
    })).toEqual([
      {
        type: 'shield',
        target_id: 'enemy-1',
        character_id: 'char-1',
        label: 'Shield - +5 AC',
        cost: '1st-level spell slot',
        damage_prevented: 9,
        hp_preview: 'HP 12 -> 3，反应后 12',
      },
    ])
  })

  it('summarizes prompt context and combat math', () => {
    expect(getReactionPromptContext({
      attacker_name: 'Cult Mage',
      spell_name: 'Hold Person',
      trigger: 'spell_cast',
    })).toBe('Cult Mage 正在施放 Hold Person')

    expect(getReactionPromptMeta({
      attack_roll: 19,
      player_ac: 15,
      incoming_damage: 11,
      target_hp_before_damage: 14,
      spell_name: 'Fireball',
      spell_level: 3,
    })).toEqual([
      '攻击 19 vs AC15',
      '伤害 11',
      'HP 14 -> 3',
      'Fireball 3环',
    ])
  })
})
