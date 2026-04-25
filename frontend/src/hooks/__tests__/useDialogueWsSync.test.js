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
    companions: [{ name: '法师' }],
    buildDialogueQueue: vi.fn().mockReturnValue([{ role: 'dm', text: 'hi' }]),
    enterDialogueStage: vi.fn(),
    loadSession:        vi.fn(),
    setIsLoading:       vi.fn(),
    setRoom:            vi.fn(),
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

  it('未知 type: 静默忽略不报错', () => {
    const deps = makeDeps()
    const { result } = renderHook(() => useDialogueWsSync(deps))
    expect(() => {
      act(() => result.current({ type: 'made_up_event' }))
    }).not.toThrow()
    expect(deps.loadSession).not.toHaveBeenCalled()
  })
})
