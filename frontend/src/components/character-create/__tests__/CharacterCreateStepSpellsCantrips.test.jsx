import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within, cleanup } from '@testing-library/react'
import CharacterCreateStepSpellsCantrips from '../CharacterCreateStepSpellsCantrips'

describe('CharacterCreateStepSpellsCantrips', () => {
  it('returns nothing when no cantrip choices are required', () => {
    const { container } = render(
      <CharacterCreateStepSpellsCantrips
        cantripCount={0}
        chosenCantrips={[]}
        availableCantrips={['Mage Hand']}
        toggleCantrip={vi.fn()}
      />,
    )

    expect(container).toBeEmptyDOMElement()
    cleanup()
  })

  it('renders cantrip choices with stable spell-card state and toggles selections', () => {
    const toggleCantrip = vi.fn()
    render(
      <CharacterCreateStepSpellsCantrips
        cantripCount={2}
        chosenCantrips={['Mage Hand', 'Light']}
        availableCantrips={['Mage Hand', 'Light', 'Fire Bolt']}
        toggleCantrip={toggleCantrip}
      />,
    )

    const section = screen.getByRole('region', { name: 'Cantrip choices' })
    expect(section).toHaveClass('spell-choice-section')
    expect(section.querySelector('.spell-choice-title-cantrip')).not.toBeNull()
    expect(within(section).getByText('2/2')).toHaveClass('spell-choice-count')
    expect(within(section).getByText('2/2')).toHaveAttribute('data-complete', 'true')

    const list = within(section).getByRole('list', { name: 'Cantrip options' })
    expect(list).toHaveClass('spell-grid')
    const mageHand = within(list).getByRole('listitem', { name: 'Cantrip Mage Hand' })
    const fireBolt = within(list).getByRole('listitem', { name: 'Cantrip Fire Bolt' })
    expect(mageHand).toHaveClass('spell-card', 'cantrip', 'sel')
    expect(mageHand).toHaveAttribute('data-selected', 'true')
    expect(mageHand.querySelector('.sp-icon')).not.toBeNull()
    expect(within(mageHand).getByText('Mage Hand')).toHaveClass('sp-name')
    expect(fireBolt).toHaveClass('spell-card', 'cantrip', 'dis')
    expect(fireBolt).toBeDisabled()

    fireEvent.click(mageHand)
    expect(toggleCantrip).toHaveBeenCalledWith('Mage Hand')

    cleanup()
  })
})
