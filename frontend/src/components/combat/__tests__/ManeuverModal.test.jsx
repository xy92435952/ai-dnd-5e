import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
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

    const dialog = screen.getByRole('dialog', { name: '战技选择' })
    expect(dialog).toHaveClass('maneuver-modal-dialog')
    expect(within(dialog).getByText('优越骰: d8 × 1')).toHaveClass('maneuver-modal-meta')
    const list = within(dialog).getByRole('list', { name: '可用战技' })
    expect(within(list).getAllByRole('listitem').length).toBeGreaterThan(1)
    const trip = within(list).getByRole('button', { name: /发动战技 绊摔/ })
    expect(trip).toHaveClass('maneuver-modal-action')

    fireEvent.click(trip)

    expect(onUse).toHaveBeenCalledWith('trip')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes when the backdrop is clicked', () => {
    const onClose = vi.fn()
    render(
      <ManeuverModal
        diceType="d10"
        remaining={2}
        onUse={vi.fn()}
        onClose={onClose}
      />,
    )

    fireEvent.click(screen.getByRole('dialog', { name: '战技选择' }).parentElement)
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

    const dialog = screen.getByRole('dialog', { name: '战技选择' })
    const list = within(dialog).getByRole('list', { name: '可用战技' })
    const trip = within(list).getByRole('button', { name: /发动战技 绊摔/ })
    expect(trip).toBeDisabled()
    expect(trip).toHaveAttribute('title', '没有可用优越骰')
    expect(within(dialog).getByRole('status')).toHaveTextContent('没有可用优越骰，无法发动战技。')
    expect(within(dialog).getByRole('button', { name: '取消' })).toHaveClass('maneuver-modal-cancel')

    fireEvent.click(trip)
    expect(onUse).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })
})
