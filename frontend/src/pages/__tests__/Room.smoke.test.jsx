import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup, act, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const {
  roomFixture,
  roomsGetMock,
  focusGroupMock,
  wsHandlers,
} = vi.hoisted(() => ({
  roomFixture: {
    session_id: 'sess-1',
    room_code: '234567',
    module_id: 'mod-1',
    save_name: '测试房间',
    host_user_id: 'me',
    max_players: 4,
    is_multiplayer: true,
    game_started: false,
    members: [
      { user_id: 'me', display_name: '我', role: 'host', character_id: 'c1', character_name: '战士', is_online: true },
      { user_id: 'u2', display_name: '队友', role: 'player', character_id: null, character_name: null, is_online: true },
    ],
    ai_companions: [],
    active_group_id: 'main',
    party_groups: [
      { id: 'main', name: '主队', location: '酒馆大厅', member_user_ids: ['me'] },
      { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['u2'] },
    ],
    pending_actions_by_group: {
      main: [],
      alley: [{ user_id: 'u2', display_name: '队友', text: '我检查后门。' }],
    },
    group_readiness: {
      main: { me: 'drafting' },
      alley: { u2: 'ready' },
    },
    room_votes: [],
    start_ready_user_ids: [],
  },
  roomsGetMock: vi.fn(),
  focusGroupMock: vi.fn(),
  wsHandlers: { current: null },
}))

vi.mock('../../api/client', () => ({
  roomsApi: {
    get: roomsGetMock,
    start: vi.fn(),
    setStartReady: vi.fn(),
    leave: vi.fn(),
    kick: vi.fn(),
    transfer: vi.fn(),
    fillAi: vi.fn(),
    focusGroup: focusGroupMock,
  },
}))

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: (_sessionId, onEvent) => {
    wsHandlers.current = onEvent
    return { connected: true, send: () => true }
  },
}))

import Room from '../Room'

describe('Room multiplayer lobby', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    wsHandlers.current = null
    localStorage.setItem('user', JSON.stringify({ user_id: 'me', username: 'me', display_name: '我' }))
    roomsGetMock.mockResolvedValue(roomFixture)
    focusGroupMock.mockResolvedValue({ ...roomFixture, active_group_id: 'alley' })
  })

  it('shows readiness and party group focus controls', async () => {
    render(
      <MemoryRouter initialEntries={['/room/sess-1']}>
        <Routes>
          <Route path="/room/:sessionId" element={<Room />} />
        </Routes>
      </MemoryRouter>
    )

    await screen.findByText(/联机准备/)
    expect(screen.getByText(/1\/2 已认领角色/)).toBeInTheDocument()
    expect(screen.getAllByText(/后巷组/).length).toBeGreaterThan(0)
    expect(screen.getByText(/队友 · 已确认/)).toBeInTheDocument()
    expect(screen.getByText('已就绪：后巷组 · 1 条待处理 · 全员已确认')).toBeInTheDocument()
    expect(screen.getByText(/我检查后门/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /设为焦点/ }))
    await waitFor(() => {
      expect(focusGroupMock).toHaveBeenCalledWith('sess-1', 'alley')
    })

    cleanup()
  })

  it('updates kick vote progress from room_state_updated websocket events', async () => {
    render(
      <MemoryRouter initialEntries={['/room/sess-1']}>
        <Routes>
          <Route path="/room/:sessionId" element={<Room />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(wsHandlers.current).toBeTypeOf('function')
    })

    act(() => {
      wsHandlers.current({
        type: 'room_state_updated',
        room: {
          ...roomFixture,
          room_votes: [{
            id: 'kick:u2',
            type: 'kick',
            target_user_id: 'u2',
            created_by_user_id: 'me',
            eligible_voter_user_ids: ['me', 'u3'],
            yes_user_ids: ['me'],
            threshold: 2,
            status: 'open',
          }],
        },
      })
    })

    expect(await screen.findByRole('button', { name: /1\/2/ })).toBeDisabled()

    cleanup()
  })

  it('applies member presence websocket snapshots without refetching the room', async () => {
    render(
      <MemoryRouter initialEntries={['/room/sess-1']}>
        <Routes>
          <Route path="/room/:sessionId" element={<Room />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(wsHandlers.current).toBeTypeOf('function')
    })
    expect(roomsGetMock).toHaveBeenCalledTimes(1)

    act(() => {
      wsHandlers.current({
        type: 'member_offline',
        user_id: 'u2',
        members: [
          {
            user_id: 'me',
            display_name: 'Me',
            role: 'host',
            character_id: 'c1',
            character_name: 'Fighter',
            is_online: true,
          },
          {
            user_id: 'u2',
            display_name: 'Ally',
            role: 'player',
            character_id: 'c2',
            character_name: 'Wizard',
            is_online: false,
          },
        ],
      })
    })

    expect(roomsGetMock).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Ally')).toBeInTheDocument()
    expect(screen.getByText(/Wizard/)).toBeInTheDocument()

    cleanup()
  })

  it('updates transferred host from websocket events without refetching the room', async () => {
    render(
      <MemoryRouter initialEntries={['/room/sess-1']}>
        <Routes>
          <Route path="/room/:sessionId" element={<Room />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(wsHandlers.current).toBeTypeOf('function')
    })
    expect(await screen.findByRole('button', { name: /开启冒险/ })).toBeInTheDocument()
    expect(screen.getByText(/★ 房主/)).toBeInTheDocument()
    expect(roomsGetMock).toHaveBeenCalledTimes(1)

    act(() => {
      wsHandlers.current({
        type: 'host_transferred',
        new_host_user_id: 'u2',
      })
    })

    expect(roomsGetMock).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: /开启冒险/ })).not.toBeInTheDocument()
    const newHostCard = screen.getAllByText('队友')[0].closest('.panel-ornate')
    expect(within(newHostCard).getByText(/★ 房主/)).toBeInTheDocument()
    expect(screen.getByText(/等待房主开启冒险/)).toBeInTheDocument()

    cleanup()
  })
})
