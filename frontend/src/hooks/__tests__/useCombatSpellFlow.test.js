import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { spellRollMock, spellConfirmMock, predictMock, rollDice3DMock } = vi.hoisted(() => ({
  spellRollMock: vi.fn(),
  spellConfirmMock: vi.fn(),
  predictMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    spellRoll: spellRollMock,
    spellConfirm: spellConfirmMock,
    predict: predictMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

import { useCombatSpellFlow } from '../useCombatSpellFlow'

describe('useCombatSpellFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    predictMock.mockResolvedValue(null)
    spellRollMock.mockResolvedValue({
      pending_spell_id: 'pending-spell-1',
      damage_dice: '2d6',
      targets: [{ id: 'enemy-1', name: '训练假人' }],
      turn_state: { action_used: true },
    })
    spellConfirmMock.mockResolvedValue({
      target_id: 'enemy-1',
      target_new_hp: 3,
      remaining_slots: { '1st': 1 },
      narration: '魔法飞弹击中训练假人',
      turn_state: { action_used: true, spell_cast: true },
      combat_over: false,
    })
    rollDice3DMock.mockResolvedValue({ total: 7, rolls: [3, 4] })
  })

  it('runs the two-step spell flow and applies confirm results after the dice delay', async () => {
    const processingRef = { current: false }
    const setIsProcessing = vi.fn()
    const setSpellModalOpen = vi.fn()
    const setError = vi.fn()
    const setTurnState = vi.fn()
    const setCombat = vi.fn()
    const setPlayerSpellSlots = vi.fn()
    const addLog = vi.fn()
    const setSelectedTarget = vi.fn()
    const setCombatOver = vi.fn()
    const showDice = vi.fn()

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      processingRef,
      setIsProcessing,
      setSpellModalOpen,
      setError,
      setTurnState,
      setCombat,
      setPlayerSpellSlots,
      addLog,
      setSelectedTarget,
      setCombatOver,
      showDice,
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'char-1', id: 'char-1' }],
      },
    }))

    await act(async () => {
      await result.current({ name: '魔法飞弹', type: 'damage' }, 1)
    })

    expect(spellRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      '魔法飞弹',
      1,
      'enemy-1',
      ['enemy-1'],
      '1:0:char-1',
      null,
      null,
    )
    expect(addLog).toHaveBeenCalledWith({
      role: 'system',
      content: '魔法飞弹 → 训练假人 — 掷骰 2d6',
      log_type: 'system',
    })
    expect(setSpellModalOpen).toHaveBeenCalledWith(false)
    expect(processingRef.current).toBe(true)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200)
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(6, 2)
    expect(showDice).toHaveBeenCalledWith({ faces: 6, result: 7, label: '魔法飞弹', count: 2 })
    expect(spellConfirmMock).toHaveBeenCalledWith('sess-1', 'pending-spell-1', [3, 4])

    const hpUpdater = setCombat.mock.calls[0][0]
    expect(hpUpdater({
      entities: {
        'enemy-1': { id: 'enemy-1', name: '训练假人', hp_current: 7 },
      },
    }).entities['enemy-1'].hp_current).toBe(3)
    expect(setTurnState).toHaveBeenLastCalledWith({ action_used: true, spell_cast: true })
    expect(setPlayerSpellSlots).toHaveBeenCalledWith({ '1st': 1 })
    expect(addLog).toHaveBeenLastCalledWith({
      role: 'player',
      content: '魔法飞弹击中训练假人',
      log_type: 'combat',
      dice_result: null,
      state_changes: [
        '训练假人 HP 3',
        '法术位剩余 1环 1',
        '动作已用',
      ],
    })
    expect(setSelectedTarget).toHaveBeenCalledWith(null)
    expect(processingRef.current).toBe(false)
    expect(setIsProcessing).toHaveBeenLastCalledWith(false)
  })

  it('rolls a d20 before confirming a spell attack and passes the crit context through the backend flow', async () => {
    spellRollMock.mockResolvedValueOnce({
      pending_spell_id: 'pending-fire-bolt',
      damage_dice: '1d10',
      spell_attack_required: true,
      hit: true,
      is_crit: true,
      attack_roll: {
        d20: 20,
        attack_total: 25,
        target_ac: 15,
        hit: true,
        is_crit: true,
      },
      targets: [{ id: 'enemy-1', name: 'Training Dummy' }],
      turn_state: { action_used: false },
    })
    rollDice3DMock
      .mockResolvedValueOnce({ total: 20, rolls: [20] })
      .mockResolvedValueOnce({ total: 8, rolls: [8] })

    const processingRef = { current: false }
    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      processingRef,
      setIsProcessing: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      addLog: vi.fn(),
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice: vi.fn(),
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'char-1', id: 'char-1' }],
      },
    }))

    await act(async () => {
      await result.current({ name: 'Fire Bolt', name_en: 'Fire Bolt', type: 'damage' }, 0)
    })

    expect(rollDice3DMock).toHaveBeenNthCalledWith(1, 20, 1)
    expect(spellRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      'Fire Bolt',
      0,
      'enemy-1',
      ['enemy-1'],
      '1:0:char-1',
      20,
      null,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200)
    })

    expect(rollDice3DMock).toHaveBeenNthCalledWith(2, 10, 1)
    expect(spellConfirmMock).toHaveBeenCalledWith('sess-1', 'pending-fire-bolt', [8])
  })

  it('rolls two d20s for disadvantaged spell attacks and forwards both raw dice', async () => {
    spellRollMock.mockResolvedValueOnce({
      pending_spell_id: 'pending-fire-bolt-miss',
      damage_dice: '1d10',
      spell_attack_required: true,
      hit: false,
      is_crit: false,
      attack_roll: {
        d20: 4,
        d20_rolls: [18, 4],
        selected_d20: 4,
        other_roll: 18,
        d20_selection: 'disadvantage',
        attack_bonus: 5,
        attack_total: 9,
        target_ac: 15,
        hit: false,
        is_crit: false,
        is_fumble: false,
        disadvantage: true,
        roll_state: 'disadvantage',
        disadvantage_sources: ['attacker poisoned'],
      },
      targets: [{ id: 'enemy-1', name: 'Training Dummy' }],
      turn_state: { action_used: false },
    })
    rollDice3DMock.mockResolvedValueOnce({ total: 22, rolls: [18, 4] })
    const processingRef = { current: false }
    const showDice = vi.fn()
    const addLog = vi.fn()

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      processingRef,
      setIsProcessing: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      addLog,
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice,
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'char-1', id: 'char-1' }],
      },
      prediction: { advantage: false, disadvantage: true },
    }))

    await act(async () => {
      await result.current({ name: 'Fire Bolt', name_en: 'Fire Bolt', type: 'damage' }, 0)
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(20, 2)
    expect(showDice).toHaveBeenCalledWith({
      faces: 20,
      result: 4,
      label: '法术攻击检定（劣势）',
      count: 2,
    })
    expect(spellRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      'Fire Bolt',
      0,
      'enemy-1',
      ['enemy-1'],
      '1:0:char-1',
      18,
      4,
    )
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      dice_result: {
        attack: expect.objectContaining({
          d20: 4,
          d20_rolls: [18, 4],
          selected_d20: 4,
          other_roll: 18,
          d20_selection: 'disadvantage',
          disadvantage: true,
          roll_state: 'disadvantage',
        }),
      },
    }))
    expect(spellConfirmMock).toHaveBeenCalledWith('sess-1', 'pending-fire-bolt-miss', null)
  })

  it('refreshes prediction before spell attack rolls so hidden caster advantage uses two d20s', async () => {
    predictMock.mockResolvedValueOnce({
      advantage: true,
      disadvantage: false,
      advantage_sources: ['attacker hidden'],
    })
    spellRollMock.mockResolvedValueOnce({
      pending_spell_id: 'pending-hidden-fire-bolt',
      damage_dice: '1d10',
      spell_attack_required: true,
      hit: true,
      is_crit: false,
      attack_roll: {
        d20: 16,
        d20_rolls: [7, 16],
        selected_d20: 16,
        other_roll: 7,
        d20_selection: 'advantage',
        attack_bonus: 5,
        attack_total: 21,
        target_ac: 12,
        hit: true,
        is_crit: false,
        advantage: true,
        roll_state: 'advantage',
        advantage_sources: ['attacker hidden'],
      },
      targets: [{ id: 'enemy-1', name: 'Reveal Witness' }],
      turn_state: { action_used: true },
    })
    rollDice3DMock
      .mockResolvedValueOnce({ total: 23, rolls: [7, 16] })
      .mockResolvedValueOnce({ total: 6, rolls: [6] })

    const processingRef = { current: false }
    const showDice = vi.fn()

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      processingRef,
      setIsProcessing: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      addLog: vi.fn(),
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice,
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'char-1', id: 'char-1' }],
      },
      prediction: null,
    }))

    await act(async () => {
      await result.current({
        name: 'Fire Bolt',
        name_en: 'Fire Bolt',
        type: 'damage',
        desc: 'Make a ranged spell attack.',
      }, 0)
    })

    expect(predictMock).toHaveBeenCalledWith('sess-1', 'char-1', 'enemy-1', 'atk', true)
    expect(rollDice3DMock).toHaveBeenNthCalledWith(1, 20, 2)
    expect(showDice).toHaveBeenCalledWith({
      faces: 20,
      result: 16,
      label: '法术攻击检定（优势）',
      count: 2,
    })
    expect(spellRollMock).toHaveBeenCalledWith(
      'sess-1',
      'char-1',
      'Fire Bolt',
      0,
      'enemy-1',
      ['enemy-1'],
      '1:0:char-1',
      7,
      16,
    )
  })

  it('merges resurrection result state from spell confirmation', async () => {
    spellRollMock.mockResolvedValueOnce({
      pending_spell_id: 'pending-raise-dead',
      targets: [{ id: 'ally-1', name: '倒下的队友' }],
      turn_state: { action_used: false },
    })
    spellConfirmMock.mockResolvedValueOnce({
      target_id: 'ally-1',
      target_new_hp: 1,
      target_state: {
        target_id: 'ally-1',
        new_hp: 1,
        death_saves: null,
        conditions: [],
        life_state: 'alive',
      },
      resurrection_results: [
        {
          target_id: 'ally-1',
          resurrected: true,
          new_hp: 1,
          death_saves: null,
          conditions: [],
          life_state: 'alive',
        },
      ],
      remaining_slots: { '5th': 0 },
      narration: '死者重新睁开双眼。',
      turn_state: { action_used: true },
      combat_over: false,
    })

    const processingRef = { current: false }
    const setCombat = vi.fn()
    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'cleric-1',
      selectedTarget: 'ally-1',
      isProcessing: false,
      processingRef,
      setIsProcessing: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setCombat,
      setPlayerSpellSlots: vi.fn(),
      addLog: vi.fn(),
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice: vi.fn(),
    }))

    await act(async () => {
      await result.current({ name: '复活死者', type: 'utility' }, 5)
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200)
    })

    const stateUpdater = setCombat.mock.calls[0][0]
    const updated = stateUpdater({
      entities: {
        'ally-1': {
          id: 'ally-1',
          hp_current: 0,
          death_saves: { successes: 0, failures: 3, stable: false },
          conditions: ['unconscious'],
          life_state: 'dead',
        },
      },
    })

    expect(updated.entities['ally-1']).toMatchObject({
      hp_current: 1,
      death_saves: null,
      conditions: [],
      life_state: 'alive',
    })
  })

  it('sends explicit AoE targets gathered from the hovered template cells', async () => {
    spellRollMock.mockResolvedValueOnce({
      pending_spell_id: 'pending-fireball',
      damage_dice: '8d6',
      targets: [
        { id: 'goblin-1', name: '哥布林' },
        { id: 'goblin-2', name: '哥布林弓手' },
      ],
      turn_state: { action_used: true },
    })
    const processingRef = { current: false }

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'wizard-1',
      selectedTarget: null,
      aoeHover: '6_5',
      isProcessing: false,
      processingRef,
      setIsProcessing: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      addLog: vi.fn(),
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice: vi.fn(),
      combat: {
        round_number: 2,
        current_turn_index: 0,
        turn_order: [{ character_id: 'wizard-1', id: 'wizard-1' }],
        entity_positions: {
          'wizard-1': { x: 5, y: 5 },
          'goblin-1': { x: 6, y: 5 },
          'goblin-2': { x: 7, y: 5 },
          'goblin-far': { x: 10, y: 10 },
        },
        entities: {
          'wizard-1': { id: 'wizard-1', is_enemy: false, hp_current: 18 },
          'goblin-1': { id: 'goblin-1', is_enemy: true, hp_current: 7 },
          'goblin-2': { id: 'goblin-2', is_enemy: true, hp_current: 7 },
          'goblin-far': { id: 'goblin-far', is_enemy: true, hp_current: 7 },
        },
      },
    }))

    await act(async () => {
      await result.current({
        name: '火球术',
        type: 'damage',
        aoe: true,
        desc: '半径5尺爆炸',
      }, 3)
    })

    expect(spellRollMock).toHaveBeenCalledWith(
      'sess-1',
      'wizard-1',
      '火球术',
      3,
      'wizard-1',
      ['wizard-1', 'goblin-1', 'goblin-2'],
      '2:0:wizard-1',
      null,
      null,
    )
  })

  it('blocks empty AoE ground points instead of sending an empty target list', async () => {
    const setError = vi.fn()
    const setIsProcessing = vi.fn()
    const setSpellModalOpen = vi.fn()
    const processingRef = { current: false }

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'wizard-1',
      selectedTarget: null,
      aoeHover: '12_12',
      isProcessing: false,
      processingRef,
      setIsProcessing,
      setSpellModalOpen,
      setError,
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      addLog: vi.fn(),
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice: vi.fn(),
      combat: {
        entity_positions: {
          'wizard-1': { x: 5, y: 5 },
          'goblin-1': { x: 6, y: 5 },
        },
        entities: {
          'wizard-1': { id: 'wizard-1', is_enemy: false, hp_current: 18 },
          'goblin-1': { id: 'goblin-1', is_enemy: true, hp_current: 7 },
        },
      },
    }))

    await act(async () => {
      await result.current({
        name: 'Fireball',
        type: 'damage',
        aoe: true,
        desc: '5ft radius blast',
      }, 3)
    })

    expect(spellRollMock).not.toHaveBeenCalled()
    expect(setError).toHaveBeenCalledWith('法术范围内没有可结算目标')
    expect(setSpellModalOpen).not.toHaveBeenCalled()
    expect(setIsProcessing).not.toHaveBeenCalled()
    expect(processingRef.current).toBe(false)
  })

  it('does not cast when the current user does not control this turn', async () => {
    const setIsProcessing = vi.fn()
    const setSpellModalOpen = vi.fn()

    const { result } = renderHook(() => useCombatSpellFlow({
      sessionId: 'sess-1',
      playerId: 'char-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      canActThisTurn: false,
      processingRef: { current: false },
      setIsProcessing,
      setSpellModalOpen,
      setError: vi.fn(),
      setTurnState: vi.fn(),
      setCombat: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      addLog: vi.fn(),
      setSelectedTarget: vi.fn(),
      setCombatOver: vi.fn(),
      showDice: vi.fn(),
    }))

    await act(async () => {
      await result.current({ name: '魔法飞弹', type: 'damage' }, 1)
    })

    expect(spellRollMock).not.toHaveBeenCalled()
    expect(setSpellModalOpen).not.toHaveBeenCalled()
    expect(setIsProcessing).not.toHaveBeenCalled()
  })
})
