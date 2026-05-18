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
import { render, cleanup, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

// ─── 把所有外部副作用模块 mock 到最小可用 ───────────────────

const {
  sessionFixture,
  actionMock,
  getSessionMock,
  roomsGetMock,
  submitGroupActionMock,
  joinGroupMock,
  setGroupReadinessMock,
} = vi.hoisted(() => ({
  sessionFixture: {
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
  },
  actionMock: vi.fn(),
  getSessionMock: vi.fn(),
  roomsGetMock: vi.fn(),
  submitGroupActionMock: vi.fn(),
  joinGroupMock: vi.fn(),
  setGroupReadinessMock: vi.fn(),
}))

vi.mock('../../api/game', () => ({
  gameApi: {
    getSession: getSessionMock,
    action:     actionMock,
    actionStream: actionMock,
    skillCheck: vi.fn(),
    rest:       vi.fn(),
    saveCheckpoint:  vi.fn(),
    getCheckpoint:   vi.fn(),
    generateJournal: vi.fn(),
  },
}))

vi.mock('../../api/characters', () => ({
  charactersApi: { prepareSpells: vi.fn() },
}))

vi.mock('../../api/rooms', () => ({
  roomsApi: {
    get: roomsGetMock,
    submitGroupAction: submitGroupActionMock,
    joinGroup: joinGroupMock,
    setGroupReadiness: setGroupReadinessMock,
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
    localStorage.setItem('user', JSON.stringify({ user_id: 'me', username: 'me', display_name: '我' }))
    getSessionMock.mockResolvedValue(sessionFixture)
    roomsGetMock.mockRejectedValue(new Error('not multiplayer'))
    submitGroupActionMock.mockResolvedValue({})
    joinGroupMock.mockResolvedValue({})
    setGroupReadinessMock.mockResolvedValue({})
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

  it('点击带 skill_check 的选项时进入前端检定流程', async () => {
    getSessionMock.mockResolvedValue({
      ...sessionFixture,
      game_state: {
        last_turn: {
          last_actor_user_id: null,
          player_choices: [{
            text: '仔细辨认暗纹',
            skill_check: true,
            tags: [{ kind: 'perception', label: '察觉', dc: 12 }],
          }],
        },
      },
      player: {
        id: 'char-1',
        name: 'Tester',
        char_class: 'Wizard',
        hp_current: 10,
        derived: {
          hp_max: 10,
          proficiency_bonus: 2,
          ability_modifiers: { wis: 1 },
        },
        proficient_skills: [],
      },
    })

    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByRole('button', { name: /仔细辨认暗纹/ })
    fireEvent.click(screen.getByRole('button', { name: /仔细辨认暗纹/ }))

    await waitFor(() => {
      expect(screen.getByText(/察觉检定 · DC 12/)).toBeInTheDocument()
    })

    expect(errSpy.mock.calls.map(c => c.join(' ')).join('\n')).not.toMatch(/KIND_TO_SKILL_ZH|ReferenceError/)
    errSpy.mockRestore()
    cleanup()
  })

  it('点击 DM 生成的普通选项时带 ai_generated_choice 来源', async () => {
    actionMock.mockResolvedValue({
      type: 'exploration',
      narrative: '你靠近墙面，符文在微光里泛起冷色。',
      companion_reactions: '',
      dice_display: [],
      player_choices: [],
      needs_check: { required: false },
      combat_triggered: false,
      combat_ended: false,
    })
    getSessionMock.mockResolvedValue({
      ...sessionFixture,
      game_state: {
        last_turn: {
          last_actor_user_id: null,
          player_choices: [{
            text: '伸手触碰低处的符文',
            tags: [],
          }],
        },
      },
      player: {
        id: 'char-1',
        name: 'Tester',
        char_class: 'Wizard',
        hp_current: 10,
        derived: {
          hp_max: 10,
          proficiency_bonus: 2,
          ability_modifiers: { int: 3 },
        },
        proficient_skills: [],
      },
    })

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByRole('button', { name: /伸手触碰低处的符文/ })
    fireEvent.click(screen.getByRole('button', { name: /伸手触碰低处的符文/ }))

    await waitFor(() => {
      expect(actionMock).toHaveBeenCalledWith({
        session_id: 'sess-1',
        action_text: '伸手触碰低处的符文',
        action_source: 'ai_generated_choice',
      }, expect.objectContaining({
        onNarrativeDelta: expect.any(Function),
      }))
    })

    cleanup()
  })

  it('多人当前发言者提交时只发送主行动，分队聚合交给后端', async () => {
    actionMock.mockResolvedValue({
      type: 'exploration',
      narrative: 'DM 汇总了分队行动。',
      companion_reactions: '',
      dice_display: [],
      player_choices: [],
      needs_check: { required: false },
      combat_triggered: false,
      combat_ended: false,
    })
    roomsGetMock.mockResolvedValue({
      session_id: 'sess-1',
      is_multiplayer: true,
      room_code: '234567',
      current_speaker_user_id: 'me',
      active_group_id: 'alley',
      members: [
        { user_id: 'me', display_name: '我', character_id: 'char-1', is_online: true },
        { user_id: 'u2', display_name: '队友', character_id: 'char-2', is_online: true },
      ],
      party_groups: [
        { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me', 'u2'] },
      ],
      pending_actions_by_group: {
        alley: [{ user_id: 'u2', display_name: '队友', text: '我检查仓库门锁。' }],
      },
      group_readiness: {
        alley: { me: 'drafting', u2: 'ready' },
      },
    })
    setGroupReadinessMock.mockResolvedValue({
      session_id: 'sess-1',
      is_multiplayer: true,
      room_code: '234567',
      current_speaker_user_id: 'me',
      active_group_id: 'alley',
      members: [
        { user_id: 'me', display_name: '我', character_id: 'char-1', is_online: true },
        { user_id: 'u2', display_name: '队友', character_id: 'char-2', is_online: true },
      ],
      party_groups: [
        { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me', 'u2'] },
      ],
      pending_actions_by_group: {
        alley: [{ user_id: 'u2', display_name: '队友', text: '我检查仓库门锁。' }],
      },
      group_readiness: {
        alley: { me: 'ready', u2: 'ready' },
      },
    })
    getSessionMock.mockResolvedValue({
      ...sessionFixture,
      is_multiplayer: true,
      player: {
        id: 'char-1',
        name: 'Tester',
        char_class: 'Wizard',
        hp_current: 10,
        derived: { hp_max: 10, proficiency_bonus: 2, ability_modifiers: { int: 3 } },
        proficient_skills: [],
      },
    })

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText(/你是当前发言者 · DM 会汇总本分队 1 条意图/)
    expect(screen.getByText(/队友 · 已确认/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /我已确认/ }))
    await waitFor(() => {
      expect(setGroupReadinessMock).toHaveBeenCalledWith('sess-1', 'alley', 'ready')
    })

    fireEvent.change(screen.getByPlaceholderText(/描述你的行动/), {
      target: { value: '我撬开后门。' },
    })
    fireEvent.click(screen.getByRole('button', { name: /发送/ }))

    await waitFor(() => {
      expect(actionMock).toHaveBeenCalledWith({
        session_id: 'sess-1',
        action_text: '我撬开后门。',
        action_source: 'human_input',
      }, expect.objectContaining({
        onNarrativeDelta: expect.any(Function),
      }))
    })
    const payload = actionMock.mock.calls[0][0]
    expect(payload.action_text).not.toContain('队友意图')

    cleanup()
  })
})
