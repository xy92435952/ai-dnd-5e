import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  endConcentrationMock,
  useLegendaryActionMock,
  skipLegendaryActionMock,
  useLairActionMock,
  skipLairActionMock,
  getCombatMock,
  triggerAiTurnMock,
} = vi.hoisted(() => ({
  endConcentrationMock: vi.fn(),
  useLegendaryActionMock: vi.fn(),
  skipLegendaryActionMock: vi.fn(),
  useLairActionMock: vi.fn(),
  skipLairActionMock: vi.fn(),
  getCombatMock: vi.fn(),
  triggerAiTurnMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    endConcentration: endConcentrationMock,
    useLegendaryAction: useLegendaryActionMock,
    skipLegendaryAction: skipLegendaryActionMock,
    useLairAction: useLairActionMock,
    skipLairAction: skipLairActionMock,
    getCombat: getCombatMock,
  },
}))

vi.mock('../useCombatAiTurns', () => ({
  useCombatAiTurns: () => ({ triggerAiTurn: triggerAiTurnMock }),
}))

vi.mock('../useCombatLoader', () => ({
  useCombatLoader: () => ({ loadCombat: vi.fn() }),
}))

vi.mock('../useCombatTurnControls', () => ({
  useCombatTurnControls: () => ({ handleEndTurn: vi.fn() }),
}))

vi.mock('../useCombatAttackFlow', () => ({
  useCombatAttackFlow: () => vi.fn(),
}))

vi.mock('../useCombatSpellFlow', () => ({
  useCombatSpellFlow: () => vi.fn(),
}))

vi.mock('../useCombatDeathSave', () => ({
  useCombatDeathSave: () => vi.fn(),
}))

vi.mock('../useCombatPlayerActions', () => ({
  useCombatPlayerActions: () => ({
    handleClassFeature: vi.fn(),
    handleHealingPotion: vi.fn(),
    handleDodge: vi.fn(),
    handleDash: vi.fn(),
    handleDisengage: vi.fn(),
  }),
}))

vi.mock('../useCombatSpecialActions', () => ({
  useCombatSpecialActions: () => ({
    handleSmite: vi.fn(),
    handleReaction: vi.fn(),
    handleCancelReaction: vi.fn(),
    handleManeuver: vi.fn(),
  }),
}))

import { useCombatFlowHandlers } from '../useCombatFlowHandlers'

describe('useCombatFlowHandlers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function renderHandlers(overrides = {}) {
    const page = {
      combat: {
        current_turn_index: 1,
        turn_order: [{ character_id: 'hero-1', is_player: true }],
        entities: {
          'hero-1': { id: 'hero-1', name: 'Smoke Sentinel', hp_current: 20 },
          'enemy-1': { id: 'enemy-1', name: 'Open Spark Decoy', legendary_action_uses_remaining: 2 },
        },
      },
      setCombat: vi.fn(),
      isProcessing: false,
      setIsProcessing: vi.fn(),
      setCombatOver: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      setPlayerKnownSpells: vi.fn(),
      setPlayerCantrips: vi.fn(),
      playerId: 'hero-1',
      setPlayerId: vi.fn(),
      setTurnState: vi.fn(),
      smitePrompt: null,
      setSmitePrompt: vi.fn(),
      setPlayerClass: vi.fn(),
      setPlayerLevel: vi.fn(),
      setClassResources: vi.fn(),
      setPlayerSubclass: vi.fn(),
      setPlayerSubclassEffects: vi.fn(),
      playerSubclassEffects: {},
      setReactionPrompt: vi.fn(),
      setLegendaryActionPrompt: vi.fn(),
      setLairActionPrompt: vi.fn(),
      initiativeShown: false,
      setInitiativeShown: vi.fn(),
      session: {},
      setSession: vi.fn(),
      aiTimer: { current: null },
      processingRef: { current: false },
      setError: vi.fn(),
      ...overrides.page,
    }
    const targeting = {
      selectedTarget: 'enemy-1',
      setSelectedTarget: vi.fn(),
      aoeLockedCenter: null,
      setMoveMode: vi.fn(),
      isRanged: false,
      selectedWeaponName: null,
      setHelpMode: vi.fn(),
      ...overrides.targeting,
    }
    const log = {
      setLogs: vi.fn(),
      addLog: vi.fn(),
      ...overrides.log,
    }
    return {
      page,
      targeting,
      log,
      ...renderHook(() => useCombatFlowHandlers({
        sessionId: 'sess-1',
        showDice: vi.fn(),
        page,
        targeting,
        log,
        canDriveAiTurns: false,
      })),
    }
  }

  it('ends active concentration through the combat endpoint and logs the update', async () => {
    endConcentrationMock.mockResolvedValue({
      action: 'concentration_end',
      actor_id: 'hero-1',
      actor_name: 'Smoke Sentinel',
      narration: 'Smoke Sentinel ends concentration on Web.',
      target_state: {
        target_id: 'hero-1',
        target_name: 'Smoke Sentinel',
        concentration: null,
      },
    })
    const { result, page, log } = renderHandlers()

    await act(async () => {
      await result.current.handleEndConcentration()
    })

    expect(endConcentrationMock).toHaveBeenCalledWith('sess-1', 'hero-1')
    expect(log.addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'player',
      content: 'Smoke Sentinel ends concentration on Web.',
      log_type: 'combat',
    }))
    expect(page.setCombat).toHaveBeenCalledWith(expect.any(Function))
  })

  it('uses the damaged target name, not the legendary actor, for attack hp state rows', async () => {
    useLegendaryActionMock.mockResolvedValue({
      action: 'legendary_action',
      resolution: 'attack',
      actor_id: 'enemy-1',
      actor_name: 'Open Spark Decoy',
      target_id: 'hero-1',
      target_name: 'Smoke Sentinel',
      hp_before: 20,
      narration: 'Open Spark Decoy uses Legendary Action: Tail Strike.',
      dice_result: {
        type: 'legendary_action',
        attack: { d20: 18, attack_bonus: 99, attack_total: 117, target_ac: 13, hit: true },
        damage_roll: { notation: '1d8+3', total: 8 },
        damage: 8,
        total_damage: 8,
      },
      target_state: {
        target_id: 'hero-1',
        target_name: 'Smoke Sentinel',
        hp_current: 12,
      },
      actor_state: {
        target_id: 'enemy-1',
        target_name: 'Open Spark Decoy',
        legendary_action_uses: 3,
        legendary_action_uses_remaining: 1,
      },
    })
    getCombatMock.mockResolvedValue({ current_turn_index: 1, turn_order: [{ character_id: 'hero-2', is_player: true }] })
    const { result, log } = renderHandlers()

    await act(async () => {
      await result.current.handleLegendaryAction('enemy-1', 'tail', 'hero-1')
    })

    expect(log.addLog).toHaveBeenCalledWith(expect.objectContaining({
      state_changes: [
        'Smoke Sentinel HP 20 -> 12',
      ],
    }))
    expect(log.addLog.mock.calls[0][0].state_changes).not.toContain('Open Spark Decoy HP 20 -> 12')
  })

  it('pauses after a legendary action when an incoming-attack reaction is available', async () => {
    const reactionPrompt = {
      can_react: true,
      reactor_character_id: 'hero-1',
      attacker_id: 'enemy-1',
      available_reactions: [{ type: 'shield', name: 'Shield', damage_prevented: 8 }],
    }
    const combatSnapshot = {
      current_turn_index: 1,
      turn_order: [{ character_id: 'enemy-2', is_player: false }],
      turn_states: {
        'hero-1': {
          pending_attack_reaction: {
            trigger: 'incoming_attack',
            attacker_id: 'enemy-1',
            available_reactions: [{ type: 'shield', name: 'Shield', damage_prevented: 8 }],
          },
        },
      },
    }
    useLegendaryActionMock.mockResolvedValue({
      action: 'legendary_action',
      resolution: 'attack',
      actor_id: 'enemy-1',
      actor_name: 'Open Spark Decoy',
      target_id: 'hero-1',
      target_name: 'Smoke Sentinel',
      hp_before: 20,
      narration: 'Open Spark Decoy uses Legendary Action: Tail Strike.',
      player_can_react: true,
      reaction_prompt: reactionPrompt,
      combat: combatSnapshot,
      dice_result: {
        type: 'legendary_action',
        attack: { attack_total: 18, target_ac: 16, hit: true },
        damage: 8,
        total_damage: 8,
      },
      target_state: {
        target_id: 'hero-1',
        target_name: 'Smoke Sentinel',
        hp_current: 12,
      },
    })
    const { result, page } = renderHandlers()

    await act(async () => {
      await result.current.handleLegendaryAction('enemy-1', 'tail', 'hero-1')
    })

    expect(page.setReactionPrompt).toHaveBeenCalledWith({
      trigger: 'incoming_attack',
      attacker_id: 'enemy-1',
      available_reactions: [{ type: 'shield', name: 'Shield', damage_prevented: 8 }],
      reactor_character_id: 'hero-1',
    })
    expect(page.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(getCombatMock).not.toHaveBeenCalled()
    expect(triggerAiTurnMock).not.toHaveBeenCalled()
  })

  it('restores a legendary-action reaction prompt from the returned combat snapshot', async () => {
    const pendingReaction = {
      trigger: 'incoming_attack',
      attacker_id: 'enemy-1',
      attacker_name: 'Open Spark Decoy',
      available_reactions: [{ type: 'cutting_words_damage', die: 'd8' }],
    }
    const combatSnapshot = {
      current_turn_index: 1,
      turn_order: [
        { character_id: 'enemy-1', is_player: false },
        { character_id: 'hero-1', is_player: true },
      ],
      turn_states: {
        'enemy-1': { action_used: true },
        'hero-1': {
          reaction_used: false,
          pending_attack_reaction: pendingReaction,
        },
      },
    }
    useLegendaryActionMock.mockResolvedValue({
      action: 'legendary_action',
      resolution: 'attack',
      actor_id: 'enemy-1',
      actor_name: 'Open Spark Decoy',
      target_id: 'hero-1',
      target_name: 'Smoke Sentinel',
      hp_before: 20,
      narration: 'Open Spark Decoy uses Legendary Action: Tail Strike.',
      player_can_react: false,
      reaction_prompt: null,
      combat: combatSnapshot,
      dice_result: {
        type: 'legendary_action',
        attack: { attack_total: 18, target_ac: 16, hit: true },
        damage: 8,
        total_damage: 8,
      },
      target_state: {
        target_id: 'hero-1',
        target_name: 'Smoke Sentinel',
        hp_current: 12,
      },
    })
    const { result, page } = renderHandlers()

    await act(async () => {
      await result.current.handleLegendaryAction('enemy-1', 'tail', 'hero-1')
    })

    expect(page.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(page.setTurnState).toHaveBeenCalledWith({
      reaction_used: false,
      pending_attack_reaction: pendingReaction,
    })
    expect(page.setReactionPrompt).toHaveBeenCalledWith({
      ...pendingReaction,
      reactor_character_id: 'hero-1',
    })
    expect(getCombatMock).not.toHaveBeenCalled()
    expect(triggerAiTurnMock).not.toHaveBeenCalled()
  })

  it('persists a skipped legendary-action window before resuming the turn flow', async () => {
    const freshCombat = {
      current_turn_index: 0,
      turn_order: [{ character_id: 'hero-2', is_player: true }],
      turn_states: { 'hero-2': { action_used: false } },
    }
    skipLegendaryActionMock.mockResolvedValue({
      action: 'legendary_action_skip',
      combat: freshCombat,
    })
    const { result, page } = renderHandlers()

    await act(async () => {
      await result.current.handleSkipLegendaryAction()
    })

    expect(page.setLegendaryActionPrompt).toHaveBeenCalledWith(null)
    expect(skipLegendaryActionMock).toHaveBeenCalledWith('sess-1')
    expect(page.setCombat).toHaveBeenCalledWith(freshCombat)
    expect(page.setTurnState).toHaveBeenCalledWith({ action_used: false })
  })

  it('keeps a legendary-action window visible when skip confirmation fails', async () => {
    skipLegendaryActionMock.mockRejectedValue(new Error('skip failed'))
    const { result, page } = renderHandlers()

    await act(async () => {
      await result.current.handleSkipLegendaryAction()
    })

    expect(skipLegendaryActionMock).toHaveBeenCalledWith('sess-1')
    expect(page.setLegendaryActionPrompt).not.toHaveBeenCalledWith(null)
    expect(page.setCombat).not.toHaveBeenCalled()
    expect(triggerAiTurnMock).not.toHaveBeenCalled()
    expect(page.setError).toHaveBeenCalledWith('skip failed')
  })

  it('uses lair actions, logs state changes, and resumes the turn flow', async () => {
    useLairActionMock.mockResolvedValue({
      action: 'lair_action',
      resolution: 'save',
      source_id: 'lair-1',
      source_name: 'Cracked Shrine',
      target_count: 2,
      narration: 'Cracked Shrine uses Lair Action: Seismic Pulse.',
      dice_result: {
        type: 'lair_action',
        target_results: [
          { target_id: 'hero-1', target_name: 'Smoke Sentinel', hp_before: 20, hp_current: 12, damage: 8 },
          { target_id: 'ally-1', target_name: 'Mara Quickstep', hp_before: 20, hp_current: 16, damage: 4 },
        ],
      },
      target_results: [
        { target_id: 'hero-1', target_name: 'Smoke Sentinel', hp_before: 20, hp_current: 12, damage: 8 },
        { target_id: 'ally-1', target_name: 'Mara Quickstep', hp_before: 20, hp_current: 16, damage: 4 },
      ],
    })
    const freshCombat = {
      current_turn_index: 0,
      turn_order: [{ character_id: 'hero-2', is_player: true }],
      turn_states: { 'hero-2': { action_used: false } },
    }
    getCombatMock.mockResolvedValue(freshCombat)
    const { result, page, log } = renderHandlers()

    await act(async () => {
      await result.current.handleLairAction('lair-1', 'seismic-pulse', ['hero-1', 'ally-1'])
    })

    expect(page.setLairActionPrompt).toHaveBeenCalledWith(null)
    expect(useLairActionMock).toHaveBeenCalledWith('sess-1', 'lair-1', 'seismic-pulse', ['hero-1', 'ally-1'])
    expect(log.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: 'Cracked Shrine uses Lair Action: Seismic Pulse.',
      dice_result: expect.objectContaining({ type: 'lair_action' }),
    }))
    expect(page.setCombat).toHaveBeenCalledWith(freshCombat)
    expect(page.setTurnState).toHaveBeenCalledWith({ action_used: false })
  })

  it('restores a lair-action reaction prompt from the returned combat snapshot', async () => {
    const pendingReaction = {
      trigger: 'incoming_attack',
      attacker_id: 'lair-1',
      attacker_name: 'Cracked Shrine',
      available_reactions: [{ type: 'shield', name: 'Shield' }],
    }
    const combatSnapshot = {
      current_turn_index: 1,
      turn_order: [
        { character_id: 'lair-1', is_player: false },
        { character_id: 'hero-1', is_player: true },
      ],
      turn_states: {
        'hero-1': {
          reaction_used: false,
          pending_attack_reaction: pendingReaction,
        },
      },
    }
    useLairActionMock.mockResolvedValue({
      action: 'lair_action',
      resolution: 'attack',
      source_id: 'lair-1',
      source_name: 'Cracked Shrine',
      target_id: 'hero-1',
      target_name: 'Smoke Sentinel',
      hp_before: 20,
      narration: 'Cracked Shrine lashes out.',
      player_can_react: false,
      reaction_prompt: null,
      combat: combatSnapshot,
      dice_result: {
        type: 'lair_action',
        attack: { attack_total: 18, target_ac: 16, hit: true },
        damage: 8,
        total_damage: 8,
      },
      target_state: {
        target_id: 'hero-1',
        target_name: 'Smoke Sentinel',
        hp_current: 12,
      },
    })
    const { result, page } = renderHandlers()

    await act(async () => {
      await result.current.handleLairAction('lair-1', 'lash', 'hero-1')
    })

    expect(page.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(page.setTurnState).toHaveBeenCalledWith({
      reaction_used: false,
      pending_attack_reaction: pendingReaction,
    })
    expect(page.setReactionPrompt).toHaveBeenCalledWith({
      ...pendingReaction,
      reactor_character_id: 'hero-1',
    })
    expect(getCombatMock).not.toHaveBeenCalled()
    expect(triggerAiTurnMock).not.toHaveBeenCalled()
  })

  it('persists a skipped lair-action window before resuming the turn flow', async () => {
    const freshCombat = {
      current_turn_index: 0,
      turn_order: [{ character_id: 'hero-2', is_player: true }],
      turn_states: { 'hero-2': { action_used: false } },
    }
    skipLairActionMock.mockResolvedValue({
      action: 'lair_action_skip',
      combat: freshCombat,
    })
    const { result, page } = renderHandlers()

    await act(async () => {
      await result.current.handleSkipLairAction()
    })

    expect(page.setLairActionPrompt).toHaveBeenCalledWith(null)
    expect(skipLairActionMock).toHaveBeenCalledWith('sess-1')
    expect(page.setCombat).toHaveBeenCalledWith(freshCombat)
    expect(page.setTurnState).toHaveBeenCalledWith({ action_used: false })
  })

  it('keeps a lair-action window visible when skip confirmation fails', async () => {
    skipLairActionMock.mockRejectedValue(new Error('skip failed'))
    const { result, page } = renderHandlers()

    await act(async () => {
      await result.current.handleSkipLairAction()
    })

    expect(skipLairActionMock).toHaveBeenCalledWith('sess-1')
    expect(page.setLairActionPrompt).not.toHaveBeenCalledWith(null)
    expect(page.setCombat).not.toHaveBeenCalled()
    expect(triggerAiTurnMock).not.toHaveBeenCalled()
    expect(page.setError).toHaveBeenCalledWith('skip failed')
  })
})
