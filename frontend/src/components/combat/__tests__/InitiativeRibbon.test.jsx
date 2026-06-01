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
      ent: {
        name: 'Goblin Scout',
        tactical_role: 'skirmisher',
        conditions: ['poisoned'],
        condition_durations: { poisoned: 2 },
      },
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
    expect(screen.getByRole('button', { name: /Goblin Scout, initiative 15, next turn, tactical role 游击/ })).toHaveClass('next')
    expect(within(order).getByText('游击')).toHaveAttribute(
      'title',
      '战术定位：游击。倾向攻击边缘或后排，并在安全时撤步拉开距离。',
    )
    expect(within(order).getByLabelText('Asha conditions: 祝福')).toHaveTextContent('祝')
    expect(within(order).getByTitle('祝福：激活期间，攻击和豁免获得额外骰。')).toHaveClass('buff')
    expect(within(order).getByLabelText('Goblin Scout conditions: 中毒')).toHaveTextContent('中')
    expect(within(order).getByTitle('中毒：攻击骰和属性检定处于劣势。 持续：2 轮。')).toHaveClass('harm')
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
