import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import MultiplayerTurnBar from '../MultiplayerTurnBar'

const room = {
  is_multiplayer: true,
  room_code: '123456',
  members: [
    { user_id: 'u1', display_name: '洛林', character_id: 'char-1', is_online: true },
  ],
}

describe('MultiplayerTurnBar', () => {
  it('shows combat controller status for multiplayer combat', () => {
    render(
      <MultiplayerTurnBar
        room={room}
        currentTurnLabel="轮到 洛林"
        isMyTurnMP={true}
        currentTurnCharacterId="char-1"
      />
    )

    expect(screen.getByText('轮到 洛林')).toBeInTheDocument()
    expect(screen.getByText(/房间 123456/)).toBeInTheDocument()
  })

  it('shows websocket reconnect reasons during combat sync blocks', () => {
    render(
      <MultiplayerTurnBar
        room={room}
        wsConnected={false}
        wsStatus={{
          state: 'reconnecting',
          label: '正在重连',
          detail: '服务器暂不可达或正在重启，正在自动重连。',
          retryInMs: 2000,
        }}
        syncBlocked={true}
        currentTurnLabel="轮到 洛林"
        isMyTurnMP={true}
        currentTurnCharacterId="char-1"
      />
    )

    expect(screen.getByText('同步中 · 暂停战斗操作')).toBeInTheDocument()
    expect(screen.getByText('正在重连')).toBeInTheDocument()
    expect(screen.getByTitle('服务器暂不可达或正在重启，正在自动重连。 · 2秒后重试')).toBeInTheDocument()
  })

  it('shows permission websocket failures instead of a generic sync label', () => {
    render(
      <MultiplayerTurnBar
        room={room}
        wsConnected={false}
        wsStatus={{
          state: 'permission_error',
          label: '无房间权限',
          detail: '当前账号没有这个房间的联机权限，请确认房间码或重新加入。',
        }}
        syncBlocked={true}
        currentTurnLabel="轮到 洛林"
        isMyTurnMP={false}
        currentTurnCharacterId="char-1"
      />
    )

    expect(screen.getByText('无房间权限')).toBeInTheDocument()
    expect(screen.getByTitle('当前账号没有这个房间的联机权限，请确认房间码或重新加入。')).toBeInTheDocument()
  })

  it('stays hidden for single-player combat', () => {
    const { container } = render(
      <MultiplayerTurnBar
        room={{ ...room, is_multiplayer: false }}
        currentTurnLabel="轮到 洛林"
        isMyTurnMP={true}
        currentTurnCharacterId="char-1"
      />
    )

    expect(container).toBeEmptyDOMElement()
  })
})
