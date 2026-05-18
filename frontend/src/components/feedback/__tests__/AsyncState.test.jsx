import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AsyncState, ErrorState, ReconnectNotice } from '../AsyncState'

describe('AsyncState feedback primitives', () => {
  it('renders the shared loading, error, and empty states', () => {
    const { rerender } = render(<AsyncState state="loading" loadingText="召唤冒险中" />)
    expect(screen.getByText(/召唤冒险中/)).toBeInTheDocument()

    rerender(<AsyncState state="error" error="网络断开" onRetry={() => {}} />)
    expect(screen.getByText('网络断开')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重试/ })).toBeInTheDocument()

    rerender(<AsyncState state="empty" emptyTitle="还没有存档" emptyDescription="选择模组开始冒险" />)
    expect(screen.getByText('还没有存档')).toBeInTheDocument()
    expect(screen.getByText('选择模组开始冒险')).toBeInTheDocument()
  })

  it('normalizes auth failures to a clear relogin action', () => {
    const onRetry = vi.fn()
    render(<ErrorState error={{ status: 401, message: 'token expired' }} onRetry={onRetry} />)

    expect(screen.getByText(/登录状态已失效/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /重新登录/ }))
    expect(onRetry).toHaveBeenCalled()
  })

  it('renders reconnect status without forcing each page to hand-roll copy', () => {
    render(<ReconnectNotice connected={false} label="多人连接" />)
    expect(screen.getByText(/多人连接重连中/)).toBeInTheDocument()
  })
})
