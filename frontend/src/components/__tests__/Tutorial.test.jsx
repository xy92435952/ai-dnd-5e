import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { TutorialEntryCard } from '../Tutorial'

describe('TutorialEntryCard', () => {
  it('renders entry-card chrome through stable classes and opens from card or CTA', () => {
    const onOpen = vi.fn()
    const { container } = render(
      <TutorialEntryCard progress={2} total={4} onOpen={onOpen} />,
    )

    const card = container.querySelector('.tut-entry-card')
    expect(card).toBeInTheDocument()
    expect(container.querySelector('.tec-main')).toBeInTheDocument()
    expect(container.querySelector('.tec-body')).toBeInTheDocument()
    expect(container.querySelector('.tec-main')).not.toHaveAttribute('style')
    expect(container.querySelector('.tec-body')).not.toHaveAttribute('style')

    const dots = container.querySelectorAll('.tec-progress .dot')
    expect(dots).toHaveLength(4)
    expect(dots[0]).toHaveClass('done')
    expect(dots[1]).toHaveClass('done')
    expect(dots[2]).toHaveClass('current')

    fireEvent.click(card)
    expect(onOpen).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button'))
    expect(onOpen).toHaveBeenCalledTimes(2)
  })
})
