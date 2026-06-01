import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import RoomMultiplayerStatusPanel from '../RoomMultiplayerStatusPanel'

vi.mock('../../../api/client', () => ({
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
        wsConnected={true}
        wsStatus={{ state: 'connected', label: '同步在线', detail: '实时同步已连接。' }}
        onFocusGroup={vi.fn()}
      />
    )

    expect(screen.getByText('联机准备')).toBeInTheDocument()
    expect(screen.getByText('1/2 已认领角色')).toBeInTheDocument()
    expect(screen.getByText('当前焦点：后巷组')).toBeInTheDocument()
    expect(screen.getByText('下一处理：后巷组 · 1 条待处理 · 全员已确认')).toBeInTheDocument()
    expect(screen.getByText('同步在线')).toBeInTheDocument()
    expect(screen.getByText('房间 234567')).toBeInTheDocument()
  })

  it('shows lobby websocket restart recovery state', () => {
    const onFocusGroup = vi.fn()

    render(
      <RoomMultiplayerStatusPanel
        room={room}
        claimedCount={1}
        memberCount={2}
        busy={false}
        wsConnected={false}
        wsStatus={{
          state: 'reconnecting',
          label: '正在重连',
          detail: '服务器暂不可达或正在重启，正在自动重连。',
          retryInMs: 4000,
        }}
        syncBlocked
        syncBlockedReason="房间正在重新同步，请恢复连接后再调整分组。"
        onFocusGroup={onFocusGroup}
      />
    )

    expect(screen.getByText('正在重连')).toBeInTheDocument()
    expect(screen.getByText('同步中 · 暂停房间变更')).toBeInTheDocument()
    expect(screen.getByText('同步暂停')).toBeInTheDocument()
    expect(screen.getByTitle('服务器暂不可达或正在重启，正在自动重连。 · 4秒后重试')).toBeInTheDocument()
    const focusButton = screen.getByRole('button', { name: '设为焦点' })
    expect(focusButton).toBeDisabled()
    fireEvent.click(focusButton)
    expect(onFocusGroup).not.toHaveBeenCalled()
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
