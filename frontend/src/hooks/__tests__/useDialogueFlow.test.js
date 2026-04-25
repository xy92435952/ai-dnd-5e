/**
 * useDialogueFlow 单元测试 — 状态机 + 打字机 + 推进逻辑。
 *
 * 用 vi.useFakeTimers 控制打字机的 setTimeout，确保测试稳定。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDialogueFlow } from '../useDialogueFlow'


function createHook(addLog = vi.fn()) {
  return { addLog, ...renderHook(() => useDialogueFlow({ addLog })) }
}


describe('useDialogueFlow', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('初始为 chat 模式、空队列、typingDone=true', () => {
    const { result } = createHook()
    expect(result.current.dialogueMode).toBe('chat')
    expect(result.current.dialogueQueue).toEqual([])
    expect(result.current.dialogueIdx).toBe(0)
    expect(result.current.typingText).toBe('')
    expect(result.current.typingDone).toBe(true)
  })

  it('enterStage 切到 stage 模式', () => {
    const { result } = createHook()
    act(() => {
      result.current.enterStage([
        { speaker: 'DM', role: 'dm', text: '你看到一扇门' },
      ])
    })
    expect(result.current.dialogueMode).toBe('stage')
    expect(result.current.dialogueIdx).toBe(0)
    expect(result.current.dialogueQueue).toHaveLength(1)
  })

  it('enterStage 拒绝空队列（mode 仍为 chat）', () => {
    const { result } = createHook()
    act(() => { result.current.enterStage([]) })
    expect(result.current.dialogueMode).toBe('chat')
    act(() => { result.current.enterStage(null) })
    expect(result.current.dialogueMode).toBe('chat')
  })

  it('advance 在打字未完时立即打完文字', () => {
    const { result } = createHook()
    act(() => {
      result.current.enterStage([{ role: 'dm', text: 'short' }])
    })
    // 打字机 effect 已经把 typingDone=false
    expect(result.current.typingDone).toBe(false)
    act(() => { result.current.advance() })
    // 第一次 advance：补全文本
    expect(result.current.typingText).toBe('short')
    expect(result.current.typingDone).toBe(true)
  })

  it('advance 在打完后入 log + 推进 idx；播完队列回到 chat', () => {
    const { result, addLog } = createHook()
    act(() => {
      result.current.enterStage([
        { role: 'dm', text: 'a' },
        { role: 'companion', text: 'b' },
      ])
    })
    // 第 1 次 advance：补全字
    act(() => { result.current.advance() })
    // 第 2 次 advance：log 第 0 段，进 idx=1
    act(() => { result.current.advance() })
    expect(addLog).toHaveBeenCalledWith('dm', 'a', 'narrative')
    expect(result.current.dialogueIdx).toBe(1)
    expect(result.current.dialogueMode).toBe('stage')

    // 第 3 / 4 次：补全 + log 第 1 段，队列结束回 chat
    act(() => { result.current.advance() })
    act(() => { result.current.advance() })
    expect(addLog).toHaveBeenCalledWith('companion', 'b', 'companion')
    expect(result.current.dialogueMode).toBe('chat')
    expect(result.current.dialogueQueue).toEqual([])
  })

  it('短文本（≤60 字）走 30ms/字 打字机', () => {
    const { result } = createHook()
    const text = 'hello'   // 5 字
    act(() => {
      result.current.enterStage([{ role: 'dm', text }])
    })
    // 初始 60ms 启动延迟
    act(() => { vi.advanceTimersByTime(60) })
    expect(result.current.typingText).toBe('h')
    // 4 次 30ms 间隔后全部打完
    act(() => { vi.advanceTimersByTime(30 * 4) })
    expect(result.current.typingText).toBe('hello')
    expect(result.current.typingDone).toBe(true)
  })

  it('长文本（>150 字）跳过打字机，整段直接显示', () => {
    const { result } = createHook()
    const long = 'x'.repeat(180)
    act(() => {
      result.current.enterStage([{ role: 'dm', text: long }])
    })
    expect(result.current.typingDone).toBe(false)
    // 60ms 后整段一次性出现
    act(() => { vi.advanceTimersByTime(60) })
    expect(result.current.typingText).toBe(long)
    expect(result.current.typingDone).toBe(true)
  })
})
