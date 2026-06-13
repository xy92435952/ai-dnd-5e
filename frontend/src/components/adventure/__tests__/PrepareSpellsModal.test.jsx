import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

const { charactersOptionsMock } = vi.hoisted(() => ({
  charactersOptionsMock: vi.fn(),
}))

vi.mock('../../../api/client', () => ({
  charactersApi: {
    options: charactersOptionsMock,
  },
}))

import PrepareSpellsModal from '../PrepareSpellsModal'

const baseDerived = {
  spell_ability: 'wis',
  ability_modifiers: {
    wis: 3,
    cha: 2,
    int: 3,
  },
}

function renderModal(player, onSave = vi.fn()) {
  render(
    <PrepareSpellsModal
      player={player}
      onSave={onSave}
      onClose={() => {}}
    />,
  )
  return onSave
}

describe('PrepareSpellsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  it('surfaces prepared-caster subclass expanded spells', async () => {
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Cleric: 'prepared' },
      class_spell_details: {
        Cleric: [{ name: 'Bless', level: 1 }],
      },
      subclass_bonus_spell_details: {
        War: {
          1: [{ name: 'Divine Favor', level: 1 }],
        },
      },
    })
    const onSave = renderModal({
      id: 'cleric-1',
      name: 'War Cleric',
      char_class: 'Cleric',
      subclass: 'War',
      level: 1,
      known_spells: [],
      prepared_spells: [],
      derived: baseDerived,
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Divine Favor' }))
    fireEvent.click(screen.getByLabelText('Save prepared spells'))

    expect(onSave).toHaveBeenCalledWith(['Divine Favor'])
  })

  it('keeps spellbook casters limited to known spellbook entries', async () => {
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Wizard: 'spellbook' },
      class_spell_details: {
        Wizard: [
          { name: 'Magic Missile', level: 1 },
          { name: 'Shield', level: 1 },
        ],
      },
    })
    renderModal({
      id: 'wizard-1',
      name: 'Spellbook Wizard',
      char_class: 'Wizard',
      level: 3,
      known_spells: ['Magic Missile'],
      prepared_spells: ['Magic Missile'],
      derived: {
        ...baseDerived,
        spell_ability: 'int',
      },
    })

    expect(await screen.findByText(/Magic Missile/)).toBeInTheDocument()
    await waitFor(() => expect(charactersOptionsMock).toHaveBeenCalledTimes(1))

    expect(screen.queryByText('Shield')).not.toBeInTheDocument()
  })

  it('locks known-spell casters to their full known list', async () => {
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Warlock: 'known' },
      class_spell_details: {
        Warlock: [
          { name: 'Hex', level: 1 },
          { name: 'Command', level: 1 },
        ],
      },
    })
    const onSave = renderModal({
      id: 'warlock-1',
      name: 'Pact Warlock',
      char_class: 'Warlock',
      level: 3,
      known_spells: ['Hex', 'Armor of Agathys'],
      prepared_spells: [],
      derived: {
        ...baseDerived,
        spell_ability: 'cha',
      },
    })

    const hex = await screen.findByRole('button', { name: /Hex/ })
    const armor = screen.getByRole('button', { name: /Armor of Agathys/ })

    expect(hex).toBeDisabled()
    expect(armor).toBeDisabled()

    fireEvent.click(screen.getByLabelText('Save prepared spells'))

    expect(onSave).toHaveBeenCalledWith(['Hex', 'Armor of Agathys'])
  })

  it('uses half-caster prepared spell limits for paladins', async () => {
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Paladin: 'prepared' },
      class_spell_details: {
        Paladin: [
          { name: 'Bless', level: 1 },
          { name: 'Command', level: 1 },
          { name: 'Cure Wounds', level: 1 },
          { name: 'Shield of Faith', level: 1 },
          { name: 'Wrathful Smite', level: 1 },
        ],
      },
    })
    const onSave = renderModal({
      id: 'paladin-1',
      name: 'Oath Paladin',
      char_class: 'Paladin',
      level: 5,
      known_spells: [],
      prepared_spells: [],
      derived: {
        ...baseDerived,
        spell_ability: 'cha',
      },
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Bless' }))
    fireEvent.click(screen.getByRole('button', { name: 'Command' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cure Wounds' }))
    fireEvent.click(screen.getByRole('button', { name: 'Shield of Faith' }))

    expect(screen.getByRole('button', { name: 'Wrathful Smite' })).toBeDisabled()

    fireEvent.click(screen.getByLabelText('Save prepared spells'))

    expect(onSave).toHaveBeenCalledWith(['Bless', 'Command', 'Cure Wounds', 'Shield of Faith'])
  })
})
