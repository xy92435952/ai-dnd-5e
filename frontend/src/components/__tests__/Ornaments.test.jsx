import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DiceBadge, Divider, HpBar } from '../Ornaments'

describe('Ornaments', () => {
  it('renders divider and dice badge chrome with stable classes', () => {
    const { container } = render(
      <>
        <Divider>Table marker</Divider>
        <DiceBadge crit>20</DiceBadge>
        <DiceBadge fumble>1</DiceBadge>
      </>,
    )

    expect(container.querySelector('.divider')).toBeInTheDocument()
    expect(screen.getByText('Table marker')).toHaveClass('divider-glyph')
    expect(screen.getByText(/20/)).toHaveClass('dice-badge', 'crit')
    expect(screen.getByText(/1/)).toHaveClass('dice-badge', 'fumble')
  })

  it('keeps HP meter width dynamic while moving fixed fill and meta chrome to classes', () => {
    const { container } = render(<HpBar cur={18} max={30} />)

    const bar = container.querySelector('.hp-bar')
    expect(bar).toHaveClass('mid')
    const fill = container.querySelector('.hp-bar-fill')
    expect(fill).toBeInTheDocument()
    expect(fill).toHaveStyle({ '--hp-bar-width': '60%' })

    const meta = container.querySelector('.hp-bar-meta')
    expect(meta).toBeInTheDocument()
    expect(meta).not.toHaveAttribute('style')
    expect(meta).toHaveTextContent('HP 18/30')
  })

  it('clamps HP meter width and projects low/high tone classes', () => {
    const { container, rerender } = render(<HpBar cur={-3} max={10} />)

    expect(container.querySelector('.hp-bar')).toHaveClass('low')
    expect(container.querySelector('.hp-bar-fill')).toHaveStyle({ '--hp-bar-width': '0%' })

    rerender(<HpBar cur={14} max={10} />)
    expect(container.querySelector('.hp-bar')).toHaveClass('high')
    expect(container.querySelector('.hp-bar-fill')).toHaveStyle({ '--hp-bar-width': '100%' })
  })
})
