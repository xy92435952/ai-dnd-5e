import { describe, expect, it } from 'vitest'
import {
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
      spell_name: 'Fireball',
      spell_level: 3,
    })).toEqual([
      '攻击 19 vs AC15',
      '伤害 11',
      'Fireball 3环',
    ])
  })
})
