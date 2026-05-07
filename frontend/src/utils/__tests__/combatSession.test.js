import { describe, expect, it, vi } from 'vitest'
import { applyCombatSessionSnapshot } from '../combatSession'

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
    expect(setters.setLogs).toHaveBeenCalledWith([
      { log_type: 'combat', content: '战斗日志' },
      { log_type: 'system', content: '系统日志' },
    ])
    expect(result.playerId).toBe('char-1')
    expect(result.playerEntry).toEqual({ character_id: 'char-1', name: 'Tester', is_player: true })
  })
})
