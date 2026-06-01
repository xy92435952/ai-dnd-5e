import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { getCombatMock, aiTurnMock } = vi.hoisted(() => ({
  getCombatMock: vi.fn(),
  aiTurnMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    getCombat: getCombatMock,
    aiTurn: aiTurnMock,
  },
}))

import { useCombatAiTurns } from '../useCombatAiTurns'

describe('useCombatAiTurns', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  function renderAiTurns(overrides = {}) {
    const processingRef = { current: false }
    const deps = {
      sessionId: 'sess-1',
      playerId: 'char-1',
      processingRef,
      setIsProcessing: vi.fn(),
      setCombat: vi.fn(),
      setTurnState: vi.fn(),
      setReactionPrompt: vi.fn(),
      setCombatOver: vi.fn(),
      addLog: vi.fn(),
      showDice: vi.fn(),
      ...overrides,
    }
    return { deps, processingRef, ...renderHook(() => useCombatAiTurns(deps)) }
  }

  it('applies an ai result, waits, then stops when the next fresh combat is a player turn', async () => {
    getCombatMock
      .mockResolvedValueOnce({
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'enemy-1', is_player: false }],
      })
      .mockResolvedValueOnce({
        current_turn_index: 1,
        turn_order: [
          { character_id: 'enemy-1', is_player: false },
          { character_id: 'char-1', is_player: true },
        ],
        turn_states: {
          'char-1': { action_used: false, movement_used: 0 },
        },
      })
    aiTurnMock.mockResolvedValue({
      actor_id: 'enemy-1',
      actor_name: '哥布林',
      narration: '哥布林挥刀',
      attack_result: { d20: 12 },
      damage: 3,
      target_id: 'char-1',
      target_new_hp: 9,
      target_state: {
        target_id: 'char-1',
        new_hp: 0,
        death_saves: { successes: 0, failures: 1, stable: false },
        conditions: ['unconscious'],
        life_state: 'dying',
      },
      next_turn_index: 1,
      round_number: 1,
      entity_positions: { 'char-1': { x: 5, y: 5 } },
    })

    const { result, deps, processingRef } = renderAiTurns()

    await act(async () => {
      const promise = result.current.triggerAiTurn()
      await Promise.resolve()
      await Promise.resolve()
      await vi.runOnlyPendingTimersAsync()
      await promise
    })

    expect(aiTurnMock).toHaveBeenCalledWith('sess-1', '1:0:enemy-1')
    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'enemy',
      content: '哥布林挥刀',
      log_type: 'combat',
      dice_result: {
        attack: { d20: 12 },
        damage: 3,
      },
      state_changes: [
        'char-1 HP 0',
        '死亡豁免 成功 0/3，失败 1/3',
        '状态 unconscious',
      ],
    })
    const updater = deps.setCombat.mock.calls.find(([arg]) => typeof arg === 'function')[0]
    expect(updater({
      entities: {
        'char-1': { id: 'char-1', hp_current: 12 },
      },
    })).toMatchObject({
      current_turn_index: 1,
      round_number: 1,
      entity_positions: { 'char-1': { x: 5, y: 5 } },
      entities: {
        'char-1': {
          hp_current: 0,
          death_saves: { successes: 0, failures: 1, stable: false },
          conditions: ['unconscious'],
          life_state: 'dying',
        },
      },
    })
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: false, movement_used: 0 })
    expect(processingRef.current).toBe(false)
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('pauses the ai loop when a reaction prompt is returned', async () => {
    getCombatMock.mockResolvedValue({
      round_number: 1,
      current_turn_index: 0,
      turn_order: [{ character_id: 'enemy-1', is_player: false }],
    })
    aiTurnMock.mockResolvedValue({
      actor_id: 'enemy-1',
      actor_name: '哥布林',
      narration: '哥布林攻击',
      attack_result: {},
      target_id: 'char-1',
      target_new_hp: 10,
      next_turn_index: 0,
      round_number: 1,
      reaction_prompt: { context: '可用反应' },
      player_can_react: true,
    })

    const { result, deps } = renderAiTurns()

    await act(async () => {
      await result.current.triggerAiTurn()
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith({ context: '可用反应' })
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('adds skirmisher reposition summaries to ai combat logs', async () => {
    getCombatMock
      .mockResolvedValueOnce({
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'enemy-1', is_player: false }],
      })
      .mockResolvedValueOnce({
        current_turn_index: 1,
        turn_order: [
          { character_id: 'enemy-1', is_player: false },
          { character_id: 'char-1', is_player: true },
        ],
        turn_states: {
          'char-1': { action_used: false, movement_used: 0 },
        },
      })
    aiTurnMock.mockResolvedValue({
      actor_id: 'enemy-1',
      actor_name: 'Knife Dancer',
      narration: 'Knife Dancer throws a blade and slips back.',
      attack_result: {},
      target_id: 'char-1',
      next_turn_index: 1,
      round_number: 1,
      skirmisher_reposition: {
        from: { x: 5, y: 2 },
        to: { x: 5, y: 0 },
        steps: 2,
      },
    })

    const { result, deps } = renderAiTurns()

    await act(async () => {
      const promise = result.current.triggerAiTurn()
      await Promise.resolve()
      await Promise.resolve()
      await vi.runOnlyPendingTimersAsync()
      await promise
    })

    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      state_changes: ['游击撤步 10ft：5,2 -> 5,0'],
    }))
  })

  it('does not drive an ai turn when fresh combat already contains a pending player reaction', async () => {
    const pendingReaction = {
      trigger: 'incoming_attack',
      attacker_id: 'enemy-1',
      available_reactions: [{ type: 'shield' }],
    }
    getCombatMock.mockResolvedValue({
      round_number: 1,
      current_turn_index: 0,
      turn_order: [{ character_id: 'enemy-1', is_player: false }],
      turn_states: {
        'char-1': { pending_attack_reaction: pendingReaction },
      },
    })

    const { result, deps } = renderAiTurns()

    await act(async () => {
      await result.current.triggerAiTurn()
    })

    expect(aiTurnMock).not.toHaveBeenCalled()
    expect(deps.setTurnState).toHaveBeenCalledWith({ pending_attack_reaction: pendingReaction })
    expect(deps.setReactionPrompt).toHaveBeenCalledWith({
      ...pendingReaction,
      reactor_character_id: 'char-1',
    })
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('pauses ai and stores reaction prompts for another controlled character as a watcher notice', async () => {
    getCombatMock.mockResolvedValueOnce({
      round_number: 1,
      current_turn_index: 0,
      turn_order: [{ character_id: 'enemy-1', is_player: false }],
    })
    aiTurnMock.mockResolvedValue({
      actor_id: 'enemy-1',
      actor_name: 'Enemy Mage',
      narration: 'Enemy Mage begins casting.',
      attack_result: {},
      target_id: 'guest-char',
      target_new_hp: null,
      next_turn_index: 0,
      round_number: 1,
      reaction_prompt: {
        trigger: 'spell_cast',
        reactor_character_id: 'guest-char',
      },
      player_can_react: true,
    })

    const { result, deps } = renderAiTurns()

    await act(async () => {
      const promise = result.current.triggerAiTurn()
      await Promise.resolve()
      await Promise.resolve()
      await vi.runOnlyPendingTimersAsync()
      await promise
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith({
      trigger: 'spell_cast',
      reactor_character_id: 'guest-char',
    })
    expect(deps.setTurnState).not.toHaveBeenCalledWith({ action_used: false })
  })

  it('quietly stops when the backend rejects a stale ai turn token', async () => {
    getCombatMock.mockResolvedValue({
      round_number: 1,
      current_turn_index: 0,
      turn_order: [{ character_id: 'enemy-1', is_player: false }],
    })
    aiTurnMock.mockRejectedValue(new Error('AI turn token is stale; refresh combat state'))

    const { result, deps } = renderAiTurns()

    await act(async () => {
      await result.current.triggerAiTurn()
    })

    expect(aiTurnMock).toHaveBeenCalledWith('sess-1', '1:0:enemy-1')
    expect(deps.addLog).not.toHaveBeenCalled()
    expect(deps.setIsProcessing).toHaveBeenLastCalledWith(false)
  })
})
