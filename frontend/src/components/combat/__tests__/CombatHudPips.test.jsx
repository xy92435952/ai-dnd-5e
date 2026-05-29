import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatHudPips from '../CombatHudPips'

describe('CombatHudPips', () => {
  it('renders readable action economy labels for a fresh turn', () => {
    const { container } = render(<CombatHudPips turnState={{ movement_max: 6, movement_used: 1 }} />)

    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-label',
      '行动经济：动作可用，附赠可用，反应可用，移动5/6',
    )
    expect(screen.getByText('动作')).toBeInTheDocument()
    expect(screen.getByText('附赠')).toBeInTheDocument()
    expect(screen.getByText('反应')).toBeInTheDocument()
    expect(screen.getByText('移动')).toBeInTheDocument()
    expect(screen.getByText('5/6')).toBeInTheDocument()
    expect(screen.getAllByText('可用')).toHaveLength(3)
    expect(container.querySelector('.action-pips .pip.action.used')).toBeNull()
  })

  it('marks spent action economy and clamps movement remaining at zero', () => {
    const { container } = render(
      <CombatHudPips
        turnState={{
          action_used: true,
          bonus_action_used: true,
          reaction_used: false,
          movement_max: 6,
          movement_used: 8,
        }}
      />,
    )

    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-label',
      '行动经济：动作已用，附赠已用，反应可用，移动0/6',
    )
    expect(container.querySelector('.action-pips .pip.action.used')).toBeTruthy()
    expect(container.querySelector('.action-pips .pip.bonus.used')).toBeTruthy()
    expect(container.querySelector('.action-pips .pip.react.used')).toBeNull()
    expect(container.querySelector('.action-pip.movement.used')).toBeTruthy()
    expect(screen.getByTitle('动作已用')).toBeInTheDocument()
    expect(screen.getByTitle('附赠已用')).toBeInTheDocument()
    expect(screen.getByTitle('反应可用')).toBeInTheDocument()
    expect(screen.getByTitle('移动剩余 0/6')).toBeInTheDocument()
  })

  it('falls back to normal movement when turn state is missing', () => {
    render(<CombatHudPips />)

    expect(screen.getByRole('status')).toHaveAttribute(
      'aria-label',
      '行动经济：动作可用，附赠可用，反应可用，移动6/6',
    )
    expect(screen.getByText('6/6')).toBeInTheDocument()
  })
})
