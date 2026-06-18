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
import { render, cleanup, screen, waitFor, fireEvent, act, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

// ─── 把所有外部副作用模块 mock 到最小可用 ───────────────────

const {
  sessionFixture,
  actionMock,
  aiTakeoverMock,
  selectEncounterTemplateMock,
  skillCheckMock,
  generateJournalMock,
  rollDice3DMock,
  getSessionMock,
  roomsGetMock,
  wsConnectedMock,
  wsSendMock,
  wsEventHandlerRef,
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
  aiTakeoverMock: vi.fn(),
  selectEncounterTemplateMock: vi.fn(),
  skillCheckMock: vi.fn(),
  generateJournalMock: vi.fn(),
  rollDice3DMock: vi.fn(),
  getSessionMock: vi.fn(),
  roomsGetMock: vi.fn(),
  wsConnectedMock: vi.fn(),
  wsSendMock: vi.fn(),
  wsEventHandlerRef: { current: null },
  submitGroupActionMock: vi.fn(),
  joinGroupMock: vi.fn(),
  setGroupReadinessMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    getSession: getSessionMock,
    action:     actionMock,
    aiTakeover: aiTakeoverMock,
    selectEncounterTemplate: selectEncounterTemplateMock,
    skillCheck: skillCheckMock,
    rest:       vi.fn(),
    saveCheckpoint:  vi.fn(),
    getCheckpoint:   vi.fn(),
    generateJournal: generateJournalMock,
  },
  charactersApi: { prepareSpells: vi.fn() },
  roomsApi: {
    get: roomsGetMock,
    submitGroupAction: submitGroupActionMock,
    joinGroup: joinGroupMock,
    setGroupReadiness: setGroupReadinessMock,
  },
}))

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: (_sessionId, onEvent) => {
    wsEventHandlerRef.current = onEvent
    return { connected: wsConnectedMock(), send: wsSendMock }
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  default:    () => null,
  rollDice3D: rollDice3DMock,
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
    wsEventHandlerRef.current = null
    wsConnectedMock.mockReturnValue(false)
    wsSendMock.mockReturnValue(false)
    roomsGetMock.mockRejectedValue(new Error('not multiplayer'))
    submitGroupActionMock.mockResolvedValue({})
    joinGroupMock.mockResolvedValue({})
    setGroupReadinessMock.mockResolvedValue({})
    selectEncounterTemplateMock.mockResolvedValue({
      template: { id: 'enc-yard', name: 'Construct Patrol' },
      location_graph: {},
    })
    rollDice3DMock.mockResolvedValue({ total: 10, rolls: [10] })
    skillCheckMock.mockResolvedValue({
      d20: 10,
      modifier: 1,
      total: 11,
      success: false,
      proficient: false,
    })
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

  it('单人 Adventure 不探测多人 room 接口', async () => {
    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledWith('sess-1')
    })
    expect(roomsGetMock).not.toHaveBeenCalled()

    cleanup()
  })

  it('clears a stale exploration reaction prompt after multiplayer reconnect refresh', async () => {
    const pendingPrompt = {
      type: 'feather_fall',
      reactor_character_id: 'char-1',
      reactor_character_name: 'Mara Quickstep',
      target_character_id: 'char-2',
      target_character_name: 'Smoke Sentinel',
      trap_name: 'Gatehouse drop shaft',
      damage_prevented: 6,
      available_reactions: [{
        type: 'feather_fall',
        slot_level: '1st',
        damage_prevented: 6,
      }],
      options: [{ type: 'feather_fall', label: 'Cast Feather Fall' }],
      can_decline: true,
    }
    const roomSnapshot = {
      session_id: 'sess-1',
      is_multiplayer: true,
      room_code: '234567',
      current_speaker_user_id: 'me',
      active_group_id: 'main',
      members: [
        { user_id: 'me', display_name: 'Me', character_id: 'char-1', is_online: true },
      ],
      party_groups: [{ id: 'main', name: 'Main', location: 'Gatehouse', member_user_ids: ['me'] }],
      pending_actions_by_group: { main: [] },
      group_readiness: { main: {} },
    }
    const baseMultiplayerSession = {
      ...sessionFixture,
      is_multiplayer: true,
      player: {
        id: 'char-1',
        name: 'Mara Quickstep',
        char_class: 'Wizard',
        hp_current: 10,
        derived: { hp_max: 10, proficiency_bonus: 2, ability_modifiers: { int: 3 } },
        proficient_skills: [],
      },
      companions: [],
    }
    getSessionMock
      .mockResolvedValueOnce({
        ...baseMultiplayerSession,
        game_state: { pending_exploration_reaction: pendingPrompt },
      })
      .mockResolvedValueOnce({
        ...baseMultiplayerSession,
        game_state: {},
      })
    roomsGetMock.mockResolvedValue(roomSnapshot)
    wsConnectedMock.mockReturnValue(false)

    const view = render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByRole('dialog', { name: 'Exploration reaction prompt' })).toBeInTheDocument()

    wsConnectedMock.mockReturnValue(true)
    view.rerender(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledTimes(2)
    })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Exploration reaction prompt' })).not.toBeInTheDocument()
    })

    cleanup()
  })

  it('clears a stale exploration reaction prompt after dm_responded refresh', async () => {
    const pendingPrompt = {
      type: 'feather_fall',
      reactor_character_id: 'char-1',
      reactor_character_name: 'Mara Quickstep',
      target_character_id: 'char-2',
      target_character_name: 'Smoke Sentinel',
      trap_name: 'Gatehouse drop shaft',
      damage_prevented: 6,
      available_reactions: [{
        type: 'feather_fall',
        slot_level: '1st',
        damage_prevented: 6,
      }],
      options: [{ type: 'feather_fall', label: 'Cast Feather Fall' }],
      can_decline: true,
    }
    const roomSnapshot = {
      session_id: 'sess-1',
      is_multiplayer: true,
      room_code: '234567',
      current_speaker_user_id: 'me',
      active_group_id: 'main',
      members: [
        { user_id: 'me', display_name: 'Me', character_id: 'char-1', is_online: true },
        { user_id: 'u2', display_name: 'Ally', character_id: 'char-2', is_online: true },
      ],
      party_groups: [{ id: 'main', name: 'Main', location: 'Gatehouse', member_user_ids: ['me', 'u2'] }],
      pending_actions_by_group: { main: [] },
      group_readiness: { main: {} },
    }
    const baseMultiplayerSession = {
      ...sessionFixture,
      is_multiplayer: true,
      player: {
        id: 'char-1',
        name: 'Mara Quickstep',
        char_class: 'Wizard',
        hp_current: 10,
        derived: { hp_max: 10, proficiency_bonus: 2, ability_modifiers: { int: 3 } },
        proficient_skills: [],
      },
      companions: [],
    }
    getSessionMock
      .mockResolvedValueOnce({
        ...baseMultiplayerSession,
        game_state: { pending_exploration_reaction: pendingPrompt },
      })
      .mockResolvedValueOnce({
        ...baseMultiplayerSession,
        game_state: {},
      })
    roomsGetMock.mockResolvedValue(roomSnapshot)
    wsConnectedMock.mockReturnValue(true)

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByRole('dialog', { name: 'Exploration reaction prompt' })).toBeInTheDocument()
    await waitFor(() => {
      expect(wsEventHandlerRef.current).toEqual(expect.any(Function))
    })

    await act(async () => {
      wsEventHandlerRef.current({
        type: 'dm_responded',
        by_user_id: 'u2',
        action_type: 'exploration',
        narrative: 'The table sees the resolved fall.',
        companion_reactions: '',
        dice_display: [],
        combat_triggered: false,
        combat_ended: false,
      })
    })

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalledTimes(2)
    })
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Exploration reaction prompt' })).not.toBeInTheDocument()
    })

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

  it('技能检定成功后把结果和原始选择作为系统行动回传给 DM', async () => {
    rollDice3DMock.mockResolvedValue({ total: 18, rolls: [18] })
    skillCheckMock.mockResolvedValue({
      d20: 18,
      modifier: 2,
      total: 20,
      success: true,
      proficient: true,
    })
    actionMock.mockResolvedValue({
      type: 'exploration',
      narrative: '你辨认出暗纹是古老的封印符号。',
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
          ability_modifiers: { wis: 2 },
        },
        proficient_skills: ['察觉'],
      },
    })

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByRole('button', { name: /仔细辨认暗纹/ })
    fireEvent.click(screen.getByRole('button', { name: /仔细辨认暗纹/ }))
    fireEvent.click(await screen.findByRole('button', { name: /投掷 d20/ }))

    await waitFor(() => {
      expect(skillCheckMock).toHaveBeenCalledWith({
        session_id: 'sess-1',
        character_id: 'char-1',
        skill: '察觉',
        dc: 12,
        d20_value: 18,
        second_d20_value: null,
      })
    })
    await waitFor(() => {
      expect(actionMock).toHaveBeenCalledWith(expect.objectContaining({
        session_id: 'sess-1',
        action_source: 'system_action',
        action_text: expect.stringContaining('察觉检定 成功'),
      }))
    }, { timeout: 1500 })
    const payload = actionMock.mock.calls[0][0]
    expect(payload.action_text).toContain('20 vs DC12')
    expect(payload.action_text).toContain('我的行动："仔细辨认暗纹"')

    cleanup()
  })

  it('技能检定失败后也会把失败结果作为系统行动回传给 DM', async () => {
    rollDice3DMock.mockResolvedValue({ total: 4, rolls: [4] })
    skillCheckMock.mockResolvedValue({
      d20: 4,
      modifier: 1,
      total: 5,
      success: false,
      proficient: false,
    })
    actionMock.mockResolvedValue({
      type: 'exploration',
      narrative: '暗纹像是普通磨损，你没能看出更多。',
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
            text: '翻找潮湿的账本',
            skill_check: true,
            check_type: '调查',
            dc: 14,
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
          ability_modifiers: { int: 1 },
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

    await screen.findByRole('button', { name: /翻找潮湿的账本/ })
    fireEvent.click(screen.getByRole('button', { name: /翻找潮湿的账本/ }))
    fireEvent.click(await screen.findByRole('button', { name: /投掷 d20/ }))

    await waitFor(() => {
      expect(actionMock).toHaveBeenCalledWith(expect.objectContaining({
        session_id: 'sess-1',
        action_source: 'system_action',
        action_text: expect.stringContaining('调查检定 失败'),
      }))
    }, { timeout: 1500 })
    const payload = actionMock.mock.calls[0][0]
    expect(payload.action_text).toContain('5 vs DC14')
    expect(payload.action_text).toContain('我的行动："翻找潮湿的账本"')

    cleanup()
  })

  it('刷新 Adventure 后恢复单人日志、选项和待检定状态', async () => {
    getSessionMock.mockResolvedValue({
      ...sessionFixture,
      logs: [
        { id: 'log-1', role: 'dm', log_type: 'narrative', content: '石门后传来低沉回声。' },
        { id: 'log-2', role: 'player', log_type: 'narrative', content: '我靠近石门。' },
      ],
      game_state: {
        last_turn: {
          last_actor_user_id: null,
          player_choices: [
            { text: '继续聆听门后的声音', tags: [] },
          ],
          needs_check: {
            required: true,
            check_type: '察觉',
            dc: 13,
            context: '辨认门后声音',
          },
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

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('石门后传来低沉回声。')).toBeInTheDocument()
    expect(screen.getByText(/我靠近石门。/)).toBeInTheDocument()
    expect(screen.getByText(/察觉检定 · DC 13/)).toBeInTheDocument()
    expect(screen.getByText('辨认门后声音')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /继续聆听门后的声音/ })).not.toBeInTheDocument()

    cleanup()
  })

  it('刷新多人 Adventure 后恢复房间发言权和分队待处理意图', async () => {
    wsConnectedMock.mockReturnValue(true)
    roomsGetMock.mockResolvedValue({
      session_id: 'sess-1',
      is_multiplayer: true,
      room_code: '234567',
      current_speaker_user_id: 'other',
      active_group_id: 'alley',
      members: [
        { user_id: 'me', display_name: '我', character_id: 'char-1', character_name: 'Tester', is_online: true },
        { user_id: 'other', display_name: '队友', character_id: 'char-2', character_name: 'Ally', is_online: true },
      ],
      party_groups: [
        { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['me', 'other'] },
      ],
      pending_actions_by_group: {
        alley: [{ user_id: 'me', display_name: '我', text: '我检查仓库门锁。' }],
      },
      group_readiness: {
        alley: { me: 'ready', other: 'drafting' },
      },
    })
    getSessionMock.mockResolvedValue({
      ...sessionFixture,
      is_multiplayer: true,
      game_state: {
        last_turn: {
          last_actor_user_id: 'other',
          player_choices: [{ text: '队友可见的选择', tags: [] }],
        },
      },
      player: {
        id: 'char-1',
        name: 'Tester',
        char_class: 'Wizard',
        hp_current: 10,
        derived: { hp_max: 10, proficiency_bonus: 2, ability_modifiers: { int: 3 } },
        proficient_skills: [],
      },
      logs: [
        { id: 'log-1', role: 'dm', log_type: 'narrative', content: '分队停在后巷。' },
      ],
    })

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText(/等待 队友 发言/)).toBeInTheDocument()
    expect(screen.getByText('同步在线')).toBeInTheDocument()
    expect(screen.getByTitle('当前发言者：队友，角色：Ally')).toHaveTextContent('发言 队友 / Ally · 在线')
    expect(screen.getAllByText('后巷组').length).toBeGreaterThan(0)
    expect(screen.getByText(/我检查仓库门锁。/)).toBeInTheDocument()
    expect(screen.getByText(/我 · 已确认/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/等待发言权/)).toBeDisabled()
    expect(screen.queryByRole('button', { name: /队友可见的选择/ })).not.toBeInTheDocument()

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
      expect(actionMock).toHaveBeenCalledWith(expect.objectContaining({
        session_id: 'sess-1',
        action_text: '伸手触碰低处的符文',
        action_source: 'ai_generated_choice',
      }))
    })

    cleanup()
  })

  it('多人当前发言者提交时只发送主行动，分队聚合交给后端', async () => {
    wsConnectedMock.mockReturnValue(true)
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
      expect(actionMock).toHaveBeenCalledWith(expect.objectContaining({
        session_id: 'sess-1',
        action_text: '我撬开后门。',
        action_source: 'human_input',
      }))
    })
    const payload = actionMock.mock.calls[0][0]
    expect(payload.idempotency_key).toEqual(expect.any(String))
    expect(payload.action_text).not.toContain('队友意图')

    cleanup()
  })

  it('triggers AI takeover for an offline multiplayer speaker and refreshes room state', async () => {
    wsConnectedMock.mockReturnValue(true)
    aiTakeoverMock.mockResolvedValue({
      narrative: 'The ally checks the locked door.',
      companion_reactions: '',
      dice_display: [],
      player_choices: [],
      needs_check: { required: false },
      combat_triggered: false,
      combat_ended: false,
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
      logs: [],
    })
    roomsGetMock
      .mockResolvedValueOnce({
        session_id: 'sess-1',
        is_multiplayer: true,
        room_code: '234567',
        current_speaker_user_id: 'u2',
        active_group_id: 'main',
        members: [
          { user_id: 'me', display_name: 'Me', character_id: 'char-1', is_online: true, seconds_since_seen: 0 },
          { user_id: 'u2', display_name: 'Ally', character_id: 'char-2', is_online: false, seconds_since_seen: 42 },
        ],
        party_groups: [{ id: 'main', name: 'Main', location: 'Hall', member_user_ids: ['me', 'u2'] }],
        pending_actions_by_group: { main: [] },
        group_readiness: { main: {} },
      })
      .mockResolvedValueOnce({
        session_id: 'sess-1',
        is_multiplayer: true,
        room_code: '234567',
        current_speaker_user_id: 'me',
        active_group_id: 'main',
        members: [
          { user_id: 'me', display_name: 'Me', character_id: 'char-1', is_online: true, seconds_since_seen: 0 },
          { user_id: 'u2', display_name: 'Ally', character_id: 'char-2', is_online: false, seconds_since_seen: 43 },
        ],
        party_groups: [{ id: 'main', name: 'Main', location: 'Hall', member_user_ids: ['me', 'u2'] }],
        pending_actions_by_group: { main: [] },
        group_readiness: { main: {} },
      })

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    const takeoverButton = await screen.findByRole('button', { name: /AI 代演/ })
    expect(takeoverButton).toBeEnabled()
    fireEvent.click(takeoverButton)

    await waitFor(() => {
      expect(aiTakeoverMock).toHaveBeenCalledWith('sess-1')
    })
    await waitFor(() => {
      expect(roomsGetMock).toHaveBeenCalledTimes(2)
    })
    expect(getSessionMock).toHaveBeenCalledTimes(1)

    cleanup()
  })

  it('blocks AI takeover while local multiplayer sync is disconnected', async () => {
    wsConnectedMock.mockReturnValue(false)
    aiTakeoverMock.mockResolvedValue({
      narrative: '这段不应该出现。',
      companion_reactions: '',
      dice_display: [],
      player_choices: [],
      needs_check: { required: false },
      combat_triggered: false,
      combat_ended: false,
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
      logs: [],
    })
    roomsGetMock.mockResolvedValue({
      session_id: 'sess-1',
      is_multiplayer: true,
      room_code: '234567',
      current_speaker_user_id: 'u2',
      active_group_id: 'main',
      members: [
        { user_id: 'me', display_name: 'Me', character_id: 'char-1', is_online: true, seconds_since_seen: 0 },
        { user_id: 'u2', display_name: 'Ally', character_id: 'char-2', is_online: false, seconds_since_seen: 42 },
      ],
      party_groups: [{ id: 'main', name: 'Main', location: 'Hall', member_user_ids: ['me', 'u2'] }],
      pending_actions_by_group: { main: [] },
      group_readiness: { main: {} },
    })

    render(
      <MemoryRouter initialEntries={['/adventure/sess-1']}>
        <Routes>
          <Route path="/adventure/:sessionId" element={<Adventure />} />
        </Routes>
      </MemoryRouter>
    )

    const takeoverButton = await screen.findByRole('button', { name: /AI 代演/ })
    expect(takeoverButton).toBeDisabled()
    expect(takeoverButton).toHaveAttribute('title', '房间正在重新同步，请恢复连接后再使用 AI 代演')
    fireEvent.click(takeoverButton)

    expect(aiTakeoverMock).not.toHaveBeenCalled()

    cleanup()
  })

  it('多人同步断开时地图可读但禁止切换遭遇模板', async () => {
    wsConnectedMock.mockReturnValue(false)
    roomsGetMock.mockResolvedValue({
      session_id: 'sess-1',
      is_multiplayer: true,
      room_code: '234567',
      current_speaker_user_id: 'me',
      active_group_id: 'main',
      members: [
        { user_id: 'me', display_name: '我', character_id: 'char-1', is_online: true },
      ],
      party_groups: [{ id: 'main', name: '主队', location: '训练场', member_user_ids: ['me'] }],
      pending_actions_by_group: { main: [] },
      group_readiness: { main: {} },
    })
    getSessionMock.mockResolvedValue({
      ...sessionFixture,
      is_multiplayer: true,
      game_state: {
        location_graph: {
          current_location_id: 'yard',
          nodes: [
            { id: 'yard', name: 'Training Yard', visited: true, encounter_template_ids: ['enc-yard'] },
          ],
          encounter_templates: [{
            id: 'enc-yard',
            location_id: 'yard',
            status: 'available',
            public: true,
            name: 'Construct Patrol',
            difficulty_hint: 'moderate',
            enemy_names: ['Clockwork Construct'],
          }],
        },
      },
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

    fireEvent.click(await screen.findByRole('button', { name: 'Map: Open mapped locations and encounter templates.' }))

    expect(await screen.findByRole('heading', { name: 'Map' })).toBeInTheDocument()
    expect(screen.getAllByText('Construct Patrol').length).toBeGreaterThan(0)
    const encounters = screen.getByLabelText('Selected encounter templates')
    expect(within(encounters).getByText('同步暂停')).toBeInTheDocument()
    expect(within(encounters).getAllByText('房间正在重新同步，请恢复连接后再选择遭遇。').length).toBeGreaterThanOrEqual(2)

    const selectButton = screen.getByRole('button', { name: 'Set active' })
    expect(selectButton).toBeDisabled()
    expect(selectButton).toHaveAttribute('title', '房间正在重新同步，请恢复连接后再选择遭遇。')
    fireEvent.click(selectButton)

    expect(selectEncounterTemplateMock).not.toHaveBeenCalled()

    cleanup()
  })

  it('多人同步断开时禁用发言入口并阻止行动提交', async () => {
    wsConnectedMock.mockReturnValue(false)
    actionMock.mockResolvedValue({
      type: 'exploration',
      narrative: '这段不应该出现。',
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
      active_group_id: 'main',
      members: [
        { user_id: 'me', display_name: '我', character_id: 'char-1', is_online: true },
      ],
      party_groups: [{ id: 'main', name: '主队', location: '大厅', member_user_ids: ['me'] }],
      pending_actions_by_group: { main: [] },
      group_readiness: { main: {} },
    })
    getSessionMock.mockResolvedValue({
      ...sessionFixture,
      is_multiplayer: true,
      game_state: {
        last_turn: {
          last_actor_user_id: null,
          player_choices: [{ text: '推开大厅门', tags: [] }],
        },
      },
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

    const input = await screen.findByPlaceholderText(/正在重新同步房间/)
    expect(input).toBeDisabled()
    const choice = screen.getByRole('button', { name: /推开大厅门/ })
    expect(choice).toBeDisabled()
    fireEvent.click(choice)

    expect(screen.getByRole('button', { name: /发送/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /跳过本轮/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /存档/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /休息/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /备法/ })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: /日志/ }))
    expect(await screen.findByText('冒险卷宗')).toBeInTheDocument()
    expect(generateJournalMock).not.toHaveBeenCalled()
    expect(actionMock).not.toHaveBeenCalled()
    expect(wsSendMock).not.toHaveBeenCalled()

    cleanup()
  })
})
