/**
 * useCombatTargeting 单元测试 — 瞄准 / 视觉模式集合状态。
 *
 * 这是纯客户端 UI 状态，没外部依赖，测试简单清晰。
 */
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCombatTargeting } from '../useCombatTargeting'


describe('useCombatTargeting', () => {
  it('初始所有状态都为关 / 空', () => {
    const { result } = renderHook(() => useCombatTargeting())
    expect(result.current.selectedTarget).toBeNull()
    expect(result.current.moveMode).toBe(false)
    expect(result.current.isRanged).toBe(false)
    expect(result.current.showThreat).toBe(false)
    expect(result.current.aoePreview).toBeNull()
    expect(result.current.aoeHover).toBeNull()
    expect(result.current.helpMode).toBe(false)
  })

  it('toggleMoveMode 切换 moveMode 并清掉 helpMode + selectedTarget', () => {
    const { result } = renderHook(() => useCombatTargeting())

    // 先把 helpMode 和 selectedTarget 弄上
    act(() => {
      result.current.setHelpMode(true)
      result.current.setSelectedTarget('enemy-1')
    })
    expect(result.current.helpMode).toBe(true)

    act(() => { result.current.toggleMoveMode() })
    expect(result.current.moveMode).toBe(true)
    expect(result.current.helpMode).toBe(false)
    expect(result.current.selectedTarget).toBeNull()

    // 再 toggle 关掉
    act(() => { result.current.toggleMoveMode() })
    expect(result.current.moveMode).toBe(false)
  })

  it('enterHelpMode 互斥地关闭 moveMode', () => {
    const { result } = renderHook(() => useCombatTargeting())
    act(() => { result.current.setMoveMode(true) })
    expect(result.current.moveMode).toBe(true)

    act(() => { result.current.enterHelpMode() })
    expect(result.current.helpMode).toBe(true)
    expect(result.current.moveMode).toBe(false)
  })

  it('clearTargeting 一键清空 moveMode / helpMode / selectedTarget', () => {
    const { result } = renderHook(() => useCombatTargeting())
    act(() => {
      result.current.setMoveMode(true)
      result.current.setHelpMode(true)
      result.current.setSelectedTarget('foe-1')
    })
    act(() => { result.current.clearTargeting() })
    expect(result.current.moveMode).toBe(false)
    expect(result.current.helpMode).toBe(false)
    expect(result.current.selectedTarget).toBeNull()
  })

  it('AoE 预览 set + clear', () => {
    const { result } = renderHook(() => useCombatTargeting())
    act(() => {
      result.current.setAoePreview({ radius: 3, spellName: 'fireball' })
      result.current.setAoeHover('5_4')
    })
    expect(result.current.aoePreview).toEqual({ radius: 3, spellName: 'fireball' })
    expect(result.current.aoeHover).toBe('5_4')

    act(() => { result.current.clearAoePreview() })
    expect(result.current.aoePreview).toBeNull()
    expect(result.current.aoeHover).toBeNull()
  })

  it('isRanged / showThreat 是独立开关，不被互斥逻辑影响', () => {
    const { result } = renderHook(() => useCombatTargeting())
    act(() => {
      result.current.setIsRanged(true)
      result.current.setShowThreat(true)
    })
    expect(result.current.isRanged).toBe(true)
    expect(result.current.showThreat).toBe(true)

    // 切换其他模式不应该清掉这两个
    act(() => { result.current.toggleMoveMode() })
    expect(result.current.isRanged).toBe(true)
    expect(result.current.showThreat).toBe(true)
  })
})
