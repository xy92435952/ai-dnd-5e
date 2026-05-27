import { describe, expect, it, vi } from 'vitest'
import { applyCombatSessionSnapshot, getPendingReactionPrompt } from '../combatSession'

describe('applyCombatSessionSnapshot', () => {
  it('syncs combat, player fields, turn state, and combat logs', () => {
    const setters = {
      setCombat: vi.fn(),
      setSession: vi.fn(),
      setPlayerId: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      setPlayerKnownSpells: vi.fn(),
      setPlayerCantrips: vi.fn(),
      setPlayerClass: vi.fn(),
      setPlayerLevel: vi.fn(),
      setClassResources: vi.fn(),
      setPlayerSubclass: vi.fn(),
      setPlayerSubclassEffects: vi.fn(),
      setTurnState: vi.fn(),
      setReactionPrompt: vi.fn(),
      setLogs: vi.fn(),
    }
    const combatData = {
      turn_order: [
        { character_id: 'char-1', name: 'Tester', is_player: true },
      ],
      turn_states: {
        'char-1': { action_used: false },
      },
    }
    const sessionData = {
      player: {
        id: 'char-1',
        spell_slots: { '1st': 2 },
        known_spells: ['Magic Missile'],
        cantrips: ['Fire Bolt'],
        char_class: 'Wizard',
        level: 3,
        class_resources: { arcane_recovery_used: false },
        subclass: 'Evocation',
        derived: { subclass_effects: { sculpt_spells: true } },
      },
      logs: [
        { log_type: 'combat', content: '战斗日志' },
        { log_type: 'narrative', content: '剧情日志' },
        { log_type: 'system', content: '系统日志' },
      ],
    }

    const result = applyCombatSessionSnapshot({ combatData, sessionData, ...setters })

    expect(setters.setCombat).toHaveBeenCalledWith(combatData)
    expect(setters.setSession).toHaveBeenCalledWith(sessionData)
    expect(setters.setPlayerId).toHaveBeenCalledWith('char-1')
    expect(setters.setPlayerSpellSlots).toHaveBeenCalledWith({ '1st': 2 })
    expect(setters.setPlayerClass).toHaveBeenCalledWith('Wizard')
    expect(setters.setTurnState).toHaveBeenCalledWith({ action_used: false })
    expect(setters.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(setters.setLogs).toHaveBeenCalledWith([
      { log_type: 'combat', content: '战斗日志' },
      { log_type: 'system', content: '系统日志' },
    ])
    expect(result.playerId).toBe('char-1')
    expect(result.playerEntry).toEqual({ character_id: 'char-1', name: 'Tester', is_player: true })
  })

  it('returns the current controlled player entry instead of the first player in initiative', () => {
    const setters = {
      setCombat: vi.fn(),
      setSession: vi.fn(),
      setPlayerId: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      setPlayerKnownSpells: vi.fn(),
      setPlayerCantrips: vi.fn(),
      setPlayerClass: vi.fn(),
      setPlayerLevel: vi.fn(),
      setClassResources: vi.fn(),
      setPlayerSubclass: vi.fn(),
      setPlayerSubclassEffects: vi.fn(),
      setTurnState: vi.fn(),
      setReactionPrompt: vi.fn(),
      setLogs: vi.fn(),
    }
    const combatData = {
      turn_order: [
        { character_id: 'host-char', name: 'Host Hero', is_player: true, initiative: 18, d20: 17 },
        { character_id: 'guest-char', name: 'Guest Hero', is_player: true, initiative: 12, d20: 11 },
      ],
      turn_states: {
        'guest-char': { action_used: false },
      },
    }
    const sessionData = {
      player: { id: 'guest-char', char_class: 'Wizard', level: 1 },
      logs: [],
    }

    const result = applyCombatSessionSnapshot({ combatData, sessionData, ...setters })

    expect(setters.setTurnState).toHaveBeenCalledWith({ action_used: false })
    expect(setters.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(result.playerId).toBe('guest-char')
    expect(result.playerEntry).toEqual({
      character_id: 'guest-char',
      name: 'Guest Hero',
      is_player: true,
      initiative: 12,
      d20: 11,
    })
  })

  it('restores a pending attack reaction prompt for the controlled player', () => {
    const setters = {
      setCombat: vi.fn(),
      setSession: vi.fn(),
      setPlayerId: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      setPlayerKnownSpells: vi.fn(),
      setPlayerCantrips: vi.fn(),
      setPlayerClass: vi.fn(),
      setPlayerLevel: vi.fn(),
      setClassResources: vi.fn(),
      setPlayerSubclass: vi.fn(),
      setPlayerSubclassEffects: vi.fn(),
      setTurnState: vi.fn(),
      setReactionPrompt: vi.fn(),
      setLogs: vi.fn(),
    }
    const pending = {
      trigger: 'incoming_attack',
      attacker_id: 'enemy-1',
      attacker_name: 'Orc',
      available_reactions: [{ type: 'shield' }],
    }

    applyCombatSessionSnapshot({
      combatData: {
        turn_order: [{ character_id: 'char-1', is_player: true }],
        turn_states: {
          'char-1': { pending_attack_reaction: pending },
        },
      },
      sessionData: { player: { id: 'char-1' }, logs: [] },
      ...setters,
    })

    expect(setters.setReactionPrompt).toHaveBeenCalledWith({
      ...pending,
      reactor_character_id: 'char-1',
    })
  })

  it('restores a pending spell reaction prompt and keeps backend reactor id', () => {
    const prompt = getPendingReactionPrompt({
      pending_spell_reaction: {
        trigger: 'spell_cast',
        caster_id: 'enemy-mage',
        reactor_character_id: 'wizard-2',
        options: [{ type: 'counterspell' }],
      },
    }, 'char-1')

    expect(prompt).toEqual({
      trigger: 'spell_cast',
      caster_id: 'enemy-mage',
      reactor_character_id: 'wizard-2',
      options: [{ type: 'counterspell' }],
    })
  })

  it('does not restore a prompt after the reaction was already used', () => {
    const prompt = getPendingReactionPrompt({
      reaction_used: true,
      pending_attack_reaction: {
        trigger: 'incoming_attack',
        available_reactions: [{ type: 'shield' }],
      },
    }, 'char-1')

    expect(prompt).toBeNull()
  })
})
