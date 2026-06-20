import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within, cleanup } from '@testing-library/react'
import MagicInitiateChoiceFields from '../MagicInitiateChoiceFields'

const MAGIC_INITIATE_OPTIONS = {
  Wizard: {
    cantrips: [
      { name: 'Mage Hand', name_en: 'Mage Hand' },
      { name: 'Light', name_en: 'Light' },
      { name: 'Minor Illusion', name_en: 'Minor Illusion' },
    ],
    spells: [
      { name: 'Shield', name_en: 'Shield' },
    ],
  },
}

describe('MagicInitiateChoiceFields', () => {
  it('renders an unavailable status when no spell options are present', () => {
    render(<MagicInitiateChoiceFields options={{}} />)

    expect(screen.getByRole('status')).toHaveClass('magic-initiate-choice-empty')
    expect(screen.getByText('Magic Initiate options unavailable')).toBeInTheDocument()

    cleanup()
  })

  it('uses stable classes and emits Magic Initiate subchoice updates', () => {
    const onChange = vi.fn()
    render(
      <MagicInitiateChoiceFields
        value={{
          spellcasting_class: 'Wizard',
          cantrips: ['Mage Hand', 'Light'],
          spell: '',
        }}
        options={MAGIC_INITIATE_OPTIONS}
        onChange={onChange}
        selectClassName="input-fantasy"
      />,
    )

    const group = screen.getByRole('group', { name: 'Magic Initiate choices' })
    expect(group).toHaveClass('magic-initiate-choice-fields')
    const classSelect = screen.getByLabelText('Magic Initiate class')
    expect(classSelect).toHaveClass(
      'magic-initiate-choice-select',
      'input-fantasy',
    )
    expect(classSelect).not.toHaveAttribute('style')
    const spellSelect = screen.getByLabelText('Magic Initiate spell')
    expect(spellSelect).toHaveClass(
      'magic-initiate-choice-select',
      'input-fantasy',
    )
    expect(spellSelect).not.toHaveAttribute('style')
    expect(screen.getByText('Magic Initiate cantrips 2/2')).toHaveClass('magic-initiate-choice-title')

    const cantripList = screen.getByRole('list', { name: 'Magic Initiate cantrip choices' })
    expect(cantripList).toHaveClass('magic-initiate-choice-grid')
    const mageHand = within(cantripList).getByRole('listitem', {
      name: 'Magic Initiate cantrip option Mage Hand',
    })
    const minorIllusion = within(cantripList).getByRole('listitem', {
      name: 'Magic Initiate cantrip option Minor Illusion',
    })
    expect(mageHand).toHaveClass('magic-initiate-choice-card')
    expect(mageHand).toHaveAttribute('data-selected', 'true')
    expect(minorIllusion).toHaveAttribute('data-disabled', 'true')

    fireEvent.click(screen.getByLabelText('Magic Initiate cantrip Mage Hand'))
    expect(onChange).toHaveBeenCalledWith({
      spellcasting_class: 'Wizard',
      cantrips: ['Light'],
      spell: '',
    })

    fireEvent.change(spellSelect, {
      target: { value: 'Shield' },
    })
    expect(onChange).toHaveBeenCalledWith({
      spellcasting_class: 'Wizard',
      cantrips: ['Mage Hand', 'Light'],
      spell: 'Shield',
    })

    cleanup()
  })
})
