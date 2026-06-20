import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import AdventurePartyHud from '../AdventurePartyHud'

vi.mock('../../Portrait', () => ({
  default: ({ className }) => <div className={className} data-testid="portrait" />,
}))

vi.mock('../../Crests', () => ({
  classKey: () => 'fighter',
}))

describe('AdventurePartyHud', () => {
  it('exposes party health and character-sheet actions as a named status list', () => {
    const onOpenCharacter = vi.fn()

    render(
      <AdventurePartyHud
        allMembers={[
          {
            id: 'char-1',
            name: 'Tired Hero',
            char_class: 'Fighter',
            hp_current: 6,
            hp_max: 6,
            derived: { hp_max: 12 },
            isPlayer: true,
          },
          {
            id: 'char-2',
            name: 'Bloodied Mage',
            char_class: 'Wizard',
            hp_current: 2,
            hp_max: 10,
          },
          {
            name: 'Unassigned Ally',
            char_class: 'Cleric',
            hp_current: 4,
            derived: { hp_max: 8 },
          },
        ]}
        onOpenCharacter={onOpenCharacter}
      />,
    )

    const party = screen.getByRole('list', { name: '冒险队伍状态' })
    expect(party).toHaveClass('party-hud')
    expect(within(party).getAllByRole('listitem')).toHaveLength(3)

    const current = within(party).getByRole('button', {
      name: 'Tired Hero 当前角色，Tired Hero HP 6/6',
    })
    const currentItem = current.closest('.party-slot-item')
    expect(current).toHaveClass('party-slot-action')
    expect(current).toHaveAttribute('aria-current', 'true')
    expect(current).toHaveAttribute('title', 'Tired Hero HP 6/6')
    expect(within(current).getByText('Tired Hero HP 6/6')).toHaveClass('party-slot-hp-label')
    expect(currentItem.querySelector('.party-slot')).toHaveClass('active')
    expect(currentItem.querySelector('.party-slot-avatar')).toBeInTheDocument()
    expect(within(currentItem).getByTestId('portrait')).toHaveClass('party-slot-portrait')

    const bloodied = within(party).getByRole('button', {
      name: 'Bloodied Mage，Bloodied Mage HP 2/10',
    })
    const bloodiedItem = bloodied.closest('.party-slot-item')
    expect(bloodiedItem.querySelector('.party-slot')).toHaveClass('low')
    expect(bloodiedItem.querySelector('.avatar-crack')).toBeInTheDocument()
    const bloodiedHpFill = bloodiedItem.querySelector('.party-slot-hp-fill')
    expect(bloodiedHpFill).toBeInTheDocument()
    expect(bloodiedHpFill).toHaveStyle({ '--hp-pct': '20%' })

    const unassigned = within(party).getByRole('button', {
      name: 'Unassigned Ally，Unassigned Ally HP 4/8',
    })
    expect(unassigned).toBeDisabled()

    fireEvent.click(current)
    fireEvent.click(bloodied)
    fireEvent.click(unassigned)

    expect(onOpenCharacter).toHaveBeenCalledTimes(2)
    expect(onOpenCharacter).toHaveBeenNthCalledWith(1, 'char-1')
    expect(onOpenCharacter).toHaveBeenNthCalledWith(2, 'char-2')
  })
})
