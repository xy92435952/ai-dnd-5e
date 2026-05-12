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
