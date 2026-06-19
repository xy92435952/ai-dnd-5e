import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import WebSocketStatusPill from '../WebSocketStatusPill'

describe('WebSocketStatusPill', () => {
  it('uses the connected fallback label and stable tone when no status is supplied', () => {
    render(<WebSocketStatusPill connected />)

    const pill = screen.getByText('同步在线')
    expect(pill).toHaveClass('websocket-status-pill')
    expect(pill).toHaveAttribute('data-state', 'connected')
    expect(pill).toHaveAttribute('title', '实时同步已连接。')
  })

  it('uses the reconnecting fallback while disconnected', () => {
    render(<WebSocketStatusPill connected={false} />)

    const pill = screen.getByText('正在重连')
    expect(pill).toHaveAttribute('data-state', 'reconnecting')
    expect(pill).toHaveAttribute('title', '服务器暂不可达或正在重启，正在自动重连。')
  })

  it('includes retry timing details for reconnecting states', () => {
    render(
      <WebSocketStatusPill
        status={{
          state: 'reconnecting',
          label: '正在重连',
          detail: '服务器暂不可达或正在重启，正在自动重连。',
          retryInMs: 2600,
        }}
      />,
    )

    const pill = screen.getByText('正在重连')
    expect(pill).toHaveAttribute('data-state', 'reconnecting')
    expect(pill).toHaveAttribute('title', '服务器暂不可达或正在重启，正在自动重连。 · 3秒后重试')
  })

  it('surfaces terminal websocket errors with the exact error state', () => {
    render(
      <WebSocketStatusPill
        status={{
          state: 'permission_error',
          label: '无房间权限',
          detail: '当前账号没有这个房间的联机权限，请确认房间码或重新加入。',
        }}
      />,
    )

    const pill = screen.getByText('无房间权限')
    expect(pill).toHaveAttribute('data-state', 'permission_error')
    expect(pill).toHaveAttribute('title', '当前账号没有这个房间的联机权限，请确认房间码或重新加入。')
  })

  it('marks compact status pills without changing their label or details', () => {
    render(
      <WebSocketStatusPill
        compact
        status={{
          state: 'unavailable',
          label: '服务暂离线',
          detail: '后端正在重启。',
        }}
      />,
    )

    const pill = screen.getByText('服务暂离线')
    expect(pill).toHaveClass('websocket-status-pill', 'compact')
    expect(pill).toHaveAttribute('data-state', 'unavailable')
    expect(pill).toHaveAttribute('title', '后端正在重启。')
  })
})
