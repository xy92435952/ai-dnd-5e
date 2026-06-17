import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { roomsGetMock } = vi.hoisted(() => ({
  roomsGetMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    combatAction: vi.fn(),
    getCombat: vi.fn(),
    move: vi.fn(),
    readyAction: vi.fn(),
  },
  roomsApi: {
    get: roomsGetMock,
  },
}))

import { gameApi } from '../../api/client'
import { useCombatPageActions } from '../useCombatPageActions'

describe('useCombatPageActions websocket sync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function renderActions(overrides = {}) {
    const deps = {
      sessionId: 'sess-1',
      setRoom: vi.fn(),
      myCharacterId: 'guest-char',
      playerId: 'guest-char',
      moveMode: false,
      isProcessing: false,
      canActThisTurn: true,
      selectedTarget: 'enemy-1',
      entities: {},
      entityPositions: {},
      playerPos: null,
      setError: vi.fn(),
      setCombat: vi.fn(),
      setTurnState: vi.fn(),
      setReactionPrompt: vi.fn(),
      setLairActionPrompt: vi.fn(),
      setLegendaryActionPrompt: vi.fn(),
      addLog: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setHelpMode: vi.fn(),
      handleAttack: vi.fn(),
      handleDash: vi.fn(),
      handleDisengage: vi.fn(),
      handleDodge: vi.fn(),
      handleClassFeature: vi.fn(),
      setMoveMode: vi.fn(),
      setAoePreview: vi.fn(),
      setAoeHover: vi.fn(),
      setAoeLockedCenter: vi.fn(),
      clearAoePreview: vi.fn(),
      onLoadCombat: vi.fn(),
      setCombatOver: vi.fn(),
      onCombatEnded: vi.fn(),
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', id: 'guest-char' }],
      },
      ...overrides,
    }
    return { deps, ...renderHook(() => useCombatPageActions(deps)) }
  }

  it('applies combat_update payloads and reloads the fresh combat snapshot', () => {
    const combat = {
      current_turn_index: 1,
      turn_order: [
        { character_id: 'host-char', is_player: true },
        { character_id: 'guest-char', is_player: true },
      ],
      turn_states: {
        'guest-char': { action_used: false, movement_used: 2 },
      },
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        combat,
        combat_over: true,
        outcome: { result: 'victory' },
      })
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combat)
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: false, movement_used: 2 })
    expect(deps.setCombatOver).toHaveBeenCalledWith({ result: 'victory' })
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('uses the controlled character turn state from combat_update snapshots', () => {
    const combat = {
      current_turn_index: 0,
      turn_order: [
        { character_id: 'enemy-1', is_player: false },
        { character_id: 'guest-char', is_player: true },
      ],
      turn_states: {
        'enemy-1': { action_used: true },
        'guest-char': { reaction_used: false, pending_attack_reaction: { trigger: 'incoming_attack' } },
      },
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        combat,
        player_can_react: false,
        reaction_prompt: null,
      })
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combat)
    expect(deps.setTurnState).toHaveBeenCalledWith({
      reaction_used: false,
      pending_attack_reaction: { trigger: 'incoming_attack' },
    })
  })

  it('restores a pending reaction prompt from the combat snapshot even when the websocket payload omits it', () => {
    const pending = {
      trigger: 'incoming_attack',
      attacker_id: 'enemy-1',
      attacker_name: 'Orc',
      available_reactions: [{ type: 'shield' }],
    }
    const combat = {
      current_turn_index: 0,
      turn_order: [
        { character_id: 'enemy-1', is_player: false },
        { character_id: 'guest-char', is_player: true },
      ],
      turn_states: {
        'enemy-1': { action_used: true },
        'guest-char': { reaction_used: false, pending_attack_reaction: pending },
      },
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        combat,
      })
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combat)
    expect(deps.setTurnState).toHaveBeenCalledWith({
      reaction_used: false,
      pending_attack_reaction: pending,
    })
    expect(deps.setReactionPrompt).toHaveBeenCalledWith({
      ...pending,
      reactor_character_id: 'guest-char',
      target_id: 'enemy-1',
    })
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('uses the controlled character turn state from turn_changed snapshots', () => {
    const combat = {
      current_turn_index: 0,
      turn_order: [
        { character_id: 'host-char', is_player: true },
        { character_id: 'guest-char', is_player: true },
      ],
      turn_states: {
        'host-char': { action_used: true },
        'guest-char': { movement_used: 2, movement_max: 6 },
      },
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'turn_changed',
        combat,
      })
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combat)
    expect(deps.setTurnState).toHaveBeenCalledWith({ movement_used: 2, movement_max: 6 })
  })

  it('restores a normalized reaction prompt directly from turn_changed events', () => {
    const combat = {
      current_turn_index: 0,
      turn_order: [
        { character_id: 'enemy-mage', is_player: false },
        { character_id: 'guest-char', is_player: true },
      ],
      turn_states: {
        'guest-char': { reaction_used: false },
      },
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'turn_changed',
        combat,
        player_can_react: true,
        reaction_prompt: {
          trigger: 'spell_cast',
          caster_id: 'enemy-mage',
          reactor_character_id: 'guest-char',
          options: [{ type: 'counterspell' }],
        },
      })
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combat)
    expect(deps.setTurnState).toHaveBeenCalledWith({ reaction_used: false })
    expect(deps.setReactionPrompt).toHaveBeenCalledWith({
      trigger: 'spell_cast',
      caster_id: 'enemy-mage',
      reactor_character_id: 'guest-char',
      target_id: 'enemy-mage',
      options: [{ type: 'counterspell', target_id: 'enemy-mage' }],
    })
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('clears stale reaction prompts on turn_changed events without active prompts', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'turn_changed',
        combat: {
          current_turn_index: 0,
          turn_order: [{ character_id: 'guest-char', is_player: true }],
          turn_states: {
            'guest-char': { reaction_used: false, action_used: false },
          },
        },
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('merges entity positions from combat_update before refreshing observers', () => {
    const { result, deps } = renderActions({
      combat: {
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', is_player: true }],
        entity_positions: {
          'enemy-1': { x: 4, y: 5 },
          'guest-char': { x: 2, y: 2 },
        },
      },
    })

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        entity_positions: {
          'enemy-1': { x: 6, y: 5 },
        },
      })
    })

    const updater = deps.setCombat.mock.calls[0][0]
    expect(updater({
      entity_positions: {
        'enemy-1': { x: 4, y: 5 },
        'guest-char': { x: 2, y: 2 },
      },
    })).toEqual(expect.objectContaining({
      entity_positions: {
        'enemy-1': { x: 6, y: 5 },
        'guest-char': { x: 2, y: 2 },
      },
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs ready action results carried by websocket combat and movement updates', () => {
    const { result, deps } = renderActions()
    const readyAction = {
      applied: true,
      action_type: 'attack',
      trigger: 'target_moves',
      actor_id: 'host-char',
      actor_name: 'Ready Host',
      target_id: 'guest-char',
      target_name: 'Ready Guest',
      condition_text: 'When Ready Guest moves, attack.',
      attack_result: { hit: true, attack_total: 19, target_ac: 12 },
      damage: 5,
      target_state: { target_id: 'guest-char', hp_after: 11 },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        combat: { current_turn_index: 1, turn_order: [], turn_states: {} },
        ready_action_results: [readyAction],
      })
    })

    act(() => {
      result.current.onWsEvent({
        type: 'entity_moved',
        entity_id: 'guest-char',
        position: { x: 7, y: 5 },
        ready_action_results: [readyAction],
      })
    })

    expect(deps.addLog).toHaveBeenCalledTimes(2)
    expect(deps.addLog).toHaveBeenNthCalledWith(1, expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      dice_result: expect.objectContaining({
        type: 'ready_action',
        actor_id: 'host-char',
        target_id: 'guest-char',
        condition_text: 'When Ready Guest moves, attack.',
        damage: 5,
        target_state: expect.objectContaining({ hp_after: 11 }),
      }),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(2)
  })

  it('logs opportunity attacks and hazards carried by websocket movement updates', () => {
    const { result, deps } = renderActions()
    const opportunity = {
      attacker: 'Goblin Guard',
      target: 'Moving Hero',
      attack_result: {
        hit: true,
        attack_total: 18,
        target_ac: 14,
      },
      damage: 5,
      damage_roll: { notation: '1d6+2', total: 5 },
      movement_stop: {
        applied: true,
        attacker: 'Goblin Guard',
        to: { x: 4, y: 5 },
      },
    }
    const hazard = {
      triggered: true,
      target_id: 'guest-char',
      target_name: 'Moving Hero',
      label: 'sparking conduit',
      cell: '4_5',
      damage_roll: { notation: '2d6', rolls: [4, 4], total: 8 },
      rolled_damage: 8,
      final_damage: 4,
      damage_type: 'lightning',
      hp_before: 10,
      hp_after: 6,
      saving_throw: {
        ability: 'dex',
        d20: 15,
        modifier: 2,
        total: 17,
        dc: 13,
        success: true,
      },
      save_success: true,
    }

    act(() => {
      result.current.onWsEvent({
        type: 'entity_moved',
        entity_id: 'guest-char',
        position: { x: 4, y: 5 },
        opportunity_attacks: [opportunity],
        hazard_result: hazard,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('Goblin Guard'),
      dice_result: expect.objectContaining({
        opportunity: true,
        attacker: 'Goblin Guard',
        target: 'Moving Hero',
        damage: 5,
        movement_stop: expect.objectContaining({ applied: true }),
      }),
    }))
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('sparking conduit'),
      dice_result: expect.objectContaining({
        type: 'hazard',
        total_damage: 4,
        hazard: expect.objectContaining({
          triggered: true,
          final_damage: 4,
          target_id: 'guest-char',
        }),
      }),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs movement metadata carried by websocket movement updates', () => {
    const { result, deps } = renderActions()
    const movement = {
      type: 'movement',
      entity_id: 'guest-char',
      entity_name: 'Scout Hero',
      from: { x: 5, y: 5 },
      to: { x: 6, y: 5 },
      distance_ft: 5,
      movement_cost: 2,
      movement_path: [{ x: 6, y: 5 }],
      difficult_terrain_extra: 1,
      difficult_terrain_cells: [{ cell: '6_5', terrain: 'difficult', label: 'Mud slick', extra_cost: 1 }],
      movement_used: 2,
      movement_max: 6,
      movement_remaining: 4,
    }

    act(() => {
      result.current.onWsEvent({
        type: 'entity_moved',
        entity_id: 'guest-char',
        position: { x: 6, y: 5 },
        narration: 'Scout Hero moves 5 ft from (5,5) to (6,5), costing 2 movement.',
        movement,
        dice_result: movement,
        special_action: movement,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('Scout Hero moves 5 ft'),
      dice_result: expect.objectContaining({
        type: 'movement',
        entity_id: 'guest-char',
        movement_cost: 2,
        difficult_terrain_extra: 1,
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('4/6'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('clears stale reaction prompts before reloading after movement updates', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'entity_moved',
        entity_id: 'enemy-1',
        position: { x: 5, y: 5 },
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('ends combat from websocket movement updates that carry combat_over', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'entity_moved',
        entity_id: 'guest-char',
        position: { x: 4, y: 5 },
        combat_over: true,
        outcome: 'victory',
      })
    })

    expect(deps.setCombatOver).toHaveBeenCalledWith('victory')
    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.setLairActionPrompt).toHaveBeenCalledWith(null)
    expect(deps.setLegendaryActionPrompt).toHaveBeenCalledWith(null)
    expect(deps.setTurnState).toHaveBeenCalledWith(null)
    expect(deps.setCombat).toHaveBeenCalledWith(null)
    expect(deps.onCombatEnded).toHaveBeenCalledWith('victory')
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('logs turn-advance payloads carried by websocket combat updates', () => {
    const { result, deps } = renderActions()
    const opportunity = {
      attacker: 'Goblin Guard',
      target: 'Moving Hero',
      attack_result: { hit: true, attack_total: 18, target_ac: 14 },
      damage: 5,
      damage_roll: { notation: '1d6+2', total: 5 },
      movement_stop: { applied: true, attacker: 'Goblin Guard' },
    }
    const hazard = {
      trigger: 'turn_start',
      target_id: 'enemy-1',
      target_name: 'Goblin',
      label: 'sparking conduit',
      final_damage: 3,
      damage_type: 'lightning',
      saving_throw: { ability: 'dex', d20: 4, modifier: 1, total: 5, dc: 99, success: false },
    }
    const expiredReadyAction = {
      actor_id: 'host-char',
      actor_name: 'Ready Host',
      target_id: 'guest-char',
      target_name: 'Ready Guest',
      action_type: 'spell',
      spell_name: 'Magic Missile',
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        opportunity_attacks: [opportunity],
        turn_start_hazard_log: 'Goblin triggers sparking conduit, taking 3 lightning damage. HP 7->4',
        turn_start_hazard: hazard,
        expired_ready_action: expiredReadyAction,
        ready_action_expired_log: 'Ready Host readied Magic Missile expired.',
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('Goblin Guard'),
      dice_result: expect.objectContaining({
        opportunity: true,
        attacker: 'Goblin Guard',
        target: 'Moving Hero',
        damage: 5,
        movement_stop: expect.objectContaining({ applied: true }),
      }),
    }))
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: 'Goblin triggers sparking conduit, taking 3 lightning damage. HP 7->4',
      dice_result: expect.objectContaining({
        type: 'hazard',
        total_damage: 3,
        hazard: expect.objectContaining({ target_id: 'enemy-1' }),
      }),
    }))
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: 'Ready Host readied Magic Missile expired.',
      dice_result: expect.objectContaining({
        type: 'ready_action_expired',
        applied: false,
        actor_id: 'host-char',
        spell_name: 'Magic Missile',
      }),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs condition end saves carried by websocket combat updates', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        confusion_end_save: {
          type: 'confusion_end_save',
          condition: 'confused',
          actor_id: 'host-char',
          actor_name: 'Confused Host',
          ended: true,
          save: { ability: 'wis', total: 20, dc: 15, success: true },
        },
        condition_end_saves: [{
          type: 'condition_end_save',
          condition: 'paralyzed',
          actor_id: 'guest-char',
          actor_name: 'Held Guest',
          spell_name: 'Hold Person',
          ended: false,
          save: { ability: 'wis', total: 10, dc: 13, success: false },
        }],
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('Confused Host'),
      dice_result: expect.objectContaining({
        type: 'confusion_end_save',
        ended: true,
        save: expect.objectContaining({ total: 20, dc: 15, success: true }),
      }),
    }))
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('Held Guest'),
      dice_result: expect.objectContaining({
        type: 'condition_end_save',
        ended: false,
        save: expect.objectContaining({ total: 10, dc: 13, success: false }),
      }),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs AI turn action payloads carried by websocket combat updates', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'enemy-1',
        actor_name: 'Goblin Guard',
        narration: 'Goblin Guard slashes Smoke Sentinel.',
        attack_result: {
          d20: 16,
          attack_total: 21,
          target_ac: 14,
          hit: true,
        },
        damage: 5,
        damage_roll: { notation: '1d6+2', rolls: [3], total: 5 },
        total_damage: 9,
        damage_type: 'piercing',
        crit_extra: 4,
        extra_damage_notes: ['Sneak Attack +4'],
        weapon_resource: {
          consumed: true,
          resource_type: 'ammunition',
          weapon: 'Shortbow',
          ammo_remaining: 0,
        },
        concentration_check: {
          broke: true,
          spell_name: 'Bless',
        },
        skirmisher_reposition: {
          from: { x: 4, y: 5 },
          to: { x: 6, y: 5 },
          steps: 2,
        },
        target_state: {
          target_id: 'guest-char',
          target_name: 'Smoke Sentinel',
          hp_before: 14,
          hp_after: 9,
        },
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'enemy',
      log_type: 'combat',
      content: 'Goblin Guard slashes Smoke Sentinel.',
      dice_result: expect.objectContaining({
        attack: expect.objectContaining({
          d20: 16,
          attack_total: 21,
          target_ac: 14,
          hit: true,
        }),
        damage: 5,
        damage_roll: expect.objectContaining({
          notation: '1d6+2',
          total: 5,
        }),
        total_damage: 9,
        damage_type: 'piercing',
        crit_extra: 4,
        extra_damage_notes: ['Sneak Attack +4'],
        weapon_resource: expect.objectContaining({
          weapon: 'Shortbow',
          ammo_remaining: 0,
        }),
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Smoke Sentinel'),
        expect.stringContaining('Bless'),
        expect.stringContaining('10ft'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player attack-roll prepare combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const attackPrepare = {
      type: 'attack_prepare',
      actor_id: 'host-char',
      actor_name: 'Host Fighter',
      target_id: 'enemy-1',
      target_name: 'Clockwork Sentry',
      action_type: 'melee',
      is_offhand: false,
      is_martial_arts: false,
      attack: {
        d20: 18,
        attack_total: 23,
        target_ac: 13,
        hit: true,
        is_crit: false,
        is_fumble: false,
        target_conditions: [],
      },
      hit: true,
      is_crit: false,
      is_fumble: false,
      damage_dice: '1d8+3',
      attacks_made: 1,
      attacks_max: 1,
      defender_interception: null,
      weapon_resource: null,
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Fighter',
        narration: 'Host Fighter attacks Clockwork Sentry and hits (23 vs AC13).',
        action: 'attack_roll',
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        attack_result: attackPrepare.attack,
        dice_result: attackPrepare,
        special_action: attackPrepare,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Fighter',
      log_type: 'combat',
      content: 'Host Fighter attacks Clockwork Sentry and hits (23 vs AC13).',
      dice_result: attackPrepare,
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player damage-roll combat_update payloads for observers', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Fighter',
        narration: 'Host Fighter drives a longsword into Clockwork Sentry.',
        action: 'attack',
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        target_new_hp: 2,
        attack_result: {
          d20: 18,
          attack_total: 23,
          target_ac: 13,
          hit: true,
          target_conditions: [],
        },
        damage: 7,
        total_damage: 7,
        damage_roll: {
          notation: '1d8+3',
          rolls: [4],
          total: 7,
        },
        damage_type: 'slashing',
        sneak_attack: true,
        sneak_attack_damage: 4,
        extra_damage_notes: ['Sneak Attack +4'],
        defender_interception: { defender_name: 'Shield Guard' },
        weapon_resource: {
          consumed: true,
          resource_type: 'thrown_weapon',
          weapon: 'Handaxe',
          quantity_remaining: 0,
        },
        target_state: {
          target_id: 'enemy-1',
          target_name: 'Clockwork Sentry',
          hp_current: 2,
        },
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Fighter',
      log_type: 'combat',
      content: 'Host Fighter drives a longsword into Clockwork Sentry.',
      dice_result: expect.objectContaining({
        attack: expect.objectContaining({
          d20: 18,
          attack_total: 23,
          target_ac: 13,
          hit: true,
        }),
        damage: 7,
        total_damage: 7,
        damage_roll: expect.objectContaining({
          notation: '1d8+3',
          rolls: [4],
          total: 7,
        }),
        damage_type: 'slashing',
        sneak_attack: true,
        sneak_attack_damage: 4,
        extra_damage_notes: ['Sneak Attack +4'],
        weapon_resource: expect.objectContaining({
          weapon: 'Handaxe',
          quantity_remaining: 0,
        }),
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Clockwork Sentry'),
        expect.stringContaining('2'),
        expect.stringContaining('Shield Guard'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player spell-confirm combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const spellResult = {
      dice: {
        notation: '3d4+3',
        rolls: [1, 2, 3],
        total: 9,
      },
      damage: 9,
      heal: 0,
      target_state: {
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        hp_after: 3,
      },
      caster_state: {
        target_id: 'host-char',
        concentration: null,
      },
      concentration_effect_updates: [{
        caster_id: 'host-char',
        spell_name: 'Bless',
        ended: true,
      }],
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Wizard',
        narration: 'Host Wizard sends magic missiles into Clockwork Sentry.',
        action: 'spell',
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        target_new_hp: 3,
        target_state: {
          target_id: 'enemy-1',
          target_name: 'Clockwork Sentry',
          hp_before: 12,
          hp_after: 3,
        },
        actor_state: {
          target_id: 'host-char',
          concentration: null,
        },
        caster_state: {
          target_id: 'host-char',
          concentration: null,
        },
        damage: 9,
        heal: 0,
        dice_result: spellResult,
        spell_result: spellResult,
        aoe_results: [],
        remaining_slots: { '1st': 0 },
        concentration_effect_updates: [{
          caster_id: 'host-char',
          spell_name: 'Bless',
          ended: true,
        }],
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Wizard',
      log_type: 'combat',
      content: 'Host Wizard sends magic missiles into Clockwork Sentry.',
      dice_result: expect.objectContaining({
        dice: expect.objectContaining({
          notation: '3d4+3',
          rolls: [1, 2, 3],
          total: 9,
        }),
        damage: 9,
        heal: 0,
        target_state: expect.objectContaining({
          target_id: 'enemy-1',
          hp_after: 3,
        }),
        concentration_effect_updates: [expect.objectContaining({
          spell_name: 'Bless',
          ended: true,
        })],
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Clockwork Sentry'),
        expect.stringContaining('3'),
        expect.stringContaining('1'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player spell-roll prepare combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const spellPrepare = {
      type: 'spell_prepare',
      actor_id: 'host-char',
      actor_name: 'Host Wizard',
      spell_name: 'Magic Missile',
      spell_level: 1,
      spell_type: 'damage',
      damage_dice: '3d4+3',
      heal_dice: null,
      save_type: null,
      save_dc: null,
      is_cantrip: false,
      is_aoe: false,
      is_concentration: false,
      target_count: 1,
      spell_attack_required: false,
      attack_roll: null,
      hit: null,
      is_crit: null,
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Wizard',
        narration: 'Host Wizard prepares Magic Missile toward Clockwork Sentry.',
        action: 'spell_roll',
        dice_result: spellPrepare,
        special_action: spellPrepare,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Wizard',
      log_type: 'combat',
      content: 'Host Wizard prepares Magic Missile toward Clockwork Sentry.',
      dice_result: spellPrepare,
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs legacy direct spell combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const spellResult = {
      dice: {
        base_roll: { notation: '3d4+3', rolls: [2, 3, 4], total: 12 },
        total: 12,
      },
      spell_name: 'Magic Missile',
      damage: 12,
      heal: 0,
      target_state: {
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        hp_after: 18,
      },
      aoe: [],
      total: 12,
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Wizard',
        narration: 'Host Wizard casts Magic Missile at Clockwork Sentry.',
        action: 'spell',
        target_id: 'enemy-1',
        target_new_hp: 18,
        target_state: {
          target_id: 'enemy-1',
          target_name: 'Clockwork Sentry',
          hp_before: 30,
          hp_after: 18,
        },
        damage: 12,
        heal: 0,
        dice_result: spellResult,
        spell_result: spellResult,
        aoe_results: [],
        resurrection_results: [],
        remaining_slots: { '1st': 0 },
        concentration_checks: [],
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Wizard',
      log_type: 'combat',
      content: 'Host Wizard casts Magic Missile at Clockwork Sentry.',
      dice_result: expect.objectContaining({
        spell_name: 'Magic Missile',
        damage: 12,
        heal: 0,
        total: 12,
        target_state: expect.objectContaining({
          target_id: 'enemy-1',
          hp_after: 18,
        }),
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Clockwork Sentry'),
        expect.stringContaining('18'),
        expect.stringContaining('1'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player divine smite combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const smiteResult = {
      type: 'divine_smite',
      slot_level: 1,
      dice: '2d8',
      damage: 9,
      roll: { notation: '2d8', rolls: [4, 5], total: 9 },
      target_id: 'enemy-1',
      target_name: 'Clockwork Sentry',
      target_new_hp: 3,
      target_state: {
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        hp_after: 3,
      },
      damage_type: 'radiant',
      remaining_slots: { '1st': 0 },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Paladin',
        narration: 'Host Paladin channels Divine Smite into Clockwork Sentry.',
        action: 'divine_smite',
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        target_new_hp: 3,
        target_state: {
          target_id: 'enemy-1',
          target_name: 'Clockwork Sentry',
          hp_current: 3,
          hp_after: 3,
        },
        damage: 9,
        total_damage: 9,
        damage_roll: { notation: '2d8', rolls: [4, 5], total: 9 },
        damage_type: 'radiant',
        dice_result: smiteResult,
        special_action: smiteResult,
        remaining_slots: { '1st': 0 },
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Paladin',
      log_type: 'combat',
      content: 'Host Paladin channels Divine Smite into Clockwork Sentry.',
      dice_result: expect.objectContaining({
        type: 'divine_smite',
        slot_level: 1,
        damage: 9,
        damage_type: 'radiant',
        target_state: expect.objectContaining({
          target_id: 'enemy-1',
          hp_after: 3,
        }),
        remaining_slots: { '1st': 0 },
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Clockwork Sentry'),
        expect.stringContaining('3'),
        expect.stringContaining('1'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player class-feature combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const classFeatureResult = {
      type: 'class_feature',
      feature: 'second_wind',
      dice_roll: { faces: 10, result: 5, label: 'Second Wind 1d10+1' },
      target_state: {
        target_id: 'host-char',
        target_name: 'Host Fighter',
        hp_current: 10,
        temporary_hp: 0,
        class_resources: { second_wind_used: true },
      },
      actor_state: {
        target_id: 'host-char',
        target_name: 'Host Fighter',
        hp_current: 10,
        temporary_hp: 0,
        class_resources: { second_wind_used: true },
      },
      class_resources: { second_wind_used: true },
      turn_state: { bonus_action_used: true },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Fighter',
        narration: 'Host Fighter uses Second Wind.',
        action: 'class_feature',
        feature: 'second_wind',
        target_id: 'host-char',
        target_name: 'Host Fighter',
        target_state: classFeatureResult.target_state,
        actor_state: classFeatureResult.actor_state,
        dice_result: classFeatureResult,
        special_action: classFeatureResult,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Fighter',
      log_type: 'combat',
      content: 'Host Fighter uses Second Wind.',
      dice_result: expect.objectContaining({
        type: 'class_feature',
        feature: 'second_wind',
        dice_roll: expect.objectContaining({ result: 5 }),
        target_state: expect.objectContaining({
          target_id: 'host-char',
          hp_current: 10,
        }),
        class_resources: { second_wind_used: true },
        turn_state: { bonus_action_used: true },
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Host Fighter'),
        expect.stringContaining('10'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player maneuver combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const maneuverResult = {
      type: 'maneuver',
      maneuver: 'trip',
      superiority_die_roll: 5,
      superiority_die: 'd8',
      dice_remaining: 0,
      actor_id: 'host-char',
      actor_name: 'Host Fighter',
      target_id: 'enemy-1',
      target_name: 'Clockwork Sentry',
      tripped: true,
      extra_damage: 5,
      target_state: {
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        conditions: ['prone'],
        condition_durations: {},
      },
      class_resources: { superiority_dice_remaining: 0 },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Fighter',
        narration: 'Host Fighter trips the Clockwork Sentry.',
        action: 'maneuver',
        maneuver: 'trip',
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        target_state: maneuverResult.target_state,
        dice_result: maneuverResult,
        special_action: maneuverResult,
        class_resources: { superiority_dice_remaining: 0 },
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Fighter',
      log_type: 'combat',
      content: 'Host Fighter trips the Clockwork Sentry.',
      dice_result: expect.objectContaining({
        type: 'maneuver',
        maneuver: 'trip',
        superiority_die_roll: 5,
        dice_remaining: 0,
        target_state: expect.objectContaining({
          target_id: 'enemy-1',
          conditions: ['prone'],
        }),
        class_resources: { superiority_dice_remaining: 0 },
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('状态'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player grapple combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const grappleResult = {
      type: 'grapple',
      success: true,
      attacker_name: 'Host Fighter',
      target_id: 'enemy-1',
      target_name: 'Clockwork Sentry',
      attacker_roll: { skill: 'Athletics', total: 18 },
      target_roll: { skill: 'Athletics', total: 10 },
      condition_result: { condition: 'grappled', applied: true, immune: false },
      target_state: {
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        conditions: ['grappled'],
        condition_durations: { grappled: { source_id: 'host-char' } },
      },
      turn_state: { attacks_made: 1, attacks_max: 2 },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Fighter',
        narration: 'Host Fighter grapples the Clockwork Sentry.',
        action: 'grapple',
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        target_state: grappleResult.target_state,
        condition_result: grappleResult.condition_result,
        dice_result: grappleResult,
        special_action: grappleResult,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Fighter',
      log_type: 'combat',
      content: 'Host Fighter grapples the Clockwork Sentry.',
      dice_result: expect.objectContaining({
        type: 'grapple',
        success: true,
        attacker_roll: expect.objectContaining({ total: 18 }),
        target_roll: expect.objectContaining({ total: 10 }),
        condition_result: expect.objectContaining({
          condition: 'grappled',
          applied: true,
        }),
        target_state: expect.objectContaining({
          target_id: 'enemy-1',
          conditions: ['grappled'],
        }),
        turn_state: { attacks_made: 1, attacks_max: 2 },
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Clockwork Sentry'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs player death-save combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const deathSaveResult = {
      type: 'death_save',
      character_id: 'guest-char',
      character_name: 'Guest Wizard',
      target_id: 'guest-char',
      target_name: 'Guest Wizard',
      d20: 20,
      outcome: 'revive',
      revived: true,
      hp_current: 1,
      life_state: 'alive',
      death_saves: { successes: 0, failures: 0, stable: false },
      target_state: {
        target_id: 'guest-char',
        target_name: 'Guest Wizard',
        hp_current: 1,
        death_saves: { successes: 0, failures: 0, stable: false },
        conditions: [],
        life_state: 'alive',
      },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'guest-char',
        actor_name: 'Guest Wizard',
        narration: 'Guest Wizard rolled a natural 20 and regains 1 HP.',
        action: 'death_save',
        target_id: 'guest-char',
        target_name: 'Guest Wizard',
        target_state: deathSaveResult.target_state,
        death_save: deathSaveResult,
        dice_result: deathSaveResult,
        special_action: deathSaveResult,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Guest Wizard',
      log_type: 'combat',
      content: 'Guest Wizard rolled a natural 20 and regains 1 HP.',
      dice_result: expect.objectContaining({
        type: 'death_save',
        d20: 20,
        outcome: 'revive',
        revived: true,
        target_state: expect.objectContaining({
          target_id: 'guest-char',
          hp_current: 1,
        }),
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Guest Wizard'),
        expect.stringContaining('1'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs redacted ready-action declaration combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const redactedReadyAction = {
      type: 'ready_action',
      redacted: true,
      visibility: 'other_character',
      actor_id: 'host-char',
      actor_name: 'Host Fighter',
    }
    const readyDeclaration = {
      type: 'ready_action_declared',
      ready_action: redactedReadyAction,
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Fighter',
        narration: 'Host Fighter readies an action.',
        action: 'ready_action',
        ready_action: redactedReadyAction,
        dice_result: readyDeclaration,
        special_action: readyDeclaration,
        remaining_slots: null,
        actor_state: null,
        caster_state: null,
        concentration_started: false,
        concentration_spell_name: null,
        concentration_effect_updates: [],
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Fighter',
      log_type: 'combat',
      content: 'Host Fighter readies an action.',
      dice_result: expect.objectContaining({
        type: 'ready_action_declared',
        ready_action: expect.objectContaining({
          type: 'ready_action',
          redacted: true,
          visibility: 'other_character',
          actor_id: 'host-char',
        }),
      }),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs redacted concentration-end combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const readyActionFailed = {
      type: 'ready_action_failed',
      redacted: true,
      visibility: 'other_character',
      actor_id: 'host-char',
      actor_name: 'Host Wizard',
    }
    const concentrationEnd = {
      type: 'concentration_end',
      actor_id: 'host-char',
      actor_name: 'Host Wizard',
      concentration_ended: true,
      concentration_spell_name: null,
      ready_action_failed: readyActionFailed,
      actor_state: {
        target_id: 'host-char',
        target_name: 'Host Wizard',
        concentration: null,
        ready_action_failed: readyActionFailed,
      },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'host-char',
        actor_name: 'Host Wizard',
        narration: 'Host Wizard ends concentration.',
        action: 'concentration_end',
        concentration_ended: true,
        concentration_spell_name: null,
        ready_action_failed: readyActionFailed,
        actor_state: concentrationEnd.actor_state,
        caster_state: concentrationEnd.actor_state,
        dice_result: concentrationEnd,
        special_action: concentrationEnd,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Host Wizard',
      log_type: 'combat',
      content: 'Host Wizard ends concentration.',
      dice_result: expect.objectContaining({
        type: 'concentration_end',
        concentration_ended: true,
        ready_action_failed: expect.objectContaining({
          type: 'ready_action_failed',
          redacted: true,
          actor_id: 'host-char',
        }),
      }),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs manual condition update combat_update payloads for observers', () => {
    const { result, deps } = renderActions()
    const conditionUpdate = {
      type: 'condition_update',
      condition: 'blessed',
      condition_action: 'add',
      condition_result: {
        condition: 'blessed',
        condition_action: 'add',
        applied: true,
        removed: false,
        immune: false,
        target_id: 'guest-char',
        target_name: 'Guest Wizard',
      },
      target_id: 'guest-char',
      target_name: 'Guest Wizard',
      target_state: {
        target_id: 'guest-char',
        target_name: 'Guest Wizard',
        conditions: ['blessed'],
        condition_durations: { blessed: 2 },
      },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'guest-char',
        actor_name: 'Guest Wizard',
        narration: 'Guest Wizard gains condition: blessed for 2 round(s).',
        action: 'condition_add',
        target_id: 'guest-char',
        target_name: 'Guest Wizard',
        target_state: conditionUpdate.target_state,
        condition: 'blessed',
        condition_action: 'add',
        condition_result: conditionUpdate.condition_result,
        dice_result: conditionUpdate,
        special_action: conditionUpdate,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'companion_Guest Wizard',
      log_type: 'combat',
      content: 'Guest Wizard gains condition: blessed for 2 round(s).',
      dice_result: expect.objectContaining({
        type: 'condition_update',
        condition: 'blessed',
        condition_action: 'add',
        condition_result: expect.objectContaining({
          applied: true,
          target_id: 'guest-char',
        }),
        target_state: expect.objectContaining({
          target_id: 'guest-char',
          conditions: ['blessed'],
        }),
      }),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('sets reaction prompts from typed combat_update payloads', () => {
    const prompt = {
      trigger: 'incoming_attack',
      reactor_character_id: 'guest-char',
      options: [{ type: 'shield' }],
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        player_can_react: true,
        reaction_prompt: prompt,
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith(prompt)
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('sets and clears lair action prompts from combat_update events', () => {
    const prompt = {
      trigger: 'lair_action',
      timing: 'initiative_count_20',
      actions: [{ id: 'seismic-pulse', name: 'Seismic Pulse' }],
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        lair_action_prompt: prompt,
      })
    })

    expect(deps.setLairActionPrompt).toHaveBeenCalledWith(prompt)

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        lair_action: { action_id: 'seismic-pulse' },
      })
    })

    expect(deps.setLairActionPrompt).toHaveBeenLastCalledWith(null)
  })

  it('sets legendary action prompts from combat_update events and pauses reload', () => {
    const prompt = {
      trigger: 'legendary_action',
      actor_id: 'dragon-1',
      actor_name: 'Dragon',
      actions: [{ id: 'tail', name: 'Tail Attack' }],
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        legendary_action_prompt: prompt,
      })
    })

    expect(deps.setLegendaryActionPrompt).toHaveBeenCalledWith(prompt)
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('clears boss prompts from combat_update skip events', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        action: 'lair_action_skip',
      })
    })

    expect(deps.setLairActionPrompt).toHaveBeenCalledWith(null)

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        action: 'legendary_action_skip',
      })
    })

    expect(deps.setLegendaryActionPrompt).toHaveBeenCalledWith(null)
  })

  it('pauses reload for legendary prompts surfaced by reaction combat updates', () => {
    const prompt = {
      trigger: 'legendary_action',
      actor_id: 'dragon-1',
      actor_name: 'Dragon',
      actions: [{ id: 'tail', name: 'Tail Attack' }],
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'guest-char',
        actor_name: 'Smoke Sentinel',
        reaction_type: 'counterspell',
        legendary_action_prompt: prompt,
      })
    })

    expect(deps.setLegendaryActionPrompt).toHaveBeenCalledWith(prompt)
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('logs reaction effect payloads carried by combat_update events', () => {
    const { result, deps } = renderActions()
    const reactionResult = {
      type: 'reaction',
      reaction_type: 'shield',
      damage_prevented: 5,
      hp_before_reaction: 4,
      hp_after_reaction: 9,
      slot_used: '1st',
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'guest-char',
        actor_name: 'Smoke Sentinel',
        narration: 'Smoke Sentinel uses Shield and turns the hit aside.',
        action: 'reaction',
        reaction_type: 'shield',
        reaction_effect: {
          damage_prevented: 5,
          hp_before_reaction: 4,
          hp_after_reaction: 9,
        },
        target_state: {
          target_id: 'guest-char',
          target_name: 'Smoke Sentinel',
          hp_after: 9,
        },
        remaining_slots: { '1st': 0 },
        dice_result: reactionResult,
        special_action: reactionResult,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: 'Smoke Sentinel uses Shield and turns the hit aside.',
      log_type: 'combat',
      dice_result: expect.objectContaining({
        type: 'reaction',
        reaction_type: 'shield',
        damage_prevented: 5,
        hp_after_reaction: 9,
      }),
      state_changes: expect.arrayContaining([
        expect.stringContaining('Smoke Sentinel'),
        expect.stringContaining('4'),
        expect.stringContaining('9'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs enemy inspect payloads carried by combat_update events', () => {
    const { result, deps } = renderActions()
    const inspectResult = {
      type: 'enemy_inspect',
      actor_id: 'guest-char',
      actor_name: 'Smoke Sentinel',
      target_id: 'enemy-1',
      target_name: 'Private Stalker',
      skill: 'investigation',
      dc: 12,
      check: { d20: 18, modifier: 1, total: 19, success: true },
      success: true,
      revealed_stats: ['actions'],
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'guest-char',
        actor_name: 'Smoke Sentinel',
        narration: '[Inspect] Smoke Sentinel inspected Private Stalker: 19 vs DC 12 (success)',
        action: 'enemy_inspect',
        target_id: 'enemy-1',
        target_name: 'Private Stalker',
        inspect_result: inspectResult,
        dice_result: inspectResult,
        special_action: inspectResult,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: '[Inspect] Smoke Sentinel inspected Private Stalker: 19 vs DC 12 (success)',
      log_type: 'combat',
      dice_result: expect.objectContaining({
        type: 'enemy_inspect',
        target_id: 'enemy-1',
        skill: 'investigation',
        dc: 12,
        revealed_stats: ['actions'],
      }),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('lets lair prompts win over legendary prompts on combat_update events', () => {
    const lairPrompt = {
      trigger: 'lair_action',
      source_id: 'lair-1',
      actions: [{ id: 'pulse', name: 'Seismic Pulse' }],
    }
    const legendaryPrompt = {
      trigger: 'legendary_action',
      actor_id: 'dragon-1',
      actions: [{ id: 'tail', name: 'Tail Attack' }],
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        lair_action_prompt: lairPrompt,
        legendary_action_prompt: legendaryPrompt,
      })
    })

    expect(deps.setLairActionPrompt).toHaveBeenCalledWith(lairPrompt)
    expect(deps.setLegendaryActionPrompt).toHaveBeenCalledWith(null)
    expect(deps.setLegendaryActionPrompt).not.toHaveBeenCalledWith(legendaryPrompt)
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('clears legendary prompts when a combat_update carries a resolved legendary action', () => {
    const { result, deps } = renderActions()
    const legendaryAction = {
      type: 'legendary_action',
      actor_id: 'dragon-1',
      action_id: 'tail',
      target_id: 'guest-char',
      attack: { hit: true, attack_total: 18, target_ac: 14 },
      damage: 9,
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'dragon-1',
        actor_name: 'Dragon',
        narration: 'Dragon lashes out with Tail Attack.',
        action: 'legendary_action',
        legendary_action: legendaryAction,
        dice_result: legendaryAction,
        special_action: legendaryAction,
        target_state: {
          target_id: 'guest-char',
          target_name: 'Smoke Sentinel',
          hp_after: 6,
        },
      })
    })

    expect(deps.setLegendaryActionPrompt).toHaveBeenCalledWith(null)
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: 'Dragon lashes out with Tail Attack.',
      dice_result: legendaryAction,
      state_changes: expect.arrayContaining([
        expect.stringContaining('Smoke Sentinel'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('clears lair prompts when a combat_update carries a resolved lair action', () => {
    const { result, deps } = renderActions()
    const lairAction = {
      type: 'lair_action',
      actor_id: 'dragon-1',
      actor_name: 'Dragon',
      action_id: 'seismic-pulse',
      action_name: 'Seismic Pulse',
      target_id: 'guest-char',
      target_name: 'Smoke Sentinel',
      save: { ability: 'dex', dc: 15, total: 9, success: false },
      damage: 8,
      total_damage: 8,
      damage_roll: { notation: '2d6', rolls: [3, 5], total: 8 },
      damage_type: 'force',
      target_state: {
        target_id: 'guest-char',
        target_name: 'Smoke Sentinel',
        hp_current: 7,
      },
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        actor_id: 'dragon-1',
        actor_name: 'Dragon',
        narration: 'Dragon uses Lair Action: Seismic Pulse.',
        action: 'lair_action',
        lair_action: lairAction,
        dice_result: lairAction,
        special_action: lairAction,
        target_id: 'guest-char',
        target_name: 'Smoke Sentinel',
        save: lairAction.save,
        damage: 8,
        total_damage: 8,
        damage_roll: lairAction.damage_roll,
        damage_type: 'force',
        target_state: lairAction.target_state,
      })
    })

    expect(deps.setLairActionPrompt).toHaveBeenCalledWith(null)
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: 'Dragon uses Lair Action: Seismic Pulse.',
      dice_result: lairAction,
      state_changes: expect.arrayContaining([
        expect.stringContaining('Smoke Sentinel'),
      ]),
    }))
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('builds shaped AoE previews from hovered spells', () => {
    const { result, deps } = renderActions({
      selectedTarget: 'enemy-1',
      entityPositions: {
        'enemy-1': { x: 7, y: 4 },
      },
      playerPos: { x: 2, y: 2 },
    })

    act(() => {
      result.current.handleSpellHover({
        name: 'Burning Hands',
        aoe: true,
        desc: '15尺锥形区域喷射火焰',
      })
    })

    expect(deps.setAoePreview).toHaveBeenCalledWith({
      radius: 3,
      template: 'cone',
      spellName: 'Burning Hands',
    })
    expect(deps.setAoeHover).toHaveBeenCalledWith('7_4')

    act(() => {
      result.current.handleSpellHover({
        name: 'Spirit Guardians',
        aoe: true,
        desc: '15尺内敌人减速',
      })
    })

    expect(deps.setAoePreview).toHaveBeenLastCalledWith({
      radius: 3,
      template: 'aura',
      spellName: 'Spirit Guardians',
    })
    expect(deps.setAoeHover).toHaveBeenLastCalledWith('2_2')
  })

  it('uses returned combat snapshot and logs hazard damage after movement', async () => {
    const addLog = vi.fn()
    const combatSnapshot = {
      entity_positions: {
        'guest-char': { x: 4, y: 5 },
      },
      entities: {
        'guest-char': { id: 'guest-char', hp_current: 6 },
      },
    }
    gameApi.move.mockResolvedValue({
      combat: combatSnapshot,
      turn_state: { movement_used: 1, movement_max: 6 },
      hazard_result: {
        triggered: true,
        target_id: 'guest-char',
        target_name: 'Hero',
        label: 'sparking conduit',
        cell: '4_5',
        damage_roll: { notation: '2d6', rolls: [4, 4], total: 8 },
        rolled_damage: 8,
        final_damage: 4,
        damage_type: 'lightning',
        hp_before: 10,
        hp_after: 6,
        saving_throw: {
          ability: 'dex',
          d20: 15,
          modifier: 2,
          total: 17,
          dc: 13,
          success: true,
        },
        save_success: true,
      },
    })
    const { result, deps } = renderActions({
      moveMode: true,
      addLog,
    })

    await act(async () => {
      await result.current.handleMoveTo(4, 5)
    })

    expect(gameApi.move).toHaveBeenCalledWith('sess-1', 'guest-char', 4, 5, '1:0:guest-char')
    expect(deps.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(deps.setTurnState).toHaveBeenCalledWith({ movement_used: 1, movement_max: 6 })
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('敏捷豁免 17 vs DC13 成功'),
      dice_result: expect.objectContaining({
        type: 'hazard',
        damage: 8,
        total_damage: 4,
        damage_roll: expect.objectContaining({ notation: '2d6', total: 8 }),
        dc_source: expect.objectContaining({
          trigger: 'movement_hazard',
        }),
        saving_throw: expect.objectContaining({ ability: 'dex', success: true }),
        target_state: expect.objectContaining({ target_name: 'Hero', hp_after: 6 }),
      }),
    }))
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('logs hazards nested in ready movement results returned by movement', async () => {
    const addLog = vi.fn()
    const combatSnapshot = {
      entity_positions: {
        'guest-char': { x: 4, y: 5 },
        'ally-1': { x: 5, y: 6 },
      },
      entities: {
        'ally-1': { id: 'ally-1', hp_current: 14 },
      },
    }
    gameApi.move.mockResolvedValue({
      combat: combatSnapshot,
      turn_state: { movement_used: 1, movement_max: 6 },
      ready_action_results: [{
        type: 'ready_action',
        action_type: 'move',
        applied: true,
        trigger: 'target_moves',
        actor_id: 'ally-1',
        actor_name: 'Mara Quickstep',
        target_id: 'guest-char',
        target_name: 'Hero',
        from: { x: 5, y: 5 },
        to: { x: 5, y: 6 },
        steps: 1,
        distance_ft: 5,
        hazard_result: {
          triggered: true,
          target_id: 'ally-1',
          target_name: 'Mara Quickstep',
          target_type: 'character',
          label: 'Sparking Conduit',
          terrain: 'hazard',
          cell: '5_6',
          trigger: 'movement_hazard',
          damage_dice: '2d6',
          damage_type: 'lightning',
          damage_roll: { notation: '2d6', rolls: [3, 3], total: 6 },
          rolled_damage: 6,
          damage: 6,
          final_damage: 6,
          hp_before: 20,
          hp_after: 14,
          saving_throw: {
            ability: 'dex',
            d20: 5,
            modifier: 1,
            total: 6,
            dc: 99,
            success: false,
          },
          save_success: false,
          ready_action: true,
        },
        actor_state: {
          target_id: 'ally-1',
          target_name: 'Mara Quickstep',
          hp_current: 14,
        },
      }],
    })
    const { result, deps } = renderActions({
      moveMode: true,
      addLog,
    })

    await act(async () => {
      await result.current.handleMoveTo(4, 5)
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('\u79fb\u52a8 5ft'),
      dice_result: expect.objectContaining({
        type: 'ready_action',
        action_type: 'move',
        actor_id: 'ally-1',
        actor_state: expect.objectContaining({
          target_id: 'ally-1',
          hp_current: 14,
        }),
        hazard_result: expect.objectContaining({
          cell: '5_6',
          ready_action: true,
        }),
      }),
    }))
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('Sparking Conduit'),
      dice_result: expect.objectContaining({
        type: 'hazard',
        trigger: 'movement_hazard',
        cell: '5_6',
        total_damage: 6,
        target_state: expect.objectContaining({
          target_id: 'ally-1',
          hp_after: 14,
        }),
      }),
    }))
  })

  it('logs opportunity attacks nested in ready movement results returned by movement', async () => {
    const addLog = vi.fn()
    const combatSnapshot = {
      entity_positions: {
        'guest-char': { x: 4, y: 5 },
        'ally-1': { x: 5, y: 6 },
      },
      entities: {
        'ally-1': { id: 'ally-1', hp_current: 12 },
      },
    }
    gameApi.move.mockResolvedValue({
      combat: combatSnapshot,
      turn_state: { movement_used: 1, movement_max: 6 },
      ready_action_results: [{
        type: 'ready_action',
        action_type: 'move',
        applied: true,
        trigger: 'target_moves',
        actor_id: 'ally-1',
        actor_name: 'Mara Quickstep',
        target_id: 'guest-char',
        target_name: 'Hero',
        from: { x: 5, y: 5 },
        to: { x: 5, y: 6 },
        steps: 1,
        distance_ft: 5,
        opportunity_attacks: [{
          attacker: 'Ready Move Opportunity Guard',
          target: 'Mara Quickstep',
          attack_result: {
            attack_total: 18,
            target_ac: 14,
            hit: true,
            is_crit: false,
          },
          damage: 6,
          damage_roll: { total: 6, rolls: [6] },
        }],
        actor_state: {
          target_id: 'ally-1',
          target_name: 'Mara Quickstep',
          hp_current: 12,
        },
      }],
    })
    const { result, deps } = renderActions({
      moveMode: true,
      addLog,
    })

    await act(async () => {
      await result.current.handleMoveTo(4, 5)
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('\u79fb\u52a8 5ft'),
      dice_result: expect.objectContaining({
        type: 'ready_action',
        action_type: 'move',
        actor_id: 'ally-1',
        actor_state: expect.objectContaining({
          target_id: 'ally-1',
          hp_current: 12,
        }),
        opportunity_attacks: [expect.objectContaining({
          attacker: 'Ready Move Opportunity Guard',
          damage: 6,
        })],
      }),
    }))
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('\u501f\u673a\u653b\u51fb'),
      dice_result: expect.objectContaining({
        opportunity: true,
        ready_action: true,
        damage: 6,
        attacker: 'Ready Move Opportunity Guard',
        target: 'Mara Quickstep',
        attack: expect.objectContaining({
          attack_total: 18,
          target_ac: 14,
          hit: true,
        }),
      }),
    }))
  })

  it('blocks over-budget difficult terrain movement before calling the API', async () => {
    const { result, deps } = renderActions({
      moveMode: true,
      selectedTarget: null,
      playerPos: { x: 5, y: 5 },
      entities: {
        'guest-char': { id: 'guest-char', conditions: [], condition_durations: {} },
      },
      entityPositions: {
        'guest-char': { x: 5, y: 5 },
      },
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', id: 'guest-char' }],
        entity_positions: {
          'guest-char': { x: 5, y: 5 },
        },
        grid_data: {
          '6_5': { terrain: 'difficult', label: 'Mud slick' },
        },
        turn_states: {
          'guest-char': { movement_used: 5, movement_max: 6 },
        },
      },
    })

    await act(async () => {
      await result.current.handleMoveTo(6, 5)
    })

    expect(gameApi.move).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('困难地形需要 2 格移动力，当前剩余 1 格')
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('surfaces opportunity attacks returned by movement as combat logs', async () => {
    const addLog = vi.fn()
    const combatSnapshot = {
      entity_positions: {
        'guest-char': { x: 8, y: 5 },
        'goblin-1': { x: 6, y: 5 },
      },
      turn_states: {
        'goblin-1': { reaction_used: true },
      },
    }
    gameApi.move.mockResolvedValue({
      combat: combatSnapshot,
      turn_state: { movement_used: 3, movement_max: 6 },
      opportunity_attacks: [{
        attacker: 'Goblin Guard',
        target: 'Hero',
        attack_result: {
          attack_total: 17,
          target_ac: 12,
          hit: true,
          is_crit: false,
        },
        damage: 5,
        damage_roll: { total: 5, rolls: [5] },
        movement_stop: {
          type: 'sentinel',
          applied: true,
          attacker: 'Goblin Guard',
          target: 'Hero',
          from: { x: 5, y: 5 },
          attempted_to: { x: 8, y: 5 },
          to: { x: 5, y: 5 },
          movement_used_to_max: true,
        },
      }],
    })
    const { result, deps } = renderActions({
      moveMode: true,
      addLog,
    })

    await act(async () => {
      await result.current.handleMoveTo(8, 5)
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(deps.setTurnState).toHaveBeenCalledWith({ movement_used: 3, movement_max: 6 })
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('\u501f\u673a\u653b\u51fb'),
      dice_result: expect.objectContaining({
        opportunity: true,
        damage: 5,
        attacker: 'Goblin Guard',
        target: 'Hero',
        attack: expect.objectContaining({
          attack_total: 17,
          target_ac: 12,
          hit: true,
        }),
        movement_stop: expect.objectContaining({
          type: 'sentinel',
          applied: true,
          to: { x: 5, y: 5 },
        }),
      }),
    }))
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: expect.stringContaining('\u79fb\u52a8\u88ab Goblin Guard \u622a\u505c'),
    }))
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('declares ready movement after the ready move mode picks a destination cell', async () => {
    const addLog = vi.fn()
    const combatSnapshot = {
      entity_positions: {
        'guest-char': { x: 5, y: 5 },
        'enemy-1': { x: 10, y: 5 },
      },
      turn_states: {
        'guest-char': { action_used: true, ready_action: { action_type: 'move' } },
      },
    }
    gameApi.readyAction.mockResolvedValue({
      narration: 'Hero ready movement declared.',
      ready_action: {
        type: 'ready_action',
        action_type: 'move',
        trigger: 'target_moves',
        target_id: 'enemy-1',
        target_name: 'Goblin',
        move_to: { x: 5, y: 6 },
      },
      turn_state: { action_used: true, ready_action: { action_type: 'move' } },
      combat: combatSnapshot,
    })
    const { result, deps } = renderActions({
      moveMode: true,
      addLog,
      entityPositions: {
        'guest-char': { x: 5, y: 5 },
        'enemy-1': { x: 10, y: 5 },
      },
      playerPos: { x: 5, y: 5 },
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', id: 'guest-char' }],
        entity_positions: {
          'guest-char': { x: 5, y: 5 },
          'enemy-1': { x: 10, y: 5 },
        },
        turn_states: {
          'guest-char': {
            action_used: false,
            reaction_used: false,
            movement_used: 0,
            movement_max: 6,
          },
        },
      },
    })

    await act(async () => {
      await result.current.onSkillClick({
        k: 'atk',
        available: true,
        mode: 'ready_move',
        ready_action_type: 'move',
        trigger: 'target_moves',
        conditionText: '当 Goblin 冲过桥头时移动',
      })
    })
    expect(deps.setMoveMode).toHaveBeenCalledWith(true)

    await act(async () => {
      await result.current.handleMoveTo(5, 6)
    })

    expect(gameApi.move).not.toHaveBeenCalled()
    expect(gameApi.readyAction).toHaveBeenCalledWith('sess-1', 'guest-char', 'enemy-1', {
      actionType: 'move',
      trigger: 'target_moves',
      moveToX: 5,
      moveToY: 6,
      conditionText: '当 Goblin 冲过桥头时移动',
      expectedTurnToken: '1:0:guest-char',
    })
    expect(deps.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: true, ready_action: { action_type: 'move' } })
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'player',
      content: 'Hero ready movement declared.',
      dice_result: expect.objectContaining({
        type: 'ready_action_declared',
        ready_action: expect.objectContaining({ action_type: 'move' }),
      }),
    }))
    expect(deps.setMoveMode).toHaveBeenLastCalledWith(false)
  })

  it('blocks movement submit while actor speed is zero', async () => {
    const { result, deps } = renderActions({
      moveMode: true,
      entities: {
        'guest-char': {
          id: 'guest-char',
          conditions: ['grappled'],
          condition_durations: { grappled: 1 },
        },
      },
    })

    await act(async () => {
      await result.current.handleMoveTo(4, 5)
    })

    expect(gameApi.move).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('被擒抱 (1轮) · 移动速度为 0')
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('blocks movement submit while prone if remaining movement cannot pay stand-up cost', async () => {
    const { result, deps } = renderActions({
      moveMode: true,
      entities: {
        'guest-char': {
          id: 'guest-char',
          conditions: ['prone'],
        },
      },
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', id: 'guest-char' }],
        turn_states: {
          'guest-char': {
            movement_used: 4,
            movement_max: 6,
            base_movement_max: 6,
          },
        },
      },
    })

    await act(async () => {
      await result.current.handleMoveTo(4, 5)
    })

    expect(gameApi.move).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('倒地 · 起身需要 3 格移动力，当前剩余 2 格')
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('blocks movement submit while frightened if the destination approaches the source', async () => {
    const { result, deps } = renderActions({
      moveMode: true,
      playerPos: { x: 5, y: 5 },
      entityPositions: {
        'guest-char': { x: 5, y: 5 },
        'enemy-1': { x: 8, y: 5 },
      },
      entities: {
        'guest-char': {
          id: 'guest-char',
          conditions: ['frightened'],
          condition_durations: { frightened: { duration: 2, source_id: 'enemy-1' } },
        },
      },
    })

    await act(async () => {
      await result.current.handleMoveTo(6, 5)
    })

    expect(gameApi.move).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('恐慌 · 不能主动靠近恐惧来源')
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('blocks grapple drag movement submit when doubled cost exceeds remaining movement', async () => {
    const { result, deps } = renderActions({
      moveMode: true,
      playerPos: { x: 5, y: 5 },
      entityPositions: {
        'guest-char': { x: 5, y: 5 },
        'enemy-1': { x: 6, y: 5 },
      },
      entities: {
        'guest-char': {
          id: 'guest-char',
          name: 'Hero',
        },
        'enemy-1': {
          id: 'enemy-1',
          name: 'Dragged Duelist',
          conditions: ['grappled'],
          condition_durations: { grappled: { source_id: 'guest-char' } },
        },
      },
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', id: 'guest-char' }],
        entity_positions: {
          'guest-char': { x: 5, y: 5 },
          'enemy-1': { x: 6, y: 5 },
        },
        turn_states: {
          'guest-char': {
            movement_used: 0,
            movement_max: 6,
          },
        },
      },
    })

    await act(async () => {
      await result.current.handleMoveTo(9, 5)
    })

    expect(gameApi.move).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('拖拽 Dragged Duelist 需要 8 格移动力，当前剩余 6 格')
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('allows movement submit while prone when enough movement remains for standing up', async () => {
    gameApi.move.mockResolvedValue({
      combat: {
        entity_positions: {
          'guest-char': { x: 4, y: 5 },
        },
      },
      turn_state: { movement_used: 4, movement_max: 6, base_movement_max: 6 },
      stood_up: true,
      stand_up_cost: 3,
      conditions: [],
    })
    const { result, deps } = renderActions({
      moveMode: true,
      entities: {
        'guest-char': {
          id: 'guest-char',
          conditions: ['prone'],
          condition_durations: { prone: 1 },
        },
      },
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', id: 'guest-char' }],
        turn_states: {
          'guest-char': {
            movement_used: 0,
            movement_max: 6,
            base_movement_max: 6,
          },
        },
      },
    })

    await act(async () => {
      await result.current.handleMoveTo(4, 5)
    })

    expect(gameApi.move).toHaveBeenCalledWith('sess-1', 'guest-char', 4, 5, '1:0:guest-char')
    expect(deps.setTurnState).toHaveBeenCalledWith({ movement_used: 4, movement_max: 6, base_movement_max: 6 })
    expect(deps.setError).not.toHaveBeenCalled()
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('blocks movement skill fallback clicks while actor speed is zero', async () => {
    const handleDash = vi.fn()
    const { result, deps } = renderActions({
      handleDash,
      entities: {
        'guest-char': {
          id: 'guest-char',
          conditions: ['restrained'],
          condition_durations: { restrained: 2 },
        },
      },
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', id: 'guest-char' }],
        turn_states: {
          'guest-char': {
            action_used: false,
            bonus_action_used: false,
            movement_used: 0,
            movement_max: 6,
          },
        },
      },
    })

    await act(async () => {
      await result.current.onSkillClick({
        k: 'dash',
        label: '冲刺',
        cost: '动作',
        kind: 'move',
        available: true,
      })
    })

    expect(handleDash).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('束缚 (2轮) · 移动速度为 0')
  })

  it('keeps websocket reaction prompts so non-reactors can see a non-blocking notice', () => {
    const { result, deps } = renderActions()
    const prompt = {
      trigger: 'spell_cast',
      reactor_character_id: 'guest-char',
      options: [{ type: 'counterspell' }],
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        player_can_react: true,
        reaction_prompt: prompt,
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith(prompt)

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        player_can_react: true,
        reaction_prompt: {
          ...prompt,
          reactor_character_id: 'host-char',
        },
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenLastCalledWith({
      ...prompt,
      reactor_character_id: 'host-char',
    })
    expect(deps.setReactionPrompt).toHaveBeenCalledTimes(2)
  })

  it('normalizes websocket spell reaction prompts using the caster target', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        player_can_react: true,
        reaction_prompt: {
          trigger: 'spell_cast',
          caster_id: 'enemy-mage',
          reactor_character_id: 'guest-char',
          options: [{ type: 'counterspell' }],
        },
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith({
      trigger: 'spell_cast',
      caster_id: 'enemy-mage',
      reactor_character_id: 'guest-char',
      target_id: 'enemy-mage',
      options: [{ type: 'counterspell', target_id: 'enemy-mage' }],
    })
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('clears stale reaction prompts when a combat update has no active prompt', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        player_can_react: false,
        reaction_prompt: null,
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('cleans local combat state and skips reload when websocket says combat ended', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        combat: null,
        combat_over: true,
        outcome: 'victory',
      })
    })

    expect(deps.setCombatOver).toHaveBeenCalledWith('victory')
    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.setTurnState).toHaveBeenCalledWith(null)
    expect(deps.setCombat).toHaveBeenCalledWith(null)
    expect(deps.onCombatEnded).toHaveBeenCalledWith('victory')
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('reloads combat for turn, movement, and dm response realtime events', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({ type: 'turn_changed' })
      result.current.onWsEvent({ type: 'entity_moved' })
      result.current.onWsEvent({ type: 'dm_responded' })
    })

    expect(deps.onLoadCombat).toHaveBeenCalledTimes(3)
  })

  it('logs delayed turn broadcasts from turn_changed events', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'turn_changed',
        turn_order_delayed: true,
        delayed_turn: {
          actor_id: 'host-char',
          actor_name: 'Delay Host',
          after_entity_id: 'enemy-1',
          after_entity_name: 'Goblin Guard',
          placement: 'after_target',
          moved: true,
        },
        combat: {
          current_turn_index: 0,
          turn_order: [{ character_id: 'enemy-1', is_player: false }],
          turn_states: { 'enemy-1': { action_used: false } },
        },
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'system',
      content: 'Delay Host \u5ef6\u8fdf\u884c\u52a8\uff0c\u5c06\u56de\u5408\u79fb\u5230 Goblin Guard \u4e4b\u540e\u3002',
      log_type: 'combat',
      dice_result: expect.objectContaining({
        type: 'delay_turn',
        actor_id: 'host-char',
        after_entity_id: 'enemy-1',
        moved: true,
      }),
    })
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('logs delayed turn broadcasts and pauses reload when a control prompt is present', () => {
    const prompt = {
      trigger: 'lair_action',
      source_id: 'goblin-1',
      actions: [{ id: 'seismic-pulse', name: 'Seismic Pulse' }],
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'turn_changed',
        turn_order_delayed: true,
        delayed_turn: {
          actor_id: 'host-char',
          actor_name: 'Delay Host',
          moved: true,
        },
        lair_action_prompt: prompt,
      })
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: 'Delay Host \u5ef6\u8fdf\u884c\u52a8\uff0c\u5c06\u56de\u5408\u79fb\u5230\u672c\u8f6e\u672b\u5c3e\u3002',
    }))
    expect(deps.setLairActionPrompt).toHaveBeenCalledWith(prompt)
    expect(deps.setLegendaryActionPrompt).toHaveBeenCalledWith(null)
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('sets legendary prompts from typed turn_changed payloads', () => {
    const prompt = {
      trigger: 'legendary_action',
      actor_id: 'dragon-1',
      actor_name: 'Dragon',
      actions: [{ id: 'tail', name: 'Tail Attack' }],
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'turn_changed',
        round_number: 1,
        next_turn_index: 1,
        legendary_action_prompt: prompt,
      })
    })

    expect(deps.setLairActionPrompt).toHaveBeenCalledWith(null)
    expect(deps.setLegendaryActionPrompt).toHaveBeenCalledWith(prompt)
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('merges room_state_updated and online member snapshots without a room refetch', () => {
    const { result, deps } = renderActions()
    const prevRoom = {
      is_multiplayer: true,
      current_speaker_user_id: 'host',
      members: [{ user_id: 'host', character_id: 'host-char', is_online: true }],
    }
    const updatedRoom = {
      is_multiplayer: true,
      current_speaker_user_id: 'guest',
      members: [{ user_id: 'guest', character_id: 'guest-char', is_online: true }],
    }
    const onlineMembers = [
      { user_id: 'host', character_id: 'host-char', is_online: true },
      { user_id: 'guest', character_id: 'guest-char', is_online: true },
    ]

    act(() => {
      result.current.onWsEvent({ type: 'room_state_updated', room: updatedRoom })
    })
    expect(deps.setRoom).toHaveBeenCalledTimes(1)
    expect(deps.setRoom.mock.calls[0][0](prevRoom)).toMatchObject({
      current_speaker_user_id: 'guest',
      _currentSpeaker: 'guest',
      members: updatedRoom.members,
    })

    act(() => {
      result.current.onWsEvent({ type: 'member_online', members: onlineMembers })
    })
    expect(deps.setRoom).toHaveBeenCalledTimes(2)
    expect(deps.setRoom.mock.calls[1][0](prevRoom).members).toEqual(onlineMembers)
    expect(roomsGetMock).not.toHaveBeenCalled()
  })

  it('waits for room_state_updated when online events do not include members', async () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({ type: 'member_offline', user_id: 'guest' })
    })

    expect(roomsGetMock).not.toHaveBeenCalled()
    expect(deps.setRoom).not.toHaveBeenCalled()
  })

  it('submits Help on an allied target, refreshes combat, and exits help mode', async () => {
    gameApi.combatAction.mockResolvedValue({
      action: 'help',
      turn_state: { action_used: true },
    })
    gameApi.getCombat.mockResolvedValue({
      turn_states: {
        'ally-1': { being_helped: true },
      },
    })
    const { result, deps } = renderActions({
      helpMode: true,
      entities: {
        'ally-1': { id: 'ally-1', is_enemy: false, name: 'Ally' },
      },
    })

    let ok
    await act(async () => {
      ok = await result.current.handleHelpTarget('ally-1')
    })

    expect(ok).toBe(true)
    expect(gameApi.combatAction).toHaveBeenCalledWith('sess-1', '协助', 'ally-1', false, false, '1:0:guest-char')
    expect(gameApi.getCombat).toHaveBeenCalledWith('sess-1')
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: true })
    expect(deps.setCombat).toHaveBeenCalledWith({
      turn_states: {
        'ally-1': { being_helped: true },
      },
    })
    expect(deps.setHelpMode).toHaveBeenCalledWith(false)
    expect(deps.setError).not.toHaveBeenCalled()
  })

  it('rejects enemy and self Help targets without sending an action', async () => {
    const { result, deps } = renderActions({
      helpMode: true,
      entities: {
        'enemy-1': { id: 'enemy-1', is_enemy: true, name: 'Enemy' },
      },
    })

    await act(async () => {
      expect(await result.current.handleHelpTarget('enemy-1')).toBe(false)
      expect(await result.current.handleHelpTarget('guest-char')).toBe(false)
    })

    expect(gameApi.combatAction).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('请选择一名队友作为协助目标')
  })
})
