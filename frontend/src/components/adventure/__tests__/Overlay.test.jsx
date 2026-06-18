import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import Overlay from '../Overlay'

describe('Overlay', () => {
  it('renders the shared adventure modal shell with stable classes and document semantics', () => {
    render(
      <Overlay onClose={vi.fn()}>
        <h2>Modal content</h2>
      </Overlay>,
    )

    const panel = screen.getByRole('document')
    const backdrop = panel.parentElement
    expect(backdrop).toHaveClass('adventure-overlay-backdrop')
    expect(backdrop).toHaveAttribute('role', 'presentation')
    expect(panel).toHaveClass('panel', 'adventure-overlay-panel')
    expect(screen.getByText('Modal content')).toBeInTheDocument()
  })

  it('closes on backdrop click and prevents panel clicks from bubbling', () => {
    const onClose = vi.fn()

    render(
      <Overlay onClose={onClose}>
        <button type="button">Keep open</button>
      </Overlay>,
    )

    const panel = screen.getByRole('document')
    fireEvent.click(panel)
    fireEvent.click(screen.getByRole('button', { name: 'Keep open' }))
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.click(panel.parentElement)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
