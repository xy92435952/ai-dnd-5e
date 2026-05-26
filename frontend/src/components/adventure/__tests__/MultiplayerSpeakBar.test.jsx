import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import MultiplayerSpeakBar from '../MultiplayerSpeakBar'

function renderBar(overrides = {}) {
  const onAiTakeover = vi.fn()
  const onSkipTurn = vi.fn()
  render(<MultiplayerSpeakBar
    room={{
      room_code: '234567',
      members: [
        { user_id: 'me', display_name: '我', character_id: 'c1', character_name: '战士', is_online: true, seconds_since_seen: 0 },
        { user_id: 'u2', display_name: '队友', character_id: 'c2', character_name: '法师', is_online: false, seconds_since_seen: 8 },
      ],
      ...overrides.room,
    }}
    wsConnected
    myUserId="me"
    player={{ id: 'c1', name: '战士' }}
    isMySpeakTurn={false}
    currentSpeakerUid="u2"
    currentSpeakerName="队友"
    onSkipTurn={onSkipTurn}
    onAiTakeover={onAiTakeover}
    {...overrides}
  />)
  return { onAiTakeover, onSkipTurn }
}

describe('MultiplayerSpeakBar', () => {
  it('shows connection, controlled character, and current speaker status', () => {
    renderBar()

    expect(screen.getByText('同步在线')).toBeInTheDocument()
    expect(screen.getByText('角色 战士')).toBeInTheDocument()
    expect(screen.getByText('发言 队友 · 离线')).toBeInTheDocument()
  })

  it('shows reconnecting status while websocket is disconnected', () => {
    renderBar({ wsConnected: false })

    expect(screen.getByText('同步中')).toBeInTheDocument()
  })

  it('keeps AI takeover disabled until the offline threshold is reached', () => {
    const { onAiTakeover } = renderBar()

    const button = screen.getByRole('button', { name: /8秒无动作/ })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(onAiTakeover).not.toHaveBeenCalled()
  })

  it('enables AI takeover once the speaker has been offline long enough', () => {
    const { onAiTakeover } = renderBar({
      room: {
        members: [
          { user_id: 'me', display_name: '我', character_id: 'c1', character_name: '战士', is_online: true, seconds_since_seen: 0 },
          { user_id: 'u2', display_name: '队友', character_id: 'c2', character_name: '法师', is_online: false, seconds_since_seen: 42 },
        ],
      },
    })

    const button = screen.getByRole('button', { name: /AI 代演/ })
    expect(button).toBeEnabled()
    fireEvent.click(button)
    expect(onAiTakeover).toHaveBeenCalledTimes(1)
  })
})
