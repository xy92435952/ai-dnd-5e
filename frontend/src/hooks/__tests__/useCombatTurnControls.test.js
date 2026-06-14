import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { delayTurnMock, endTurnMock, getCombatMock, rollDice3DMock } = vi.hoisted(() => ({
  delayTurnMock: vi.fn(),
  endTurnMock: vi.fn(),
  getCombatMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    delayTurn: delayTurnMock,
    endTurn: endTurnMock,
    getCombat: getCombatMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

import { useCombatTurnControls } from '../useCombatTurnControls'

describe('useCombatTurnControls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    rollDice3DMock.mockResolvedValue({ total: 4, rolls: [4] })
  })

  function renderControls(overrides = {}) {
    const processingRef = { current: false }
    const aiTimer = { current: null }
    const deps = {
      sessionId: 'sess-1',
      combat: { current_turn_index: 0, turn_order: [{ is_player: true, character_id: 'char-1' }] },
      isProcessing: false,
      isPlayerTurn: vi.fn(() => true),
      processingRef,
      aiTimer,
      setIsProcessing: vi.fn(),
      setMoveMode: vi.fn(),
      setHelpMode: vi.fn(),
      setError: vi.fn(),
      setCombat: vi.fn(),
      setTurnState: vi.fn(),
      setCombatOver: vi.fn(),
      addLog: vi.fn(),
      triggerAiTurn: vi.fn(),
      ...overrides,
    }
    return { deps, processingRef, aiTimer, ...renderHook(() => useCombatTurnControls(deps)) }
  }

  it('ends the turn, loads fresh combat, and schedules ai when the next turn is not a player', async () => {
    endTurnMock.mockResolvedValue({
      next_turn_index: 1,
      round_number: 2,
      expired_conditions: ['迟缓结束'],
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })

    const { result, deps, aiTimer } = renderControls()

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(endTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1')
    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'system',
      content: '迟缓结束',
      log_type: 'system',
    })
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
    expect(deps.setHelpMode).toHaveBeenCalledWith(false)
    expect(getCombatMock).toHaveBeenCalledWith('sess-1')
    expect(aiTimer.current).not.toBeNull()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(600)
    })
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('submits Bardic Inspiration for an end-of-turn condition save', async () => {
    endTurnMock.mockResolvedValue({
      next_turn_index: 1,
      round_number: 1,
      condition_end_saves: [{
        save: {
          bardic_inspiration: {
            spent: true,
            uses_remaining: 0,
          },
        },
      }],
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })
    const setClassResources = vi.fn()
    const setUseBardicEndSave = vi.fn()
    const showDice = vi.fn()

    const { result } = renderControls({
      classResources: { bardic_inspiration: { die: 'd8', uses_remaining: 1 } },
      useBardicEndSave: true,
      setUseBardicEndSave,
      setClassResources,
      showDice,
    })

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8)
    expect(showDice).toHaveBeenCalledWith({
      faces: 8,
      result: 4,
      label: 'Bardic Inspiration d8',
      count: 1,
    })
    expect(endTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1', {
      useBardicInspiration: true,
      bardicInspirationRoll: 4,
    })
    expect(setUseBardicEndSave).toHaveBeenCalledWith(false)
    const updater = setClassResources.mock.calls[0][0]
    expect(updater({ bardic_inspiration: { die: 'd8', uses_remaining: 1 } })).toEqual({
      bardic_inspiration: { die: 'd8', uses_remaining: 0 },
    })
  })

  it('sets player turn state when the fresh next turn is a player', async () => {
    endTurnMock.mockResolvedValue({ next_turn_index: 0, round_number: 1 })
    getCombatMock.mockResolvedValue({
      current_turn_index: 0,
      turn_order: [{ character_id: 'char-1', is_player: true }],
      turn_states: {
        'char-1': { action_used: false },
      },
    })

    const { result, deps } = renderControls()

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: false })
  })

  it('delays the current player turn to the round end and logs the placement', async () => {
    delayTurnMock.mockResolvedValue({
      next_turn_index: 0,
      round_number: 1,
      turn_order_delayed: true,
      delayed_turn: {
        actor_id: 'char-1',
        actor_name: 'Delay Hero',
        from_index: 0,
        to_index: 2,
        moved: true,
      },
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 0,
      turn_order: [
        { character_id: 'enemy-1', is_player: false },
        { character_id: 'ally-1', is_player: true },
        { character_id: 'char-1', is_player: true },
      ],
    })

    const { result, deps } = renderControls()

    await act(async () => {
      await result.current.handleDelayTurn()
    })

    expect(delayTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1', null)
    expect(endTurnMock).not.toHaveBeenCalled()
    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'system',
      content: 'Delay Hero 延迟行动，将回合移到本轮末尾。',
      log_type: 'combat',
      dice_result: expect.objectContaining({
        type: 'delay_turn',
        actor_id: 'char-1',
        moved: true,
      }),
    })
    expect(getCombatMock).toHaveBeenCalledWith('sess-1')
  })

  it('delays the current player turn after the selected later combatant', async () => {
    delayTurnMock.mockResolvedValue({
      next_turn_index: 0,
      round_number: 1,
      turn_order_delayed: true,
      delayed_turn: {
        actor_id: 'char-1',
        actor_name: 'Delay Hero',
        after_entity_id: 'enemy-1',
        after_entity_name: 'Goblin Guard',
        placement: 'after_target',
        from_index: 0,
        to_index: 1,
        moved: true,
      },
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 0,
      turn_order: [
        { character_id: 'enemy-1', is_player: false },
        { character_id: 'char-1', is_player: true },
      ],
    })

    const { result, deps } = renderControls()

    await act(async () => {
      await result.current.handleDelayTurn('enemy-1')
    })

    expect(delayTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1', 'enemy-1')
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: 'Delay Hero 延迟行动，将回合移到 Goblin Guard 之后。',
      dice_result: expect.objectContaining({
        type: 'delay_turn',
        after_entity_id: 'enemy-1',
      }),
    }))
  })

  it('does not delay after the current actor spent turn resources', async () => {
    const { result, deps } = renderControls({
      combat: {
        current_turn_index: 0,
        turn_order: [{ character_id: 'char-1', is_player: true }],
        turn_states: {
          'char-1': {
            action_used: true,
            bonus_action_used: false,
            movement_used: 0,
            attacks_made: 1,
          },
        },
      },
    })

    await act(async () => {
      await result.current.handleDelayTurn()
    })

    expect(delayTurnMock).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).not.toHaveBeenCalled()
  })

  it('lets the ai combat driver delay an AI-controlled turn', async () => {
    delayTurnMock.mockResolvedValue({
      next_turn_index: 0,
      round_number: 1,
      turn_order_delayed: true,
      delayed_turn: {
        actor_id: 'enemy-1',
        actor_name: 'Delay Enemy',
        from_index: 0,
        to_index: 1,
        moved: true,
      },
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 0,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })

    const { result, deps } = renderControls({
      canActThisTurn: false,
      canDriveAiTurns: true,
      isPlayerTurn: vi.fn(() => false),
      combat: {
        current_turn_index: 0,
        turn_order: [{ character_id: 'enemy-1', is_player: false }],
      },
    })

    await act(async () => {
      await result.current.handleDelayTurn()
    })

    expect(delayTurnMock).toHaveBeenCalledWith('sess-1', '1:0:enemy-1', null)
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: 'Delay Enemy 延迟行动，将回合移到本轮末尾。',
      dice_result: expect.objectContaining({
        type: 'delay_turn',
        actor_id: 'enemy-1',
      }),
    }))
  })

  it('does not let a non-driver delay an AI-controlled turn', async () => {
    const { result, deps } = renderControls({
      canActThisTurn: false,
      canDriveAiTurns: false,
      isPlayerTurn: vi.fn(() => false),
      combat: {
        current_turn_index: 0,
        turn_order: [{ character_id: 'enemy-1', is_player: false }],
      },
    })

    await act(async () => {
      await result.current.handleDelayTurn()
    })

    expect(delayTurnMock).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).not.toHaveBeenCalled()
  })

  it('stores lair action prompts from end turn without auto-driving the next ai turn', async () => {
    const setLairActionPrompt = vi.fn()
    const setLegendaryActionPrompt = vi.fn()
    const lairPrompt = {
      source_id: 'lair-1',
      source_name: 'Cracked Shrine',
      actions: [{ id: 'pulse', name: 'Seismic Pulse' }],
    }
    endTurnMock.mockResolvedValue({
      next_turn_index: 1,
      round_number: 2,
      lair_action_prompt: lairPrompt,
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })

    const { result, deps, aiTimer } = renderControls({ setLairActionPrompt, setLegendaryActionPrompt })

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(setLairActionPrompt).toHaveBeenCalledWith(null)
    expect(setLegendaryActionPrompt).toHaveBeenCalledWith(null)
    expect(setLairActionPrompt).toHaveBeenCalledWith(lairPrompt)
    expect(aiTimer.current).toBeNull()
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('stores legendary action prompts from end turn without auto-driving the next ai turn', async () => {
    const setLegendaryActionPrompt = vi.fn()
    const legendaryPrompt = {
      actor_id: 'dragon-1',
      actor_name: 'Dragon',
      actions: [{ id: 'tail', name: 'Tail Strike' }],
    }
    endTurnMock.mockResolvedValue({
      next_turn_index: 1,
      round_number: 1,
      legendary_action_prompt: legendaryPrompt,
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })

    const { result, deps, aiTimer } = renderControls({ setLegendaryActionPrompt })

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(setLegendaryActionPrompt).toHaveBeenCalledWith(legendaryPrompt)
    expect(aiTimer.current).toBeNull()
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('logs start-of-turn hazard damage returned by end turn', async () => {
    endTurnMock.mockResolvedValue({
      next_turn_index: 1,
      round_number: 1,
      turn_start_hazard_log: 'Goblin triggers sparking conduit, taking 3 lightning damage. HP 7->4',
      turn_start_hazard: {
        trigger: 'turn_start',
        target_id: 'enemy-1',
        final_damage: 3,
      },
    })
    getCombatMock.mockResolvedValue({
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })

    const { result, deps } = renderControls()

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'system',
      content: 'Goblin triggers sparking conduit, taking 3 lightning damage. HP 7->4',
      log_type: 'combat',
      dice_result: {
        damage: 3,
        hazard: {
          trigger: 'turn_start',
          target_id: 'enemy-1',
          final_damage: 3,
        },
      },
    })
  })

  it('does not end turn when a multiplayer observer is watching another player turn', async () => {
    const { result, deps } = renderControls({ canActThisTurn: false })

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(endTurnMock).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).not.toHaveBeenCalled()
  })

  it('does not end turn when the current combat entry is AI-controlled', async () => {
    const isPlayerTurn = vi.fn(() => false)
    const { result, deps } = renderControls({
      isPlayerTurn,
      combat: {
        current_turn_index: 0,
        turn_order: [{ character_id: 'enemy-1', is_player: false }],
      },
    })

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(isPlayerTurn).toHaveBeenCalled()
    expect(endTurnMock).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).not.toHaveBeenCalled()
  })

  it('does not auto-drive ai after ending turn on non-driver clients', async () => {
    endTurnMock.mockResolvedValue({ next_turn_index: 1, round_number: 2 })
    getCombatMock.mockResolvedValue({
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    })

    const { result, deps, aiTimer } = renderControls({ canDriveAiTurns: false })

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(endTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1')
    expect(aiTimer.current).toBeNull()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600)
    })
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('refreshes combat and stops quietly when ending turn with a stale token', async () => {
    const freshCombat = {
      current_turn_index: 1,
      turn_order: [
        { character_id: 'char-1', is_player: true },
        { character_id: 'enemy-1', is_player: false },
      ],
    }
    endTurnMock.mockRejectedValue(new Error('End turn token is stale; refresh combat state'))
    getCombatMock.mockResolvedValue(freshCombat)

    const { result, deps, processingRef } = renderControls()

    await act(async () => {
      await result.current.handleEndTurn()
    })

    expect(endTurnMock).toHaveBeenCalledWith('sess-1', '1:0:char-1')
    expect(getCombatMock).toHaveBeenCalledWith('sess-1')
    expect(deps.setCombat).toHaveBeenCalledWith(freshCombat)
    expect(deps.setError).toHaveBeenCalledWith('')
    expect(deps.setError).not.toHaveBeenCalledWith(expect.stringContaining('stale'))
    expect(processingRef.current).toBe(false)
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })
})
