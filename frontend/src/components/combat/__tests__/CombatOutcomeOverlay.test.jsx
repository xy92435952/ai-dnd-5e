import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import CombatOutcomeOverlay from '../CombatOutcomeOverlay'

describe('CombatOutcomeOverlay', () => {
  it('renders nothing before combat is over', () => {
    const { container } = render(<CombatOutcomeOverlay combatOver={null} onReturn={vi.fn()} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('returns to adventure from the victory overlay', () => {
    const onReturn = vi.fn()

    render(<CombatOutcomeOverlay combatOver="victory" onReturn={onReturn} />)

    expect(screen.getByText('战斗胜利')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /返回冒险/ }))
    expect(onReturn).toHaveBeenCalledTimes(1)
  })
})
