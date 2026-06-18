import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import DialoguePendingCheck from '../DialoguePendingCheck'

function renderPendingCheck(overrides = {}) {
  const props = {
    pendingCheck: { check_type: '运动', dc: 15, context: '推开门' },
    checkRolling: false,
    onDiceRoll: vi.fn(),
    player: { class_resources: { lucky_points_remaining: 1 } },
    onToggleLucky: vi.fn(),
    ...overrides,
  }
  render(<DialoguePendingCheck {...props} />)
  return props
}

describe('DialoguePendingCheck', () => {
  it('shows and toggles Lucky when points remain', () => {
    const props = renderPendingCheck({
      pendingCheck: { check_type: '运动', dc: 15, use_lucky: true },
      player: { class_resources: { lucky_points_remaining: 2 } },
    })

    expect(screen.getByRole('region', { name: '待处理技能检定' })).toHaveTextContent('运动检定 · DC 15')
    expect(screen.getByRole('status')).toHaveTextContent('运动检定 · DC 15')
    expect(screen.getByRole('group', { name: '检定资源修正' })).toBeInTheDocument()
    const lucky = screen.getByRole('button', { name: 'Lucky ON · 2' })
    expect(lucky).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(lucky)
    expect(props.onToggleLucky).toHaveBeenCalledTimes(1)
  })

  it('hides Lucky when the character has no points', () => {
    renderPendingCheck({
      player: { class_resources: { lucky_points_remaining: 0 } },
    })

    expect(screen.queryByRole('button', { name: /Lucky/ })).not.toBeInTheDocument()
  })

  it('shows and toggles Bardic Inspiration when an unused die is available', () => {
    const props = renderPendingCheck({
      pendingCheck: { check_type: 'Athletics', dc: 15, use_bardic_inspiration: true },
      player: { class_resources: { bardic_inspiration: { die: 'd8', uses_remaining: 1 } } },
      onToggleBardicInspiration: vi.fn(),
    })

    const bardic = screen.getByRole('button', { name: 'Bardic ON · d8' })
    expect(bardic).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(bardic)
    expect(props.onToggleBardicInspiration).toHaveBeenCalledTimes(1)
  })

  it('disables the roll action while waiting for sync recovery', () => {
    const props = renderPendingCheck({ disabled: true })

    const roll = screen.getByRole('button', { name: '✦ 等待同步恢复 ✦' })
    expect(roll).toBeDisabled()
    fireEvent.click(roll)
    expect(props.onDiceRoll).not.toHaveBeenCalled()
  })
})
