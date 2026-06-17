import { describe, expect, it, vi } from 'vitest'
import { applyCombatSessionSnapshot, getPendingReactionPrompt } from '../combatSession'

describe('applyCombatSessionSnapshot', () => {
  function createSetters(overrides = {}) {
    return {
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
      setLairActionPrompt: vi.fn(),
      setLegendaryActionPrompt: vi.fn(),
      setLogs: vi.fn(),
      ...overrides,
    }
  }

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
    expect(result.pendingReaction).toBeNull()
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

    const result = applyCombatSessionSnapshot({
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
    expect(result.pendingReaction).toEqual({
      ...pending,
      reactor_character_id: 'char-1',
    })
  })

  it('restores the controlled player pending reaction even during an enemy turn reload', () => {
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
      reactor_character_id: 'guest-char',
      available_reactions: [{ type: 'hellish_rebuke' }],
    }

    const result = applyCombatSessionSnapshot({
      combatData: {
        current_turn_index: 0,
        turn_order: [
          { character_id: 'enemy-1', is_enemy: true },
          { character_id: 'guest-char', is_player: true },
        ],
        turn_states: {
          'enemy-1': { action_used: true },
          'guest-char': { pending_attack_reaction: pending },
        },
      },
      sessionData: { player: { id: 'guest-char' }, logs: [] },
      ...setters,
    })

    expect(setters.setTurnState).toHaveBeenCalledWith({ pending_attack_reaction: pending })
    expect(setters.setReactionPrompt).toHaveBeenCalledWith(pending)
    expect(result.pendingReaction).toEqual(pending)
  })

  it('clears stale local reaction prompts when the refreshed controlled state has no pending reaction', () => {
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

    const result = applyCombatSessionSnapshot({
      combatData: {
        current_turn_index: 0,
        turn_order: [
          { character_id: 'enemy-1', is_enemy: true },
          { character_id: 'guest-char', is_player: true },
        ],
        turn_states: {
          'enemy-1': { action_used: true },
          'guest-char': { reaction_used: true },
        },
      },
      sessionData: { player: { id: 'guest-char' }, logs: [] },
      ...setters,
    })

    expect(setters.setTurnState).toHaveBeenCalledWith({ reaction_used: true })
    expect(setters.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(result.pendingReaction).toBeNull()
  })

  it('clears stale local boss control prompts when refreshed combat has no prompt', () => {
    const setters = createSetters()

    const result = applyCombatSessionSnapshot({
      combatData: {
        current_turn_index: 0,
        turn_order: [{ character_id: 'enemy-1', is_enemy: true }],
        turn_states: { 'char-1': { action_used: false } },
      },
      sessionData: { player: { id: 'char-1' }, logs: [] },
      ...setters,
    })

    expect(setters.setLairActionPrompt).toHaveBeenCalledWith(null)
    expect(setters.setLegendaryActionPrompt).toHaveBeenCalledWith(null)
    expect(result.lairActionPrompt).toBeNull()
    expect(result.legendaryActionPrompt).toBeNull()
  })

  it('restores a lair action prompt from combat snapshot and suppresses legendary prompt', () => {
    const setters = createSetters()
    const lairPrompt = {
      trigger: 'lair_action',
      source_id: 'dragon-lair',
      actions: [{ id: 'quake', name: 'Quake' }],
    }
    const legendaryPrompt = {
      trigger: 'legendary_action',
      actor_id: 'dragon',
      actions: [{ id: 'tail', name: 'Tail Attack' }],
    }

    const result = applyCombatSessionSnapshot({
      combatData: {
        turn_order: [],
        turn_states: {},
        lair_action_prompt: lairPrompt,
        legendary_action_prompt: legendaryPrompt,
      },
      sessionData: { player: null, logs: [] },
      ...setters,
    })

    expect(setters.setLairActionPrompt).toHaveBeenCalledWith(lairPrompt)
    expect(setters.setLegendaryActionPrompt).toHaveBeenCalledWith(null)
    expect(result.lairActionPrompt).toBe(lairPrompt)
    expect(result.legendaryActionPrompt).toBeNull()
  })

  it('restores a legendary action prompt from combat snapshot when no lair prompt is active', () => {
    const setters = createSetters()
    const legendaryPrompt = {
      trigger: 'legendary_action',
      actor_id: 'dragon',
      actions: [{ id: 'tail', name: 'Tail Attack' }],
    }

    const result = applyCombatSessionSnapshot({
      combatData: {
        turn_order: [],
        turn_states: {},
        legendary_action_prompt: legendaryPrompt,
      },
      sessionData: { player: null, logs: [] },
      ...setters,
    })

    expect(setters.setLairActionPrompt).toHaveBeenCalledWith(null)
    expect(setters.setLegendaryActionPrompt).toHaveBeenCalledWith(legendaryPrompt)
    expect(result.lairActionPrompt).toBeNull()
    expect(result.legendaryActionPrompt).toBe(legendaryPrompt)
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

  it('restores a pending Bardic spell-save prompt even when reaction was already used', () => {
    const prompt = getPendingReactionPrompt({
      reaction_used: true,
      pending_bardic_spell_save_reaction: {
        trigger: 'spell_save',
        reaction_type: 'bardic_spell_save',
        pending_spell_id: 'spell-1',
        target_id: 'char-1',
        die: 'd8',
        options: [{ type: 'bardic_spell_save', die: 'd8' }],
      },
    }, 'char-1')

    expect(prompt).toEqual({
      trigger: 'spell_save',
      reaction_type: 'bardic_spell_save',
      pending_spell_id: 'spell-1',
      target_id: 'char-1',
      die: 'd8',
      options: [{ type: 'bardic_spell_save', die: 'd8' }],
      reactor_character_id: 'char-1',
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
