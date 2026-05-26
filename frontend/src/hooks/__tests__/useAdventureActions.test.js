import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../api/client', () => ({
  gameApi: {
    action: vi.fn(),
    getSession: vi.fn().mockResolvedValue({ player: null, companions: [] }),
  },
  charactersApi: {
    prepareSpells: vi.fn(),
  },
}))

import { gameApi } from '../../api/client'
import { useAdventureActions } from '../useAdventureActions'


function makeDeps(overrides = {}) {
  return {
    sessionId: 'sess-1',
    playerId: 'char-1',
    isLoading: false,
    input: '我撬开后门。',
    inputRef: { current: { focus: vi.fn() } },
    companions: [],
    navigate: vi.fn(),
    addLog: vi.fn(),
    setChoices: vi.fn(),
    setError: vi.fn(),
    setInput: vi.fn(),
    setIsLoading: vi.fn(),
    setJournalLoading: vi.fn(),
    setJournalText: vi.fn(),
    setPendingCheck: vi.fn(),
    setPlayer: vi.fn(),
    setPrepareOpen: vi.fn(),
    setRestOpen: vi.fn(),
    setSession: vi.fn(),
    setCompanions: vi.fn(),
    buildDialogueQueue: vi.fn().mockReturnValue([{ role: 'dm', text: '后巷门锁弹开。' }]),
    enterDialogueStage: vi.fn(),
    rollPending: vi.fn(),
    ...overrides,
  }
}


beforeEach(() => {
  vi.clearAllMocks()
})


describe('useAdventureActions', () => {
  it('attaches HTTP action visibility to DM theatre segments', async () => {
    const visibility = { scope: 'group', group_id: 'alley', visible_to_user_ids: ['me'] }
    gameApi.action.mockResolvedValue({
      type: 'exploration',
      narrative: '后巷门锁弹开。',
      companion_reactions: '',
      dice_display: [],
      player_choices: [],
      needs_check: { required: false },
      combat_triggered: false,
      combat_ended: false,
      visibility,
    })
    const deps = makeDeps()
    const { result } = renderHook(() => useAdventureActions(deps))

    await act(async () => {
      await result.current.handleAction()
    })

    expect(deps.enterDialogueStage).toHaveBeenCalledWith([
      { role: 'dm', text: '后巷门锁弹开。', visibility },
    ])
  })

  it('attaches multiplayer table reason to DM theatre segments', async () => {
    gameApi.action.mockResolvedValue({
      type: 'multiplayer_table',
      narrative: '镜头转向酒馆组，请酒馆组玩家先行动。',
      table_reason: '酒馆组已有待处理行动，玩家明确要求切镜头。',
      table_decision: {
        decision: 'switch_focus',
        reason_code: 'switch_focus',
        target_group_id: 'tavern',
      },
      companion_reactions: '',
      dice_display: [],
      player_choices: [],
      needs_check: { required: false },
      combat_triggered: false,
      combat_ended: false,
    })
    const deps = makeDeps({
      buildDialogueQueue: vi.fn().mockReturnValue([{ role: 'dm', text: '镜头转向酒馆组，请酒馆组玩家先行动。' }]),
    })
    const { result } = renderHook(() => useAdventureActions(deps))

    await act(async () => {
      await result.current.handleAction()
    })

    expect(deps.enterDialogueStage).toHaveBeenCalledWith([
      {
        role: 'dm',
        text: '镜头转向酒馆组，请酒馆组玩家先行动。',
        table_reason: '酒馆组已有待处理行动，玩家明确要求切镜头。',
        table_decision: {
          decision: 'switch_focus',
          reason_code: 'switch_focus',
          target_group_id: 'tavern',
        },
      },
    ])
  })

  it('blocks action submission when the caller reports multiplayer sync is unavailable', async () => {
    gameApi.action.mockResolvedValue({
      type: 'exploration',
      narrative: '这段不应该出现。',
      companion_reactions: '',
      dice_display: [],
      player_choices: [],
      needs_check: { required: false },
      combat_triggered: false,
      combat_ended: false,
    })
    const deps = makeDeps({
      actionBlockedReason: '房间正在重新同步，请恢复连接后再发言。',
    })
    const { result } = renderHook(() => useAdventureActions(deps))

    await act(async () => {
      await result.current.handleAction()
    })

    expect(gameApi.action).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('房间正在重新同步，请恢复连接后再发言。')
    expect(deps.setInput).not.toHaveBeenCalled()
    expect(deps.addLog).not.toHaveBeenCalled()
    expect(deps.inputRef.current.focus).toHaveBeenCalledTimes(1)
  })
})
