/**
 * Combat 渲染冒烟测试：覆盖“首次 loading -> 战斗数据返回”这一跳。
 *
 * 这类场景能抓出条件 return 后再调用 hook 的问题；build 不会发现，
 * 但 React 运行时会报 hook 顺序变化并导致页面不可用。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const {
  combatFixture,
  sessionFixture,
  getCombatMock,
  getSessionMock,
  getSpellsMock,
  getSkillBarMock,
  roomsGetMock,
  attackRollMock,
  damageRollMock,
  moveMock,
  combatActionMock,
  endTurnMock,
  useItemMock,
  wsConnectedMock,
  wsSendMock,
  wsEvents,
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
      equipment: {
        gear: [
          { name: 'Healing Potion', zh: '治疗药水', consumable: true, cost: 50 },
        ],
      },
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
  roomsGetMock: vi.fn(),
  attackRollMock: vi.fn(),
  damageRollMock: vi.fn(),
  moveMock: vi.fn(),
  combatActionMock: vi.fn(),
  endTurnMock: vi.fn(),
  useItemMock: vi.fn(),
  wsConnectedMock: vi.fn(),
  wsSendMock: vi.fn(),
  wsEvents: { current: null },
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    getCombat: getCombatMock,
    getSession: getSessionMock,
    getSpells: getSpellsMock,
    getSkillBar: getSkillBarMock,
    predict: vi.fn().mockResolvedValue(null),
    endCombat: vi.fn().mockResolvedValue({}),
    endTurn: endTurnMock,
    attackRoll: attackRollMock,
    damageRoll: damageRollMock,
    move: moveMock,
    combatAction: combatActionMock,
  },
  charactersApi: {
    useItem: useItemMock,
  },
  roomsApi: {
    get: roomsGetMock,
  },
}))

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: (_sessionId, onEvent) => {
    wsEvents.current = onEvent
    return { connected: wsConnectedMock(), send: wsSendMock }
  },
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
    wsEvents.current = null
    wsConnectedMock.mockReturnValue(false)
    wsSendMock.mockReturnValue(false)
    getCombatMock.mockResolvedValue(combatFixture)
    getSessionMock.mockResolvedValue(sessionFixture)
    getSpellsMock.mockResolvedValue([])
    getSkillBarMock.mockResolvedValue({ bar: [] })
    roomsGetMock.mockRejectedValue(new Error('not multiplayer'))
    endTurnMock.mockResolvedValue({})
    attackRollMock.mockResolvedValue({
      d20: 10,
      attack_bonus: 5,
      attack_total: 15,
      target_ac: 10,
      hit: true,
      is_crit: false,
      is_fumble: false,
      target_name: '训练假人',
      attacker_name: 'Guest Hero',
      attacks_made: 1,
      attacks_max: 1,
      damage_dice: '1d8',
      pending_attack_id: 'pa-1',
      weapon_resource: {
        weapon: 'Longbow',
        resource_type: 'ammunition',
        consumed: true,
        ammo_remaining: 19,
      },
      turn_state: { action_used: true, attacks_made: 1, attacks_max: 1 },
    })
    damageRollMock.mockResolvedValue({
      target_id: 'enemy-1',
      target_new_hp: 2,
      damage_total: 5,
      total_damage: 5,
      narration: 'Guest Hero 命中训练假人',
      turn_state: { action_used: true, attacks_made: 1, attacks_max: 1 },
      combat_over: false,
    })
    moveMock.mockResolvedValue({
      entity_positions: combatFixture.entity_positions,
      turn_state: { movement_used: 1, movement_max: 6 },
    })
    combatActionMock.mockResolvedValue({
      action: 'help',
      turn_state: { action_used: true, movement_used: 0, movement_max: 6 },
    })
    useItemMock.mockResolvedValue({
      item: 'Healing Potion',
      heal_amount: 5,
      hp_after: 12,
      equipment: { gear: [] },
      turn_state: {
        action_used: true,
        bonus_action_used: false,
        reaction_used: false,
        movement_used: 0,
        movement_max: 6,
      },
    })
  })

  afterEach(() => {
    localStorage.removeItem('user')
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
    expect(roomsGetMock).not.toHaveBeenCalled()

    const errors = errSpy.mock.calls
      .map(c => c.join(' '))
      .filter(s => /Rendered more hooks|change in the order of Hooks|ReferenceError|Cannot access/.test(s))
    expect(errors).toEqual([])

    errSpy.mockRestore()
  })

  it('can open the player character sheet from combat', async () => {
    render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
          <Route path="/character/:characterId" element={<div>角色卡页面</div>} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText(/结束回合/)
    fireEvent.click(screen.getByRole('button', { name: /角色卡/ }))

    await waitFor(() => {
      expect(screen.getByText('角色卡页面')).toBeInTheDocument()
    })
  })

  it('returns to Adventure when combat has already ended before refresh completes', async () => {
    getCombatMock.mockRejectedValue(new Error('当前没有进行中的战斗'))

    render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
          <Route path="/adventure/:sessionId" element={<div>Adventure restored</div>} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText('Adventure restored')
    expect(getSessionMock).not.toHaveBeenCalled()
    expect(screen.queryByText(/鍔犺浇鎴樻枟/)).not.toBeInTheDocument()
  })

  it('can use a consumable directly from combat', async () => {
    render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText(/结束回合/)
    fireEvent.click(screen.getByRole('button', { name: /使用 治疗药水/ }))

    await waitFor(() => {
      expect(useItemMock).toHaveBeenCalledWith('char-1', 'Healing Potion', {
        session_id: 'sess-1',
        use_in_combat: true,
      })
      expect(screen.getByText(/治疗药水 恢复 5 HP/)).toBeInTheDocument()
    })
  })

  it('lets the active multiplayer owner end their combat turn', async () => {
    wsConnectedMock.mockReturnValue(true)
    const ownerCombat = {
      ...combatFixture,
      current_turn_index: 0,
      turn_order: [
        { character_id: 'guest-char', name: 'Guest Hero', is_player: true, initiative: 16 },
        { character_id: 'enemy-1', name: '训练假人', is_enemy: true, initiative: 8 },
      ],
      entities: {
        ...combatFixture.entities,
        'guest-char': {
          ...combatFixture.entities['char-1'],
          id: 'guest-char',
          name: 'Guest Hero',
        },
      },
      entity_positions: {
        ...combatFixture.entity_positions,
        'guest-char': { x: 5, y: 5 },
      },
      turn_states: {
        'guest-char': { action_used: false, movement_used: 0, movement_max: 6 },
      },
    }
    const ownerSession = {
      ...sessionFixture,
      is_multiplayer: true,
      player: {
        ...sessionFixture.player,
        id: 'guest-char',
        name: 'Guest Hero',
      },
    }
    const room = {
      is_multiplayer: true,
      session_id: 'sess-1',
      room_code: '234567',
      members: [
        { user_id: 'guest-user', display_name: 'Guest', character_id: 'guest-char', is_online: true },
      ],
    }

    localStorage.setItem('user', JSON.stringify({ user_id: 'guest-user', display_name: 'Guest' }))
    window.dispatchEvent(new Event('user-changed'))
    roomsGetMock.mockResolvedValue(room)
    getCombatMock.mockResolvedValue(ownerCombat)
    getSessionMock.mockResolvedValue(ownerSession)
    endTurnMock.mockResolvedValue({ next_turn_index: 1, round_number: 1 })

    render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
        </Routes>
      </MemoryRouter>
    )

    const endTurnButton = await screen.findByRole('button', { name: /结束回合/ })
    await waitFor(() => expect(endTurnButton).not.toBeDisabled())
    fireEvent.click(endTurnButton)

    await waitFor(() => {
      expect(endTurnMock).toHaveBeenCalledWith('sess-1', '2:0:guest-char')
    })
  })

  it('pauses multiplayer combat controls while websocket sync is unavailable', async () => {
    wsConnectedMock.mockReturnValue(false)
    const ownerCombat = {
      ...combatFixture,
      current_turn_index: 0,
      turn_order: [
        { character_id: 'guest-char', name: 'Guest Hero', is_player: true, initiative: 16 },
        { character_id: 'enemy-1', name: '训练假人', is_enemy: true, initiative: 8 },
      ],
      entities: {
        ...combatFixture.entities,
        'guest-char': {
          ...combatFixture.entities['char-1'],
          id: 'guest-char',
          name: 'Guest Hero',
        },
      },
      entity_positions: {
        ...combatFixture.entity_positions,
        'guest-char': { x: 5, y: 5 },
      },
      turn_states: {
        'guest-char': { action_used: false, movement_used: 0, movement_max: 6 },
      },
    }
    const ownerSession = {
      ...sessionFixture,
      is_multiplayer: true,
      player: {
        ...sessionFixture.player,
        id: 'guest-char',
        name: 'Guest Hero',
      },
    }
    const room = {
      is_multiplayer: true,
      session_id: 'sess-1',
      room_code: '234567',
      members: [
        { user_id: 'guest-user', display_name: 'Guest', character_id: 'guest-char', is_online: true },
      ],
    }

    localStorage.setItem('user', JSON.stringify({ user_id: 'guest-user', display_name: 'Guest' }))
    window.dispatchEvent(new Event('user-changed'))
    roomsGetMock.mockResolvedValue(room)
    getCombatMock.mockResolvedValue(ownerCombat)
    getSessionMock.mockResolvedValue(ownerSession)
    getSkillBarMock.mockResolvedValue({
      bar: [
        { k: 'atk', label: '攻击', glyph: 'A', cost: '动作', key: '1', kind: 'attack', available: true },
      ],
    })

    const { container } = render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText(/同步中 · 暂停战斗操作/)
    const syncButton = screen.getByRole('button', { name: /同步中/ })
    expect(syncButton).toBeDisabled()

    const enemyChip = container.querySelector('.unit-chip.enemy')
    expect(enemyChip).toBeTruthy()
    fireEvent.click(enemyChip)
    await waitFor(() => {
      expect(container.querySelector('.target-card')).toHaveTextContent(ownerCombat.entities['enemy-1'].name)
    })

    const attackSlot = container.querySelector('.slot-key.attack')
    expect(attackSlot).toBeTruthy()
    fireEvent.click(attackSlot)
    fireEvent.click(syncButton)

    expect(attackRollMock).not.toHaveBeenCalled()
    expect(endTurnMock).not.toHaveBeenCalled()
  })

  it('restores multiplayer combat turn, battlefield state, hp, and pending reaction after refresh', async () => {
    wsConnectedMock.mockReturnValue(true)
    const restoredCombat = {
      ...combatFixture,
      round_number: 4,
      current_turn_index: 1,
      turn_order: [
        { character_id: 'host-char', name: 'Host Hero', is_player: true, initiative: 18 },
        { character_id: 'guest-char', name: 'Guest Hero', is_player: true, initiative: 16 },
        { character_id: 'enemy-1', name: '训练假人', is_enemy: true, initiative: 8 },
      ],
      entities: {
        ...combatFixture.entities,
        'host-char': {
          id: 'host-char',
          name: 'Host Hero',
          is_enemy: false,
          hp_current: 12,
          hp_max: 12,
          ac: 16,
          char_class: 'Fighter',
        },
        'guest-char': {
          ...combatFixture.entities['char-1'],
          id: 'guest-char',
          name: 'Guest Hero',
          hp_current: 5,
          hp_max: 18,
          ac: 15,
          char_class: 'Wizard',
          derived: {
            hp_max: 18,
            ac: 15,
            initiative: 3,
            spell_save_dc: 14,
          },
        },
        'enemy-1': {
          ...combatFixture.entities['enemy-1'],
          hp_current: 2,
          hp_max: 10,
        },
      },
      entity_positions: {
        'host-char': { x: 9, y: 6 },
        'guest-char': { x: 10, y: 6 },
        'enemy-1': { x: 12, y: 6 },
      },
      turn_states: {
        'host-char': { action_used: false, movement_used: 0, movement_max: 6 },
        'guest-char': {
          action_used: true,
          bonus_action_used: false,
          reaction_used: false,
          movement_used: 3,
          movement_max: 6,
          pending_attack_reaction: {
            trigger: 'incoming_attack',
            attacker_id: 'enemy-1',
            attacker_name: '训练假人',
            target_id: 'guest-char',
            reactor_character_id: 'guest-char',
            reactor_name: 'Guest Hero',
            incoming_damage: 7,
            target_hp_before_damage: 5,
            attack_roll: 17,
            player_ac: 15,
            available_reactions: [
              { type: 'shield', name: 'Shield', cost: '1环法术位', damage_prevented: 7 },
            ],
          },
        },
      },
    }
    const restoredSession = {
      ...sessionFixture,
      is_multiplayer: true,
      player: {
        ...sessionFixture.player,
        id: 'guest-char',
        name: 'Guest Hero',
        hp_current: 5,
        hp_max: 18,
        char_class: 'Wizard',
        level: 3,
        spell_slots: { '1st': 1 },
        derived: {
          ...sessionFixture.player.derived,
          hp_max: 18,
          ac: 15,
          initiative: 3,
          spell_save_dc: 14,
        },
      },
      logs: [
        { id: 'combat-log-1', log_type: 'combat', role: 'system', content: '上一轮命中，等待反应。' },
      ],
    }
    const room = {
      is_multiplayer: true,
      session_id: 'sess-1',
      room_code: '234567',
      host_user_id: 'host-user',
      members: [
        { user_id: 'host-user', display_name: 'Host', character_id: 'host-char', is_online: true },
        { user_id: 'guest-user', display_name: 'Guest', character_id: 'guest-char', is_online: true },
      ],
    }

    localStorage.setItem('user', JSON.stringify({ user_id: 'guest-user', display_name: 'Guest' }))
    window.dispatchEvent(new Event('user-changed'))
    roomsGetMock.mockResolvedValue(room)
    getCombatMock.mockResolvedValue(restoredCombat)
    getSessionMock.mockResolvedValue(restoredSession)

    const { container } = render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText(/当前回合：Guest（Guest Hero）/)
    expect(screen.getAllByText('你的回合').length).toBeGreaterThan(0)
    expect(screen.getByText('R 4')).toBeInTheDocument()
    expect(screen.getByText('上一轮命中，等待反应。')).toBeInTheDocument()

    const portrait = container.querySelector('.hud-portrait')
    expect(portrait).toHaveTextContent('Guest Hero')
    expect(portrait).toHaveTextContent('5 / 18')
    expect(portrait).toHaveTextContent('移动 3/6')
    expect(container.querySelector('.action-pips .pip.action.used')).toBeTruthy()

    expect(container.querySelector('.iso-unit.player.active')).toBeTruthy()
    expect(container.querySelector('.iso-unit.enemy.low')).toBeTruthy()
    expect(container.querySelector('[data-grid-key="10_6"] [data-entity-id="guest-char"]')).toBeTruthy()
    expect(container.querySelector('[data-grid-key="12_6"] [data-entity-id="enemy-1"]')).toBeTruthy()

    const prompt = await screen.findByRole('dialog', { name: /反应触发/ })
    expect(prompt).toHaveTextContent('训练假人 的攻击造成 7 点待处理伤害')
    expect(prompt).toHaveTextContent('攻击 17 vs AC15')
    expect(prompt).toHaveTextContent('HP 5 -> 0')
    expect(prompt).toHaveTextContent('Shield')
    expect(prompt).toHaveTextContent('不反应 HP 5 -> 0')
    expect(prompt).toHaveTextContent('使用后 HP 5 -> 5')
    expect(prompt).toHaveTextContent('可避免倒地')
  })

  it('simulates multiplayer combat clicks: observer waits, owner attacks on their turn', async () => {
    wsConnectedMock.mockReturnValue(true)
    const hostTurnCombat = {
      ...combatFixture,
      current_turn_index: 0,
      turn_order: [
        { character_id: 'host-char', name: 'Host Hero', is_player: true, initiative: 18 },
        { character_id: 'guest-char', name: 'Guest Hero', is_player: true, initiative: 16 },
        { character_id: 'enemy-1', name: '训练假人', is_enemy: true, initiative: 8 },
      ],
      entities: {
        ...combatFixture.entities,
        'host-char': {
          id: 'host-char',
          name: 'Host Hero',
          is_enemy: false,
          hp_current: 12,
          hp_max: 12,
          ac: 16,
          char_class: 'Fighter',
        },
        'guest-char': {
          ...combatFixture.entities['char-1'],
          id: 'guest-char',
          name: 'Guest Hero',
        },
      },
      entity_positions: {
        ...combatFixture.entity_positions,
        'host-char': { x: 4, y: 5 },
        'guest-char': { x: 5, y: 5 },
      },
      turn_states: {
        'host-char': { action_used: false, movement_used: 0, movement_max: 6 },
        'guest-char': { action_used: false, movement_used: 0, movement_max: 6 },
      },
    }
    const guestTurnCombat = {
      ...hostTurnCombat,
      current_turn_index: 1,
    }
    const guestSession = {
      ...sessionFixture,
      is_multiplayer: true,
      player: {
        ...sessionFixture.player,
        id: 'guest-char',
        name: 'Guest Hero',
      },
    }
    const room = {
      is_multiplayer: true,
      session_id: 'sess-1',
      room_code: '234567',
      members: [
        { user_id: 'host-user', display_name: 'Host', character_id: 'host-char', is_online: true },
        { user_id: 'guest-user', display_name: 'Guest', character_id: 'guest-char', is_online: true },
      ],
    }

    localStorage.setItem('user', JSON.stringify({ user_id: 'guest-user', display_name: 'Guest' }))
    window.dispatchEvent(new Event('user-changed'))

    roomsGetMock.mockResolvedValue(room)
    getCombatMock.mockResolvedValue(hostTurnCombat)
    getSessionMock.mockResolvedValue(guestSession)
    getSkillBarMock.mockResolvedValue({
      bar: [
        { k: 'atk', label: '攻击', glyph: 'A', cost: '动作', key: '1', kind: 'attack', available: true },
      ],
    })

    const { container } = render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
        </Routes>
      </MemoryRouter>
    )
    const getAttackSlot = () => {
      const attackSlot = container.querySelector('.slot-key.attack')
      expect(attackSlot).toBeTruthy()
      return attackSlot
    }

    const endTurnButton = await screen.findByRole('button', { name: /结束回合/ })
    await waitFor(() => expect(endTurnButton).toBeDisabled())
    expect(await screen.findByText(/Host 在线 · 等待其完成回合/)).toBeInTheDocument()

    fireEvent.click(getAttackSlot())
    expect(attackRollMock).not.toHaveBeenCalled()
    fireEvent.click(endTurnButton)
    expect(endTurnMock).not.toHaveBeenCalled()

    getCombatMock.mockResolvedValue(guestTurnCombat)
    await act(async () => {
      wsEvents.current?.({ type: 'combat_update', combat: guestTurnCombat })
    })
    await waitFor(() => expect(screen.getAllByText(/你的回合/).length).toBeGreaterThan(0))
    await waitFor(() => expect(screen.getByRole('button', { name: /结束回合/ })).not.toBeDisabled())

    const enemyChip = container.querySelector('.unit-chip.enemy')
    expect(enemyChip).toBeTruthy()
    fireEvent.click(enemyChip)
    await waitFor(() => {
      expect(container.querySelector('.target-card')).toHaveTextContent(guestTurnCombat.entities['enemy-1'].name)
    })
    fireEvent.click(getAttackSlot())

    await waitFor(() => {
      expect(attackRollMock).toHaveBeenCalledWith('sess-1', 'guest-char', 'enemy-1', 'melee', false, 10, '2:1:guest-char', null)
    })

    await waitFor(() => {
      expect(damageRollMock).toHaveBeenCalledWith('sess-1', 'pa-1', [10])
    }, { timeout: 3000 })
    expect(screen.getByText(/Longbow 弹药 -1，剩余 19/)).toBeInTheDocument()
  })

  it('lets the active combat owner Help an ally from the battlefield', async () => {
    wsConnectedMock.mockReturnValue(true)
    const helpCombat = {
      ...combatFixture,
      current_turn_index: 0,
      turn_order: [
        { character_id: 'guest-char', name: 'Guest Hero', is_player: true, initiative: 16 },
        { character_id: 'ally-char', name: 'Ally Hero', is_player: true, initiative: 12 },
        { character_id: 'enemy-1', name: '训练假人', is_enemy: true, initiative: 8 },
      ],
      entities: {
        ...combatFixture.entities,
        'guest-char': {
          ...combatFixture.entities['char-1'],
          id: 'guest-char',
          name: 'Guest Hero',
        },
        'ally-char': {
          id: 'ally-char',
          name: 'Ally Hero',
          is_enemy: false,
          hp_current: 10,
          hp_max: 10,
          ac: 14,
        },
      },
      entity_positions: {
        'guest-char': { x: 4, y: 5 },
        'ally-char': { x: 5, y: 5 },
        'enemy-1': { x: 7, y: 5 },
      },
      turn_states: {
        'guest-char': { action_used: false, movement_used: 0, movement_max: 6 },
        'ally-char': { action_used: false, movement_used: 0, movement_max: 6 },
      },
    }
    const helpedCombat = {
      ...helpCombat,
      turn_states: {
        ...helpCombat.turn_states,
        'guest-char': { action_used: true, movement_used: 0, movement_max: 6 },
        'ally-char': { action_used: false, movement_used: 0, movement_max: 6, being_helped: true },
      },
    }
    const guestSession = {
      ...sessionFixture,
      is_multiplayer: true,
      player: {
        ...sessionFixture.player,
        id: 'guest-char',
        name: 'Guest Hero',
      },
    }
    const room = {
      is_multiplayer: true,
      session_id: 'sess-1',
      room_code: '234567',
      members: [
        { user_id: 'guest-user', display_name: 'Guest', character_id: 'guest-char', is_online: true },
        { user_id: 'ally-user', display_name: 'Ally', character_id: 'ally-char', is_online: true },
      ],
    }

    localStorage.setItem('user', JSON.stringify({ user_id: 'guest-user', display_name: 'Guest' }))
    window.dispatchEvent(new Event('user-changed'))

    roomsGetMock.mockResolvedValue(room)
    getCombatMock.mockImplementation(() => (
      combatActionMock.mock.calls.length
        ? Promise.resolve(helpedCombat)
        : Promise.resolve(helpCombat)
    ))
    getSessionMock.mockResolvedValue(guestSession)
    getSkillBarMock.mockResolvedValue({
      bar: [
        { k: 'help', label: '协助', glyph: '☉', cost: '动作', key: '4', kind: 'bonus', available: true },
      ],
    })

    const { container } = render(
      <MemoryRouter initialEntries={['/combat/sess-1']}>
        <Routes>
          <Route path="/combat/:sessionId" element={<Combat />} />
        </Routes>
      </MemoryRouter>
    )

    const helpSlot = await waitFor(() => {
      const slot = container.querySelector('.slot-key.bonus')
      expect(slot).toBeTruthy()
      return slot
    })
    fireEvent.click(helpSlot)

    const allyToken = await waitFor(() => {
      const token = container.querySelector('.iso-unit.ally.help-target')
      expect(token).toBeTruthy()
      return token
    })
    fireEvent.click(allyToken.closest('.iso-cell'))

    await waitFor(() => {
      expect(combatActionMock).toHaveBeenCalledWith('sess-1', '协助', 'ally-char', false, false, '2:0:guest-char')
      expect(getCombatMock).toHaveBeenCalledTimes(2)
    })
  })
})
