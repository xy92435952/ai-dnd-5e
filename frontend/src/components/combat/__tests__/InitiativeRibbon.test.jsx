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

    const ribbon = screen.getByRole('region', { name: '先攻顺序' })
    const order = within(ribbon).getByRole('list', { name: '行动顺序' })
    expect(within(order).getAllByRole('listitem', { name: /行动顺位/ })).toHaveLength(3)
    expect(within(order).getByText('当前')).toBeInTheDocument()
    expect(within(order).getByText('下个')).toBeInTheDocument()

    const currentActor = screen.getByRole('button', { name: /Asha，先攻 18，当前回合，状态 祝福/ })
    expect(currentActor).toHaveClass('active')
    expect(currentActor).toHaveAttribute('aria-current', 'true')

    const nextActor = screen.getByRole('button', {
      name: /Goblin Scout，先攻 15，下一位行动，战术定位 游击，状态 中毒/,
    })
    expect(nextActor).toHaveClass('next')
    expect(within(order).getByText('游击')).toHaveAttribute(
      'title',
      '战术定位：游击。倾向攻击边缘或后排，并在安全时撤步拉开距离。',
    )

    const ashaConditions = within(order).getByRole('list', { name: 'Asha 状态：祝福' })
    expect(within(ashaConditions).getByRole('listitem', { name: '祝福：激活期间，攻击和豁免获得额外骰。' })).toHaveTextContent('祝')
    expect(within(ashaConditions).getByRole('listitem', { name: '祝福：激活期间，攻击和豁免获得额外骰。' })).toHaveClass('buff')

    const goblinConditions = within(order).getByRole('list', { name: 'Goblin Scout 状态：中毒' })
    expect(within(goblinConditions).getByRole('listitem', { name: '中毒：攻击骰和属性检定处于劣势。 持续：2 轮。' })).toHaveTextContent('中')
    expect(within(goblinConditions).getByRole('listitem', { name: '中毒：攻击骰和属性检定处于劣势。 持续：2 轮。' })).toHaveClass('harm')
  })

  it('selects living actors and disables defeated actors', () => {
    const onSelectTarget = vi.fn()
    render(<InitiativeRibbon initiativeChips={chips} onSelectTarget={onSelectTarget} />)

    fireEvent.click(screen.getByRole('button', { name: /Goblin Scout/ }))
    expect(onSelectTarget).toHaveBeenCalledWith('enemy-1')

    const defeated = screen.getByRole('button', { name: /Fallen Guard，先攻 4，友方，已倒下/ })
    expect(defeated).toBeDisabled()
  })
})
