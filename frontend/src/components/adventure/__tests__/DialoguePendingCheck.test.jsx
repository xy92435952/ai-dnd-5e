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
})
