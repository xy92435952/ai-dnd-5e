import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import SpellModalList from '../SpellModalList'

describe('SpellModalList', () => {
  it('surfaces spell rule tags before selection', () => {
    render(
      <SpellModalList
        level={3}
        shownSpells={[{
          name: 'Fireball',
          level: 3,
          type: 'damage',
          damage: '8d6',
          aoe: true,
          target_type: 'ground point',
          save: 'dex',
          desc: 'A bright streak flashes to a point you choose.',
        }]}
        cantrips={[]}
        selectedSpell={null}
        setSelectedSpell={vi.fn()}
        onSpellHover={vi.fn()}
      />,
    )

    const tags = screen.getByLabelText('Fireball rule tags')
    expect(within(tags).getByText('L3')).toBeInTheDocument()
    expect(within(tags).getByText('Damage')).toBeInTheDocument()
    expect(within(tags).getByText('AoE')).toBeInTheDocument()
    expect(within(tags).getByText('Point')).toBeInTheDocument()
    expect(within(tags).getByText('Save DEX')).toBeInTheDocument()
  })
})
