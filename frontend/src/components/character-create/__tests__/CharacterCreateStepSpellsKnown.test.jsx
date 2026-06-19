import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within, cleanup } from '@testing-library/react'
import CharacterCreateStepSpellsKnown from '../CharacterCreateStepSpellsKnown'

describe('CharacterCreateStepSpellsKnown', () => {
  it('returns nothing when no known spell choices are required', () => {
    const { container } = render(
      <CharacterCreateStepSpellsKnown
        spellCount={0}
        chosenSpells={[]}
        availableSpells={['Shield']}
        toggleSpell={vi.fn()}
      />,
    )

    expect(container).toBeEmptyDOMElement()
    cleanup()
  })

  it('renders known spell choices with stable spell-card state and toggles selections', () => {
    const toggleSpell = vi.fn()
    render(
      <CharacterCreateStepSpellsKnown
        spellCount={1}
        chosenSpells={['Shield']}
        availableSpells={['Shield', 'Magic Missile']}
        toggleSpell={toggleSpell}
      />,
    )

    const section = screen.getByRole('region', { name: 'Known spell choices' })
    expect(section).toHaveClass('spell-choice-section')
    expect(section.querySelector('.spell-choice-title-known')).not.toBeNull()
    expect(within(section).getByText('1/1')).toHaveClass('spell-choice-count')
    expect(within(section).getByText('1/1')).toHaveAttribute('data-complete', 'true')

    const list = within(section).getByRole('list', { name: 'Known spell options' })
    expect(list).toHaveClass('spell-grid')
    const shield = within(list).getByRole('listitem', { name: 'Known spell Shield' })
    const magicMissile = within(list).getByRole('listitem', { name: 'Known spell Magic Missile' })
    expect(shield).toHaveClass('spell-card', 'lv1', 'sel')
    expect(shield).toHaveAttribute('data-selected', 'true')
    expect(shield.querySelector('.sp-icon')).not.toBeNull()
    expect(within(shield).getByText('Shield')).toHaveClass('sp-name')
    expect(magicMissile).toHaveClass('spell-card', 'lv1', 'dis')
    expect(magicMissile).toBeDisabled()

    fireEvent.click(shield)
    expect(toggleSpell).toHaveBeenCalledWith('Shield')

    cleanup()
  })
})
