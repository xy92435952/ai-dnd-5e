import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import RoomMultiplayerStatusPanel from '../RoomMultiplayerStatusPanel'

vi.mock('../../../api/rooms', () => ({
  roomsApi: {
    focusGroup: vi.fn(),
  },
}))

describe('RoomMultiplayerStatusPanel', () => {
  const room = {
    is_multiplayer: true,
    session_id: 'sess-1',
    room_code: '234567',
    active_group_id: 'alley',
    members: [
      { user_id: 'me', display_name: '我' },
      { user_id: 'u2', display_name: '队友' },
    ],
    party_groups: [
      { id: 'main', name: '主队', location: '酒馆大厅', member_user_ids: ['me'] },
      { id: 'alley', name: '后巷组', location: '酒馆后巷', member_user_ids: ['u2'] },
    ],
    pending_actions_by_group: {
      alley: [{ user_id: 'u2', display_name: '队友', text: '我检查后门。' }],
    },
    group_readiness: {
      alley: { u2: 'ready' },
    },
  }

  it('shows shared multiplayer prep status for room lobby', () => {
    render(
      <RoomMultiplayerStatusPanel
        room={room}
        claimedCount={1}
        memberCount={2}
        busy={false}
        onFocusGroup={vi.fn()}
      />
    )

    expect(screen.getByText('联机准备')).toBeInTheDocument()
    expect(screen.getByText('1/2 已认领角色')).toBeInTheDocument()
    expect(screen.getByText('当前焦点：后巷组')).toBeInTheDocument()
    expect(screen.getByText('下一处理：后巷组 · 1 条待处理 · 全员已确认')).toBeInTheDocument()
    expect(screen.getByText('房间 234567')).toBeInTheDocument()
  })

  it('stays hidden for single-player rooms', () => {
    const { container } = render(
      <RoomMultiplayerStatusPanel
        room={{ ...room, is_multiplayer: false }}
        claimedCount={1}
        memberCount={2}
        busy={false}
        onFocusGroup={vi.fn()}
      />
    )

    expect(container).toBeEmptyDOMElement()
  })
})
