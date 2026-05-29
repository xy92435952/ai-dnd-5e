import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import ManeuverModal from '../ManeuverModal'

describe('ManeuverModal', () => {
  it('uses a selected maneuver when superiority dice remain', () => {
    const onUse = vi.fn()
    const onClose = vi.fn()

    render(
      <ManeuverModal
        diceType="d8"
        remaining={1}
        onUse={onUse}
        onClose={onClose}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /绊摔/ }))

    expect(onUse).toHaveBeenCalledWith('trip')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('disables maneuver buttons and explains why when no superiority dice remain', () => {
    const onUse = vi.fn()
    const onClose = vi.fn()

    render(
      <ManeuverModal
        diceType="d8"
        remaining={0}
        onUse={onUse}
        onClose={onClose}
      />,
    )

    const trip = screen.getByRole('button', { name: /绊摔/ })
    expect(trip).toBeDisabled()
    expect(trip).toHaveAttribute('title', '没有可用优越骰')
    expect(screen.getByText('没有可用优越骰，无法发动战技。')).toBeInTheDocument()

    fireEvent.click(trip)
    expect(onUse).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })
})
