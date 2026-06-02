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
    expect(screen.getByText('发言 队友 / 法师 · 离线')).toBeInTheDocument()
    expect(screen.getByTitle('当前发言者：队友，角色：法师')).toBeInTheDocument()
    expect(screen.getByText('22秒后可代演')).toBeInTheDocument()
  })

  it('shows reconnecting status while websocket is disconnected', () => {
    renderBar({
      wsConnected: false,
      wsStatus: {
        state: 'reconnecting',
        label: '正在重连',
        detail: '服务器暂不可达或正在重启，正在自动重连。',
        retryInMs: 1000,
      },
    })

    expect(screen.getByText('正在重连')).toBeInTheDocument()
    expect(screen.getByTitle('服务器暂不可达或正在重启，正在自动重连。 · 1秒后重试')).toBeInTheDocument()
  })

  it('shows terminal websocket errors so players know how to recover', () => {
    renderBar({
      wsConnected: false,
      wsStatus: {
        state: 'auth_error',
        label: '登录失效',
        detail: '登录凭证已失效，请重新登录后恢复联机同步。',
        canRetry: false,
      },
    })

    expect(screen.getByText('登录失效')).toBeInTheDocument()
    expect(screen.getByTitle('登录凭证已失效，请重新登录后恢复联机同步。')).toBeInTheDocument()
  })

  it('shows a short resynced notice after reconnect refresh completes', () => {
    renderBar({ syncNotice: '房间状态已重新同步' })

    expect(screen.getByText('房间状态已重新同步')).toBeInTheDocument()
  })

  it('keeps AI takeover disabled until the offline threshold is reached', () => {
    const { onAiTakeover } = renderBar()

    const button = screen.getByRole('button', { name: /离线 8秒/ })
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
    expect(screen.getByText('AI 可接管')).toBeInTheDocument()
    expect(button).toBeEnabled()
    fireEvent.click(button)
    expect(onAiTakeover).toHaveBeenCalledTimes(1)
  })

  it('blocks AI takeover while the local room sync is reconnecting', () => {
    const { onAiTakeover } = renderBar({
      wsConnected: false,
      wsStatus: {
        state: 'reconnecting',
        label: '正在重连',
        detail: '服务器暂不可达或正在重启，正在自动重连。',
        retryInMs: 1000,
      },
      room: {
        members: [
          { user_id: 'me', display_name: '我', character_id: 'c1', character_name: '战士', is_online: true, seconds_since_seen: 0 },
          { user_id: 'u2', display_name: '队友', character_id: 'c2', character_name: '法师', is_online: false, seconds_since_seen: 42 },
        ],
      },
    })

    const button = screen.getByRole('button', { name: /AI 代演/ })
    expect(screen.getByText('同步恢复后可代演')).toBeInTheDocument()
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', '房间正在重新同步，请恢复连接后再使用 AI 代演')
    fireEvent.click(button)
    expect(onAiTakeover).not.toHaveBeenCalled()
  })
})
