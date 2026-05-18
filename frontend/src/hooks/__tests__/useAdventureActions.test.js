import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../api/game', () => ({
  gameApi: {
    action: vi.fn(),
    actionStream: vi.fn(),
    getSession: vi.fn().mockResolvedValue({ player: null, companions: [] }),
  },
}))

vi.mock('../../api/characters', () => ({
  charactersApi: {
    prepareSpells: vi.fn(),
  },
}))

import { gameApi } from '../../api/game'
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
    setStreamingNarrative: vi.fn(),
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
    gameApi.actionStream.mockResolvedValue({
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
    gameApi.actionStream.mockResolvedValue({
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

  it('updates streaming narrative preview before the final response is applied', async () => {
    let streaming = ''
    const streamingSnapshots = []
    const setStreamingNarrative = vi.fn((next) => {
      streaming = typeof next === 'function' ? next(streaming) : next
      streamingSnapshots.push(streaming)
    })
    gameApi.actionStream.mockImplementation(async (_payload, handlers) => {
      handlers.onNarrativeDelta('雾')
      handlers.onNarrativeDelta('散')
      return {
        type: 'exploration',
        narrative: '雾散。',
        companion_reactions: '',
        dice_display: [],
        player_choices: [],
        needs_check: { required: false },
        combat_triggered: false,
        combat_ended: false,
      }
    })
    const deps = makeDeps({ setStreamingNarrative })
    const { result } = renderHook(() => useAdventureActions(deps))

    await act(async () => {
      await result.current.handleAction()
    })

    expect(gameApi.actionStream).toHaveBeenCalled()
    expect(streamingSnapshots).toContain('雾')
    expect(streamingSnapshots).toContain('雾散')
    expect(streamingSnapshots.at(-1)).toBe('')
    expect(deps.enterDialogueStage).toHaveBeenCalled()
  })
})
