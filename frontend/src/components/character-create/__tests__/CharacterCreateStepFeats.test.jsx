import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react'
import CharacterCreateStepFeats from '../CharacterCreateStepFeats'

const MAGIC_INITIATE_OPTIONS = {
  Wizard: {
    cantrips: [
      { name: 'Mage Hand', name_en: 'Mage Hand' },
      { name: 'Light', name_en: 'Light' },
    ],
    spells: [
      { name: 'Shield', name_en: 'Shield' },
    ],
  },
}

function makeCtx(chosenFeats, setChosenFeats) {
  return {
    form: { level: 4 },
    needsASI: true,
    asiCount: 1,
    asiLevels: [4],
    chosenFeats,
    setChosenFeats,
    options: {
      feats: {
        'Magic Initiate': { desc: 'Learn limited magic' },
      },
      magic_initiate_spell_options: MAGIC_INITIATE_OPTIONS,
    },
    finalScores: { str: 14, dex: 14, con: 14, int: 10, wis: 10, cha: 10 },
    isSpellcaster: false,
    chosenCantrips: [],
    chosenSpells: [],
  }
}

describe('CharacterCreateStepFeats', () => {
  it('stores Magic Initiate spell subchoices on the selected feat', async () => {
    let latestFeats = []

    function Harness() {
      const [chosenFeats, setChosenFeats] = useState([{
        name: 'Magic Initiate',
        spellcasting_class: 'Wizard',
        cantrips: [],
        spell: '',
      }])
      latestFeats = chosenFeats
      return <CharacterCreateStepFeats ctx={makeCtx(chosenFeats, setChosenFeats)} />
    }

    render(<Harness />)

    expect(screen.getByRole('group', { name: 'Magic Initiate choices' })).toHaveClass(
      'magic-initiate-choice-fields',
    )
    expect(screen.getByLabelText('Magic Initiate class')).toHaveClass(
      'magic-initiate-choice-select',
      'input-fantasy',
    )
    fireEvent.click(screen.getByLabelText('Magic Initiate cantrip Mage Hand'))
    fireEvent.click(screen.getByLabelText('Magic Initiate cantrip Light'))
    fireEvent.change(screen.getByLabelText('Magic Initiate spell'), {
      target: { value: 'Shield' },
    })

    await waitFor(() => {
      expect(latestFeats[0]).toEqual({
        name: 'Magic Initiate',
        spellcasting_class: 'Wizard',
        cantrips: ['Mage Hand', 'Light'],
        spell: 'Shield',
      })
    })

    cleanup()
  })
})
