/**
 * Combat 渲染冒烟测试：覆盖“首次 loading -> 战斗数据返回”这一跳。
 *
 * 这类场景能抓出条件 return 后再调用 hook 的问题；build 不会发现，
 * 但 React 运行时会报 hook 顺序变化并导致页面不可用。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const {
  combatFixture,
  sessionFixture,
  getCombatMock,
  getSessionMock,
  getSpellsMock,
  getSkillBarMock,
} = vi.hoisted(() => ({
  combatFixture: {
    round_number: 2,
    current_turn_index: 0,
    turn_order: [
      { character_id: 'char-1', name: 'Tester', is_player: true, initiative: 15 },
      { character_id: 'enemy-1', name: '训练假人', is_enemy: true, initiative: 8 },
    ],
    entities: {
      'char-1': {
        id: 'char-1',
        name: 'Tester',
        is_enemy: false,
        hp_current: 12,
        hp_max: 12,
        ac: 14,
        char_class: 'Wizard',
      },
      'enemy-1': {
        id: 'enemy-1',
        name: '训练假人',
        is_enemy: true,
        hp_current: 7,
        hp_max: 7,
        ac: 10,
      },
    },
    entity_positions: {
      'char-1': { x: 5, y: 5 },
      'enemy-1': { x: 7, y: 5 },
    },
    turn_states: {
      'char-1': {
        action_used: false,
        bonus_action_used: false,
        reaction_used: false,
        movement_used: 0,
        movement_max: 6,
      },
    },
    grid_data: {},
  },
  sessionFixture: {
    session_id: 'sess-1',
    player: {
      id: 'char-1',
      name: 'Tester',
      char_class: 'Wizard',
      level: 3,
      hp_current: 12,
      spell_slots: { '1st': 2 },
      known_spells: ['Magic Missile'],
      cantrips: ['Fire Bolt'],
      derived: {
        hp_max: 12,
        ac: 14,
        initiative: 2,
        spell_save_dc: 13,
        spell_slots_max: { '1st': 2 },
      },
    },
    logs: [],
  },
  getCombatMock: vi.fn(),
  getSessionMock: vi.fn(),
  getSpellsMock: vi.fn(),
  getSkillBarMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    getCombat: getCombatMock,
    getSession: getSessionMock,
    getSpells: getSpellsMock,
    getSkillBar: getSkillBarMock,
    predict: vi.fn().mockResolvedValue(null),
    endCombat: vi.fn().mockResolvedValue({}),
    endTurn: vi.fn().mockResolvedValue({}),
  },
  roomsApi: {
    get: vi.fn().mockRejectedValue(new Error('not multiplayer')),
  },
}))

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ connected: false, send: () => false }),
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  default: () => null,
  rollDice3D: vi.fn().mockResolvedValue({ total: 10, rolls: [10] }),
}))

vi.mock('../../juice', () => ({
  JuiceAudio: {
    turn: vi.fn(),
    crit: vi.fn(),
    miss: vi.fn(),
    hit: vi.fn(),
    hover: vi.fn(),
    click: vi.fn(),
  },
  shake: vi.fn(),
}))

import Combat from '../Combat'

describe('Combat render smoke', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getCombatMock.mockResolvedValue(combatFixture)
    getSessionMock.mockResolvedValue(sessionFixture)
    getSpellsMock.mockResolvedValue([])
    getSkillBarMock.mockResolvedValue({ bar: [] })
  })

  afterEach(() => {
    cleanup()
  })

  it('能从加载态切到战斗 HUD，且不触发 hook 顺序错误', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText(/结束回合/)

    const errors = errSpy.mock.calls
      .map(c => c.join(' '))
      .filter(s => /Rendered more hooks|change in the order of Hooks|ReferenceError|Cannot access/.test(s))
    expect(errors).toEqual([])

    errSpy.mockRestore()
  })
})
