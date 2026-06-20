import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SwordIcon } from '../Icons'

describe('RPG icons', () => {
  it('renders default shared icon chrome through classes without inline style', () => {
    render(<SwordIcon data-testid="sword-icon" />)

    const icon = screen.getByTestId('sword-icon')
    expect(icon).toHaveClass('rpg-icon')
    expect(icon).not.toHaveAttribute('style')
  })

  it('preserves caller class names and explicit dynamic style overrides', () => {
    render(
      <SwordIcon
        data-testid="styled-icon"
        className="action-icon"
        style={{ opacity: 0.5 }}
      />,
    )

    const icon = screen.getByTestId('styled-icon')
    expect(icon).toHaveClass('rpg-icon')
    expect(icon).toHaveClass('action-icon')
    expect(icon).toHaveStyle({ opacity: '0.5' })
  })
})
