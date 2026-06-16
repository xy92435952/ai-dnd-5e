/**
 * useDialogueWsSync 单元测试 —— WS 事件分发逻辑。
 *
 * 测试关注点：
 *   - dm_thinking_start：仅其他玩家触发时 setIsLoading(true)
 *   - dm_responded：非自己触发时启动剧场；无论谁触发都 loadSession
 *   - dm_speak_turn：用 functional updater 更新 _currentSpeaker
 *   - member_*: 调 roomsApi.get 刷新房间
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

vi.mock('../../api/client', () => ({
  roomsApi: {
    get: vi.fn().mockResolvedValue({
      is_multiplayer: true,
      current_speaker_user_id: 'u-next',
      members: [],
    }),
  },
}))

import { roomsApi } from '../../api/client'
import { useDialogueWsSync } from '../useDialogueWsSync'


function makeDeps(overrides = {}) {
  return {
    sessionId: 'sess-1',
    myUserId:  'me',
    room: {
      party_groups: [
        { id: 'alley', member_user_ids: ['me'] },
        { id: 'tower', member_user_ids: ['other'] },
      ],
    },
    companions: [{ name: '法师' }],
    buildDialogueQueue: vi.fn().mockReturnValue([{ role: 'dm', text: 'hi' }]),
    enterDialogueStage: vi.fn(),
    loadSession:        vi.fn(),
    setIsLoading:       vi.fn(),
    setRoom:            vi.fn(),
    setPendingExplorationReaction: vi.fn(),
    ...overrides,
  }
}


beforeEach(() => {
  vi.clearAllMocks()
})


describe('useDialogueWsSync', () => {
  it('dm_thinking_start: 别人触发 → setIsLoading(true)', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({ type: 'dm_thinking_start', by_user_id: 'other', action_text: '...' })
    })
    expect(deps.setIsLoading).toHaveBeenCalledWith(true)
  })

  it('dm_thinking_start: 自己触发 → 不动 isLoading', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({ type: 'dm_thinking_start', by_user_id: 'me', action_text: '...' })
    })
    expect(deps.setIsLoading).not.toHaveBeenCalled()
  })

  it('dm_responded: 别人触发 → 启动剧场 + 关 loading + loadSession', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({
        type: 'dm_responded', by_user_id: 'other',
        narrative: 'DM 说', companion_reactions: '',
        action_type: 'exploration', dice_display: [],
        combat_triggered: false, combat_ended: false,
      })
    })
    expect(deps.setIsLoading).toHaveBeenCalledWith(false)
    expect(deps.buildDialogueQueue).toHaveBeenCalled()
    expect(deps.enterDialogueStage).toHaveBeenCalled()
    expect(deps.loadSession).toHaveBeenCalled()
  })

  it('dm_responded: 自己触发 → 不启动剧场（HTTP 响应已经触发了）但仍 loadSession', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({
        type: 'dm_responded', by_user_id: 'me',
        narrative: 'DM 说', companion_reactions: '',
        action_type: 'exploration', dice_display: [],
        combat_triggered: false, combat_ended: false,
      })
    })
    expect(deps.enterDialogueStage).not.toHaveBeenCalled()
    expect(deps.loadSession).toHaveBeenCalled()
  })

  it('dm_responded: 带可见范围但不包含自己 → 忽略剧场和刷新', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({
        type: 'dm_responded',
        by_user_id: 'other',
        narrative: '后巷私密信息',
        companion_reactions: '',
        action_type: 'exploration',
        dice_display: [],
        combat_triggered: false,
        combat_ended: false,
        visibility: {
          scope: 'group',
          group_id: 'alley',
          visible_to_user_ids: ['u-alley-1'],
        },
      })
    })
    expect(deps.setIsLoading).not.toHaveBeenCalledWith(false)
    expect(deps.buildDialogueQueue).not.toHaveBeenCalled()
    expect(deps.enterDialogueStage).not.toHaveBeenCalled()
    expect(deps.loadSession).not.toHaveBeenCalled()
  })

  it('dm_responded: group visibility missing explicit targets only reaches my own group', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))

    act(() => {
      result.current({
        type: 'dm_responded',
        by_user_id: 'other',
        narrative: '后巷低声交换口令。',
        companion_reactions: '',
        action_type: 'exploration',
        dice_display: [],
        combat_triggered: false,
        combat_ended: false,
        visibility: { scope: 'group', group_id: 'alley', visible_to_user_ids: [] },
      })
    })
    expect(deps.enterDialogueStage).toHaveBeenCalled()

    vi.clearAllMocks()
    act(() => {
      result.current({
        type: 'dm_responded',
        by_user_id: 'other',
        narrative: '钟楼找到了第二张地图。',
        companion_reactions: '',
        action_type: 'exploration',
        dice_display: [],
        combat_triggered: false,
        combat_ended: false,
        visibility: { scope: 'group', group_id: 'tower', visible_to_user_ids: [] },
      })
    })
    expect(deps.enterDialogueStage).not.toHaveBeenCalled()
    expect(deps.loadSession).not.toHaveBeenCalled()
  })

  it('dm_responded: private visibility missing explicit targets is hidden', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({
        type: 'dm_responded',
        by_user_id: 'other',
        narrative: '无目标私密暗号。',
        companion_reactions: '',
        action_type: 'exploration',
        dice_display: [],
        combat_triggered: false,
        combat_ended: false,
        visibility: { scope: 'private', visible_to_user_ids: [] },
      })
    })
    expect(deps.buildDialogueQueue).not.toHaveBeenCalled()
    expect(deps.enterDialogueStage).not.toHaveBeenCalled()
    expect(deps.loadSession).not.toHaveBeenCalled()
  })

  it('dm_responded: 可见事件进入剧场时把 visibility 附到 DM 段落', () => {
    const visibility = {
      scope: 'group',
      group_id: 'alley',
      visible_to_user_ids: ['me'],
    }
    const queue = [{ role: 'dm', text: '后巷门锁弹开。' }]
    const deps = makeDeps({
      buildDialogueQueue: vi.fn().mockReturnValue(queue),
    })
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({
        type: 'dm_responded',
        by_user_id: 'other',
        narrative: '后巷门锁弹开。',
        companion_reactions: '',
        action_type: 'exploration',
        dice_display: [],
        combat_triggered: false,
        combat_ended: false,
        visibility,
      })
    })
    expect(deps.enterDialogueStage).toHaveBeenCalledWith([
      { role: 'dm', text: '后巷门锁弹开。', visibility },
    ])
  })

  it('dm_responded: table-only 事件进入剧场时保留 table_reason', () => {
    const queue = [{ role: 'dm', text: '镜头转向酒馆组，请酒馆组玩家先行动。' }]
    const deps = makeDeps({
      buildDialogueQueue: vi.fn().mockReturnValue(queue),
    })
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({
        type: 'dm_responded',
        by_user_id: 'other',
        narrative: '镜头转向酒馆组，请酒馆组玩家先行动。',
        companion_reactions: '',
        action_type: 'multiplayer_table',
        dice_display: [],
        combat_triggered: false,
        combat_ended: false,
        table_reason: '酒馆组已有待处理行动，玩家明确要求切镜头。',
        table_decision: {
          decision: 'switch_focus',
          reason_code: 'switch_focus',
          target_group_id: 'tavern',
        },
      })
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

  it('dm_speak_turn: 用 functional updater 更新 _currentSpeaker', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    act(() => {
      result.current({ type: 'dm_speak_turn', user_id: 'u-next', auto: true })
    })
    expect(deps.setRoom).toHaveBeenCalledWith(expect.any(Function))
    // 模拟 setRoom 接到的函数：旧值 → 新值
    const updater = deps.setRoom.mock.calls[0][0]
    expect(updater({ _currentSpeaker: 'u-prev', members: [] })).toEqual({
      _currentSpeaker: 'u-next', members: [],
    })
    expect(updater(null)).toBeNull()  // 房间不存在时不构造对象
  })

  it('member_online: 调 roomsApi.get 刷新房间', async () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    await act(async () => {
      result.current({ type: 'member_online', user_id: 'other' })
      // 等待 roomsApi.get promise 链
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(roomsApi.get).toHaveBeenCalledWith('sess-1')
  })

  it('member_online: 事件自带 members 时直接更新房间，避免额外刷新', async () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    await act(async () => {
      result.current({
        type: 'member_online',
        user_id: 'other',
        members: [{ user_id: 'other', display_name: 'Other', is_online: true }],
      })
      await Promise.resolve()
    })
    expect(roomsApi.get).not.toHaveBeenCalled()
    expect(deps.setRoom).toHaveBeenCalledWith(expect.any(Function))
    const updater = deps.setRoom.mock.calls[0][0]
    expect(updater({ is_multiplayer: true, room_code: '234567', _currentSpeaker: 'me', members: [] })).toMatchObject({
      room_code: '234567',
      _currentSpeaker: 'me',
      members: [{ user_id: 'other', display_name: 'Other', is_online: true }],
    })
  })

  it('room_state_updated: 直接用完整房间快照更新 realtime room', async () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    await act(async () => {
      result.current({
        type: 'room_state_updated',
        room: {
          is_multiplayer: true,
          room_code: '765432',
          current_speaker_user_id: 'u-next',
          party_groups: [{ id: 'main', member_user_ids: ['me'] }],
        },
      })
      await Promise.resolve()
    })
    expect(roomsApi.get).not.toHaveBeenCalled()
    expect(deps.setRoom).toHaveBeenCalledWith(expect.any(Function))
    const updater = deps.setRoom.mock.calls[0][0]
    expect(updater({ is_multiplayer: true, room_code: '234567', _currentSpeaker: 'old' })).toMatchObject({
      room_code: '765432',
      _currentSpeaker: 'u-next',
      party_groups: [{ id: 'main', member_user_ids: ['me'] }],
    })
  })

  it('exploration_reaction_prompt: restores the private Feather Fall prompt without theatre replay', () => {
    const prompt = {
      type: 'feather_fall',
      reactor_character_id: 'bard-1',
      reactor_user_id: 'me',
      options: [{ type: 'feather_fall' }],
    }
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))

    act(() => {
      result.current({ type: 'exploration_reaction_prompt', prompt })
    })

    expect(deps.setPendingExplorationReaction).toHaveBeenCalledWith(prompt)
    expect(deps.setIsLoading).toHaveBeenCalledWith(false)
    expect(deps.enterDialogueStage).not.toHaveBeenCalled()
    expect(deps.loadSession).not.toHaveBeenCalled()
  })

  it('未知 type: 静默忽略不报错', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    expect(() => {
      act(() => result.current({ type: 'made_up_event' }))
    }).not.toThrow()
    expect(deps.loadSession).not.toHaveBeenCalled()
  })
})
