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
    expect(screen.getByRole('status', { name: '联机状态' })).toHaveStyle('box-sizing: border-box')
    expect(screen.getByRole('status', { name: '联机状态' })).toHaveStyle('min-width: 0')
    expect(screen.getByText('切换镜头')).toBeInTheDocument()
    expect(screen.getByText('酒馆组已有待处理行动，玩家明确要求切镜头。')).toBeInTheDocument()
    expect(screen.getByText('酒馆组已有待处理行动，玩家明确要求切镜头。')).toHaveStyle('overflow-wrap: anywhere')
    expect(screen.getByText('当前镜头：酒馆组')).toBeInTheDocument()
    expect(screen.getByText('当前镜头：酒馆组')).toHaveStyle('overflow-wrap: anywhere')
    expect(screen.getByText('下一处理：酒馆组 · 1 条待处理 · 全员已确认')).toBeInTheDocument()
    expect(screen.getByText('下一处理：酒馆组 · 1 条待处理 · 全员已确认')).toHaveStyle('overflow-wrap: anywhere')
    expect(screen.getByText('房间 123456')).toBeInTheDocument()
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
