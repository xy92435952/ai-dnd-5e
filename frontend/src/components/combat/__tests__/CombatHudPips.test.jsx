import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import CombatHudPips from '../CombatHudPips'

describe('CombatHudPips', () => {
  it('renders readable action economy labels for a fresh turn', () => {
    const { container } = render(<CombatHudPips turnState={{ movement_max: 6, movement_used: 1 }} />)

    const region = screen.getByRole('region', { name: '行动经济' })
    const list = within(region).getByRole('list')
    expect(region).toHaveClass('action-pips')
    expect(list).toHaveClass('action-pip-list')
    expect(list).toHaveAttribute(
      'aria-label',
      '行动经济：动作可用，附赠可用，反应可用，移动5/6',
    )
    expect(within(list).getByRole('listitem', { name: '动作可用' })).toHaveClass('action-pip', 'action')
    expect(within(list).getByRole('listitem', { name: '附赠可用' })).toHaveClass('action-pip', 'bonus')
    expect(within(list).getByRole('listitem', { name: '反应可用' })).toHaveClass('action-pip', 'react')
    expect(within(list).getByRole('listitem', { name: '移动剩余 5/6' })).toHaveClass('action-pip', 'movement')
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

    expect(screen.getByRole('list')).toHaveAttribute(
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

    expect(screen.getByRole('list')).toHaveAttribute(
      'aria-label',
      '行动经济：动作可用，附赠可用，反应可用，移动6/6',
    )
    expect(screen.getByText('6/6')).toBeInTheDocument()
  })
})
