import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import InitiativeRibbon from '../InitiativeRibbon'

describe('InitiativeRibbon', () => {
  const chips = [
    {
      ent: { name: 'Asha', conditions: ['blessed'] },
      t: { character_id: 'hero-1', name: 'Asha', initiative: 18 },
      pct: 80,
      isCur: true,
      dead: false,
      low: false,
      lifeState: 'alive',
    },
    {
      ent: { name: 'Goblin Scout' },
      t: { character_id: 'enemy-1', name: 'Goblin Scout', initiative: 15, is_enemy: true },
      pct: 50,
      isCur: false,
      dead: false,
      low: false,
      lifeState: 'alive',
    },
    {
      ent: { name: 'Fallen Guard' },
      t: { character_id: 'ally-2', name: 'Fallen Guard', initiative: 4 },
      pct: 0,
      isCur: false,
      dead: true,
      low: false,
      lifeState: 'dead',
    },
  ]

  it('marks current and next initiative actors', () => {
    render(<InitiativeRibbon initiativeChips={chips} />)

    const order = screen.getByLabelText('Initiative order')
    expect(within(order).getByText('NOW')).toBeInTheDocument()
    expect(within(order).getByText('NEXT')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Asha, initiative 18, current turn/ })).toHaveClass('active')
    expect(screen.getByRole('button', { name: /Goblin Scout, initiative 15, next turn/ })).toHaveClass('next')
  })

  it('selects living actors and disables defeated actors', () => {
    const onSelectTarget = vi.fn()
    render(<InitiativeRibbon initiativeChips={chips} onSelectTarget={onSelectTarget} />)

    fireEvent.click(screen.getByRole('button', { name: /Goblin Scout/ }))
    expect(onSelectTarget).toHaveBeenCalledWith('enemy-1')

    const defeated = screen.getByRole('button', { name: /Fallen Guard/ })
    expect(defeated).toBeDisabled()
  })
})
