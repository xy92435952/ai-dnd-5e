import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen, waitFor, cleanup, within } from '@testing-library/react'
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

function makeCtx(chosenFeats, setChosenFeats, optionOverrides = {}) {
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
      ...optionOverrides,
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

    const card = screen.getByRole('group', { name: 'ASI or feat choice 1' })
    expect(card).toHaveClass('create-feat-choice-card')
    expect(within(card).getByText(/Lv 4/)).toHaveClass('create-feat-choice-title')
    const featToggle = within(card).getByRole('button', { name: /选择专长|閫夋嫨涓撻暱/ })
    expect(featToggle).toHaveClass('create-feat-choice-toggle')
    expect(featToggle).toHaveAttribute('data-selected', 'true')
    const featSelect = card.querySelector('.create-feat-select')
    expect(featSelect).toBeInTheDocument()
    expect(featSelect).toHaveValue('Magic Initiate')
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

  it('renders ASI and feat ability choice chrome with stable classes', async () => {
    let latestFeats = []

    function Harness() {
      const [chosenFeats, setChosenFeats] = useState([{
        name: 'Resilient',
        ability: 'con',
      }])
      latestFeats = chosenFeats
      return (
        <CharacterCreateStepFeats
          ctx={makeCtx(chosenFeats, setChosenFeats, {
            feats: {
              Resilient: {
                desc: 'Ability +1 and save proficiency',
                prereq: 'Choose one ability',
              },
            },
          })}
        />
      )
    }

    render(<Harness />)

    const card = screen.getByRole('group', { name: 'ASI or feat choice 1' })
    const asiToggle = within(card).getByRole('button', { name: /\+2/ })
    expect(asiToggle).toHaveClass('create-feat-choice-toggle')
    expect(asiToggle).toHaveAttribute('data-selected', 'false')
    expect(within(card).getByText('Prerequisite: Choose one ability')).toHaveClass(
      'create-feat-note-prereq',
    )
    expect(within(card).getByText('Ability +1 and save proficiency')).toHaveClass(
      'create-feat-note-desc',
    )
    const abilitySelect = screen.getByDisplayValue('CON')
    expect(abilitySelect).toHaveClass('create-feat-ability-select')
    expect(abilitySelect.closest('.create-feat-ability-label')).toBeInTheDocument()

    fireEvent.change(abilitySelect, { target: { value: 'wis' } })
    await waitFor(() => {
      expect(latestFeats[0]).toEqual({
        name: 'Resilient',
        ability: 'wis',
      })
    })

    fireEvent.click(asiToggle)
    await waitFor(() => {
      expect(latestFeats[0].name).toBe('__ASI__')
    })

    cleanup()
  })
})
