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
import { formatRestSummary, useAdventureActions } from '../useAdventureActions'


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

  it('sends an idempotency key with adventure actions', async () => {
    gameApi.action.mockResolvedValue({
      type: 'exploration',
      narrative: '鍚庨棬寮€浜嗐€?',
      companion_reactions: '',
      dice_display: [],
      player_choices: [],
      needs_check: { required: false },
      combat_triggered: false,
      combat_ended: false,
    })
    const deps = makeDeps()
    const { result } = renderHook(() => useAdventureActions(deps))

    await act(async () => {
      await result.current.handleAction(undefined, { idempotencyKey: 'fixed-action-key' })
    })

    expect(gameApi.action).toHaveBeenCalledWith(expect.objectContaining({
      session_id: 'sess-1',
      action_text: deps.input.trim(),
      action_source: 'human_input',
      idempotency_key: 'fixed-action-key',
    }))
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

  it('formats detailed long rest rule results for the adventure log', () => {
    const summary = formatRestSummary({
      characters: [{
        name: 'Aria',
        hp_recovered: 7,
        hp_current: 12,
        hp_max: 12,
        hit_dice_restored: 1,
        hit_dice_remaining: 1,
        hit_dice_total: 3,
        slots_restored: { '1st': 2 },
        exhaustion_level_before: 2,
        exhaustion_level_after: 1,
        conditions_removed: ['poisoned'],
        death_saves_reset: true,
      }],
    }, 'long')

    expect(summary).toContain('Aria HP+7 → 12/12')
    expect(summary).toContain('生命骰+1')
    expect(summary).toContain('剩余 1/3')
    expect(summary).toContain('法术位 1st+2')
    expect(summary).toContain('力竭 2→1')
    expect(summary).toContain('移除 poisoned')
    expect(summary).toContain('重置濒死豁免')
  })

  it('formats short rest hit dice details without hiding no-op cases', () => {
    expect(formatRestSummary({
      characters: [{
        name: 'Borin',
        hp_recovered: 5,
        hp_current: 9,
        hp_max: 12,
        hit_dice_spent: 1,
        hit_die_roll: 3,
        con_mod: 2,
        hit_dice_remaining: 0,
        hit_dice_total: 1,
      }],
    }, 'short')).toContain('生命骰 3+2')

    expect(formatRestSummary({
      characters: [{
        name: 'Celia',
        hp_recovered: 0,
        hp_current: 10,
        hp_max: 10,
        no_healing_needed: true,
        hit_dice_remaining: 1,
        hit_dice_total: 1,
      }],
    }, 'short')).toContain('满血未消耗生命骰')
  })
})
