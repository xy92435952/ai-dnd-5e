/**
 * useSkillCheck 单元测试 — 检定状态机 + 服务调用 + 音效副作用。
 *
 * 外部依赖（mock）：gameApi.skillCheck / rollDice3D / juice.JuiceAudio / juice.shake
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// vi.mock 提升到文件顶部 —— 必须用 factory 函数
vi.mock('../../api/client', () => ({
  gameApi: {
    skillCheck: vi.fn(),
  },
}))
vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: vi.fn(),
}))
vi.mock('../../juice', () => ({
  JuiceAudio: { crit: vi.fn(), miss: vi.fn(), unlock: vi.fn() },
  shake:      vi.fn(),
}))

import { gameApi } from '../../api/client'
import { rollDice3D } from '../../components/DiceRollerOverlay'
import { JuiceAudio } from '../../juice'
import { useSkillCheck } from '../useSkillCheck'


function createHook(extra = {}) {
  const addLog = vi.fn()
  const view = renderHook(() => useSkillCheck({
    sessionId: 'sess-1',
    playerId:  'char-1',
    addLog,
    ...extra,
  }))
  return { addLog, ...view }
}


beforeEach(() => {
  vi.clearAllMocks()
})


describe('useSkillCheck', () => {
  it('初始 pendingCheck=null, checkRolling=false', () => {
    const { result } = createHook()
    expect(result.current.pendingCheck).toBeNull()
    expect(result.current.checkRolling).toBe(false)
  })

  it('rollPending 在没 pendingCheck 时直接返回 null', async () => {
    const { result } = createHook()
    let val
    await act(async () => { val = await result.current.rollPending() })
    expect(val).toBeNull()
    expect(rollDice3D).not.toHaveBeenCalled()
    expect(gameApi.skillCheck).not.toHaveBeenCalled()
  })

  it('rollPending 走完成功流程：调 API、写 log、返回 autoMsg', async () => {
    rollDice3D.mockResolvedValue({ total: 17 })
    gameApi.skillCheck.mockResolvedValue({
      d20: 17, modifier: 4, total: 21, success: true, proficient: true,
    })

    const { result, addLog } = createHook()
    act(() => { result.current.setPendingCheck({ check_type: '运动', dc: 15, context: '推开门' }) })

    let autoMsg
    await act(async () => { autoMsg = await result.current.rollPending() })

    // gameApi 用 hook 传入的参数被调
    expect(gameApi.skillCheck).toHaveBeenCalledWith({
      session_id:   'sess-1',
      character_id: 'char-1',
      skill:        '运动',
      dc:           15,
      d20_value:    17,
      second_d20_value: null,
    })
    // 写了一条 dice log
    expect(addLog).toHaveBeenCalledWith(
      'dice',
      expect.stringContaining('成功'),
      'dice',
      expect.objectContaining({ dice_result: expect.any(Object) }),
    )
    // 返回 autoMsg 含 context
    expect(autoMsg).toContain('运动检定 成功')
    expect(autoMsg).toContain('推开门')
    // pending 清空、rolling 复位
    expect(result.current.pendingCheck).toBeNull()
    expect(result.current.checkRolling).toBe(false)
  })

  it('rollPending 开启 Lucky 时额外掷 d20 并提交消费字段', async () => {
    const onLuckySpent = vi.fn()
    rollDice3D
      .mockResolvedValueOnce({ total: 2, rolls: [2] })
      .mockResolvedValueOnce({ total: 18, rolls: [18] })
    gameApi.skillCheck.mockResolvedValue({
      d20: 18,
      modifier: 4,
      total: 22,
      success: true,
      proficient: true,
      lucky: {
        spent: true,
        d20_before: 2,
        d20_after: 18,
        lucky_points_remaining: 0,
      },
    })

    const { result, addLog } = createHook({
      player: { class_resources: { lucky_points_remaining: 1 } },
      onLuckySpent,
    })
    act(() => { result.current.setPendingCheck({ check_type: '运动', dc: 15, use_lucky: true }) })

    await act(async () => { await result.current.rollPending() })

    expect(rollDice3D).toHaveBeenNthCalledWith(1, 20, 1)
    expect(rollDice3D).toHaveBeenNthCalledWith(2, 20)
    expect(gameApi.skillCheck).toHaveBeenCalledWith({
      session_id:   'sess-1',
      character_id: 'char-1',
      skill:        '运动',
      dc:           15,
      d20_value:    2,
      second_d20_value: null,
      use_lucky: true,
      lucky_d20_value: 18,
    })
    expect(onLuckySpent).toHaveBeenCalledWith(0)
    expect(addLog).toHaveBeenCalledWith(
      'dice',
      expect.stringContaining('Lucky 2->18'),
      'dice',
      expect.objectContaining({ dice_result: expect.any(Object) }),
    )
  })

  it('自然 20：触发 crit 音效', async () => {
    rollDice3D.mockResolvedValue({ total: 20 })
    gameApi.skillCheck.mockResolvedValue({
      d20: 20, modifier: 2, total: 22, success: true, proficient: false,
    })
    const { result } = createHook()
    act(() => { result.current.setPendingCheck({ check_type: '感知', dc: 12 }) })
    await act(async () => { await result.current.rollPending() })
    expect(JuiceAudio.crit).toHaveBeenCalled()
  })

  it('rollPending 在日志里显示服务端判定的优势/劣势', async () => {
    rollDice3D.mockResolvedValue({ total: 9 })
    gameApi.skillCheck.mockResolvedValue({
      d20: 9,
      modifier: 4,
      total: 13,
      success: false,
      proficient: true,
      disadvantage: true,
      advantage: false,
    })

    const { result, addLog } = createHook()
    act(() => { result.current.setPendingCheck({ check_type: '运动', dc: 15 }) })
    await act(async () => { await result.current.rollPending() })

    expect(addLog).toHaveBeenCalledWith(
      'dice',
      expect.stringContaining('[劣势]'),
      'dice',
      expect.objectContaining({ dice_result: expect.any(Object) }),
    )
  })

  it('rollPending 因玩家力竭投 2d20 并把两颗骰子交给后端取低', async () => {
    rollDice3D.mockResolvedValue({ total: 19, rolls: [15, 4] })
    gameApi.skillCheck.mockResolvedValue({
      d20: 4,
      other_roll: 15,
      modifier: 4,
      total: 8,
      success: false,
      proficient: true,
      disadvantage: true,
      advantage: false,
    })

    const { result, addLog } = createHook({
      player: { condition_durations: { exhaustion_level: 1 } },
    })
    act(() => { result.current.setPendingCheck({ check_type: '运动', dc: 15 }) })
    await act(async () => { await result.current.rollPending() })

    expect(rollDice3D).toHaveBeenCalledWith(20, 2)
    expect(gameApi.skillCheck).toHaveBeenCalledWith({
      session_id:   'sess-1',
      character_id: 'char-1',
      skill:        '运动',
      dc:           15,
      d20_value:    15,
      second_d20_value: 4,
    })
    expect(addLog).toHaveBeenCalledWith(
      'dice',
      expect.stringContaining('d20=4/15'),
      'dice',
      expect.objectContaining({ dice_result: expect.any(Object) }),
    )
  })

  it('API 抛异常：autoMsg 返回 null，写 system log，pending 也被清', async () => {
    rollDice3D.mockResolvedValue({ total: 10 })
    gameApi.skillCheck.mockRejectedValue(new Error('网络错误'))

    const { result, addLog } = createHook()
    act(() => { result.current.setPendingCheck({ check_type: '隐匿', dc: 10 }) })

    let autoMsg
    await act(async () => { autoMsg = await result.current.rollPending() })

    expect(autoMsg).toBeNull()
    expect(addLog).toHaveBeenCalledWith('system', expect.stringContaining('检定失败'), 'system')
    expect(result.current.pendingCheck).toBeNull()
    expect(result.current.checkRolling).toBe(false)
  })
})
