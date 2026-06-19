import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import MultiplayerSessionStatusBar from '../MultiplayerSessionStatusBar'

describe('MultiplayerSessionStatusBar', () => {
  it('renders shared multiplayer table status with reason, focus and next step', () => {
    render(
      <MultiplayerSessionStatusBar
        room={{ is_multiplayer: true, room_code: '123456' }}
        label="DM 调度"
        title="切换镜头"
        reason="酒馆组已有待处理行动，玩家明确要求切镜头。"
        focusLabel="当前镜头：酒馆组"
        nextLabel="下一处理：酒馆组 · 1 条待处理 · 全员已确认"
      />
    )

    expect(screen.getByText('DM 调度')).toBeInTheDocument()
    const status = screen.getByRole('status', { name: '联机状态' })
    expect(status).toHaveClass('multiplayer-session-status')
    expect(status).toHaveAttribute('data-tone', 'table')
    expect(screen.getByText('DM 调度')).toHaveClass('multiplayer-session-status-label')
    expect(screen.getByText('切换镜头')).toBeInTheDocument()
    expect(screen.getByText('酒馆组已有待处理行动，玩家明确要求切镜头。')).toBeInTheDocument()
    expect(screen.getByText('酒馆组已有待处理行动，玩家明确要求切镜头。')).toHaveClass('multiplayer-session-status-reason')
    expect(screen.getByText('当前镜头：酒馆组')).toBeInTheDocument()
    expect(screen.getByText('当前镜头：酒馆组')).toHaveClass('multiplayer-session-status-focus')
    expect(screen.getByText('下一处理：酒馆组 · 1 条待处理 · 全员已确认')).toBeInTheDocument()
    expect(screen.getByText('下一处理：酒馆组 · 1 条待处理 · 全员已确认')).toHaveClass('multiplayer-session-status-next')
    expect(screen.getByText('房间 123456')).toHaveClass('multiplayer-session-status-room')
  })

  it('marks actionable multiplayer status with the active tone', () => {
    render(
      <MultiplayerSessionStatusBar
        room={{ is_multiplayer: true, room_code: '123456' }}
        label="多人战斗"
        title="你的回合"
        reason="轮到 洛林"
        focusLabel="你正在控制当前回合"
        tone="active"
      />
    )

    expect(screen.getByRole('status', { name: '联机状态' })).toHaveAttribute('data-tone', 'active')
    expect(screen.getByText('你的回合')).toHaveClass('multiplayer-session-status-title')
  })

  it('stays hidden outside multiplayer mode', () => {
    const { container } = render(
      <MultiplayerSessionStatusBar
        room={{ is_multiplayer: false, room_code: '123456' }}
        label="DM 调度"
        title="切换镜头"
      />
    )

    expect(container).toBeEmptyDOMElement()
  })
})
