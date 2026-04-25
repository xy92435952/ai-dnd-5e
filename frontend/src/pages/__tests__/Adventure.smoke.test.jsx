/**
 * Adventure 渲染冒烟测试 —— 抓 hook 顺序错乱（TDZ ReferenceError）这类
 * **build 通过但 runtime 直接整页白屏**的灾难性 bug。
 *
 * 不验证业务正确性，只断言：组件能首次挂载且不抛任何错。
 * vitest 默认会让 console.error 不构成失败，所以这里手动 spy 它。
 *
 * 教训：Adventure.jsx 重构时如果把 useCallback 的 deps 数组里塞了
 * 某个还在 TDZ 的 const，render 阶段直接 ReferenceError —— 这种 bug
 * eslint 抓不到、build 抓不到、单测试单个 hook 也抓不到。只有"实际尝试
 * mount 整个组件"才能发现。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

// ─── 把所有外部副作用模块 mock 到最小可用 ───────────────────

vi.mock('../../api/client', () => ({
  gameApi: {
    getSession: vi.fn().mockResolvedValue({
      session_id:    'sess-1',
      save_name:     'Test',
      module_id:     'm1',
      module_name:   'Test Module',
      current_scene: '测试场景',
      combat_active: false,
      game_state:    {},
      player:        null,
      companions:    [],
      logs:          [],
      campaign_state: {},
      is_multiplayer: false,
    }),
    action:     vi.fn(),
    skillCheck: vi.fn(),
    rest:       vi.fn(),
    saveCheckpoint:  vi.fn(),
    getCheckpoint:   vi.fn(),
    generateJournal: vi.fn(),
  },
  charactersApi: { prepareSpells: vi.fn() },
  roomsApi: {
    // 单人模式：拉房间时直接 reject（Adventure 会忽略）
    get: vi.fn().mockRejectedValue(new Error('not multiplayer')),
  },
}))

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ connected: false, send: () => false }),
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  default:    () => null,
  rollDice3D: vi.fn().mockResolvedValue({ total: 10 }),
}))

vi.mock('../../juice', () => ({
  JuiceAudio: { turn: vi.fn(), crit: vi.fn(), miss: vi.fn(), unlock: vi.fn(), click: vi.fn() },
  shake:      vi.fn(),
}))

import Adventure from '../Adventure'


describe('Adventure render smoke', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('能挂载且不抛 TDZ / hook 顺序错误', () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )).not.toThrow()

    // React 把 render 错误转成 console.error。如果 hook 顺序错或 TDZ
    // ReferenceError，会以 "The above error occurred in the <Adventure>"
    // 形式出现，这里检测一下。
    const errors = errSpy.mock.calls
      .map(c => c.join(' '))
      .filter(s => /ReferenceError|Cannot access|TypeError/.test(s))
    expect(errors).toEqual([])

    errSpy.mockRestore()
    cleanup()
  })
})
