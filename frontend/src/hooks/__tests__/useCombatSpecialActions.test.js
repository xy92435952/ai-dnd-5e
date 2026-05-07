import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  smiteMock,
  useReactionMock,
  maneuverMock,
  rollDice3DMock,
} = vi.hoisted(() => ({
  smiteMock: vi.fn(),
  useReactionMock: vi.fn(),
  maneuverMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    smite: smiteMock,
    useReaction: useReactionMock,
    maneuver: maneuverMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

import { useCombatSpecialActions } from '../useCombatSpecialActions'

describe('useCombatSpecialActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    rollDice3DMock.mockResolvedValue({ total: 9, rolls: [4, 5] })
    smiteMock.mockResolvedValue({
      narration: '神圣能量爆发',
      remaining_slots: { '1st': 0 },
      target_id: 'enemy-1',
      target_new_hp: 2,
    })
    useReactionMock.mockResolvedValue({
      narration: '地狱斥责命中',
      turn_state: { reaction_used: true },
    })
    maneuverMock.mockResolvedValue({
      narration: '战技命中',
      turn_state: { action_used: true },
      class_resources: { superiority_dice_remaining: 2 },
      target_new_hp: 3,
      superiority_die_roll: 6,
      superiority_die: 'd8',
    })
  })

  function renderActions(overrides = {}) {
    const processingRef = { current: false }
    const deps = {
      sessionId: 'sess-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      smitePrompt: { show: true, targetId: 'enemy-1' },
      playerSubclassEffects: { superiority_die: 'd8' },
      processingRef,
      setIsProcessing: vi.fn(),
      setError: vi.fn(),
      setSmitePrompt: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      setTurnState: vi.fn(),
      setClassResources: vi.fn(),
      setCombat: vi.fn(),
      setReactionPrompt: vi.fn(),
      setCombatOver: vi.fn(),
      triggerAiTurn: vi.fn(),
      showDice: vi.fn(),
      addLog: vi.fn(),
      ...overrides,
    }
    return { deps, processingRef, ...renderHook(() => useCombatSpecialActions(deps)) }
  }

  it('rolls smite dice and applies target hp', async () => {
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleSmite(1)
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8, 2)
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 8, result: 9, label: '神圣斩击', count: 2 })
    expect(smiteMock).toHaveBeenCalledWith('sess-1', 1, false, [4, 5], 'enemy-1')
    expect(deps.setSmitePrompt).toHaveBeenCalledWith(null)

    const hpUpdater = deps.setCombat.mock.calls[0][0]
    expect(hpUpdater({
      entities: {
        'enemy-1': { id: 'enemy-1', hp_current: 8 },
      },
    }).entities['enemy-1'].hp_current).toBe(2)
  })

  it('uses reaction and resumes ai turns', async () => {
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleReaction('hellish_rebuke', 'enemy-1')
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(10, 2)
    expect(useReactionMock).toHaveBeenCalledWith('sess-1', 'hellish_rebuke', 'enemy-1')
    expect(deps.setTurnState).toHaveBeenCalledWith({ reaction_used: true })
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('runs maneuver against the selected target', async () => {
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleManeuver('trip_attack')
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8)
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 8, result: 9, label: '战技·trip_attack' })
    expect(maneuverMock).toHaveBeenCalledWith('sess-1', 'trip_attack', 'enemy-1')
    expect(deps.setClassResources).toHaveBeenCalledWith({ superiority_dice_remaining: 2 })
  })
})
