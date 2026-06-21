import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { TutorialCoach, TutorialEntryCard, TutorialHost, TutorialSpotlight } from '../Tutorial'

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

  it('renders coach action callouts through stable classes while keeping coach placement dynamic', () => {
    const { container } = render(
      <TutorialCoach
        step={{
          coach: 'Roll initiative before the fight begins.',
          action: 'Roll initiative',
          require: 'auto',
        }}
        stepIdx={0}
        total={1}
        rect={null}
        onNext={vi.fn()}
      />,
    )

    const coach = container.querySelector('.tut-coach')
    expect(coach).toHaveAttribute('style')

    const actionCallout = container.querySelector('.coach-action-callout')
    expect(actionCallout).toBeInTheDocument()
    expect(actionCallout).not.toHaveAttribute('style')
    expect(actionCallout).toHaveTextContent('Roll initiative')
  })

  it('renders no-target tutorial fallback chrome through stable classes', async () => {
    const { container } = render(
      <TutorialHost open initialChapter="create" onClose={vi.fn()} />,
    )

    await waitFor(() => {
      expect(container.querySelector('.tut-coach')).toBeInTheDocument()
    })

    const mask = container.querySelector('.sp-mask')
    expect(mask).toHaveClass('sp-mask-clear')
    expect(mask).not.toHaveAttribute('style')

    fireEvent.click(container.querySelector('.coach-actions .primary'))

    await waitFor(() => {
      expect(container.querySelector('.tut-glossary')).toBeInTheDocument()
    })

    const glossary = container.querySelector('.tut-glossary')
    expect(glossary).toHaveClass('tut-glossary-fallback')
    expect(glossary).not.toHaveAttribute('style')
    expect(within(glossary).getByText('种族')).toBeInTheDocument()
  })

  it('projects spotlight target geometry through named CSS variables', () => {
    const { container } = render(
      <TutorialSpotlight rect={{ x: 20, y: 30, w: 100, h: 40 }} />,
    )

    const mask = container.querySelector('.sp-mask')
    expect(mask.style.getPropertyValue('--tutorial-spotlight-clip-path')).toContain('12px 22px')
    expect(mask.style.clipPath).toBe('')

    const ring = container.querySelector('.sp-ring')
    expect(ring.style.getPropertyValue('--tutorial-spotlight-x')).toBe('12px')
    expect(ring.style.getPropertyValue('--tutorial-spotlight-y')).toBe('22px')
    expect(ring.style.getPropertyValue('--tutorial-spotlight-width')).toBe('116px')
    expect(ring.style.getPropertyValue('--tutorial-spotlight-height')).toBe('56px')
    expect(ring.style.left).toBe('')
    expect(ring.style.top).toBe('')
    expect(ring.style.width).toBe('')
    expect(ring.style.height).toBe('')
  })
})
