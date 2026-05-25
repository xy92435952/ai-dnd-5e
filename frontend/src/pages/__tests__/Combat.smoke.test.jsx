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
  endTurnMock,
  useItemMock,
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
  endTurnMock: vi.fn(),
  useItemMock: vi.fn(),
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
    return { connected: false, send: () => false }
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

  it('simulates multiplayer combat clicks: observer waits, owner attacks on their turn', async () => {
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
    expect(endTurnButton).toBeDisabled()
    expect(screen.getByText(/Host 在线 · 等待其完成回合/)).toBeInTheDocument()

    fireEvent.click(getAttackSlot())
    expect(attackRollMock).not.toHaveBeenCalled()
    fireEvent.click(endTurnButton)
    expect(endTurnMock).not.toHaveBeenCalled()

    getCombatMock.mockResolvedValue(guestTurnCombat)
    await act(async () => {
      wsEvents.current?.({ type: 'combat_update', combat: guestTurnCombat })
    })
    await waitFor(() => expect(screen.getByText(/你的回合/)).toBeInTheDocument())
    await waitFor(() => expect(screen.getByRole('button', { name: /结束回合/ })).not.toBeDisabled())

    const enemyChip = container.querySelector('.unit-chip.enemy')
    expect(enemyChip).toBeTruthy()
    fireEvent.click(enemyChip)
    await waitFor(() => {
      expect(container.querySelector('.target-card')).toHaveTextContent(guestTurnCombat.entities['enemy-1'].name)
    })
    fireEvent.click(getAttackSlot())

    await waitFor(() => {
      expect(attackRollMock).toHaveBeenCalledWith('sess-1', 'guest-char', 'enemy-1', 'melee', false, 10)
    })

    await waitFor(() => {
      expect(damageRollMock).toHaveBeenCalledWith('sess-1', 'pa-1', [10])
    }, { timeout: 3000 })
  })
})
