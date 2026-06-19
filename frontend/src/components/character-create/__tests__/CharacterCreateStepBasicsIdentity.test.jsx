import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CharacterCreateStepBasicsIdentity from '../CharacterCreateStepBasicsIdentity'

function makeCtx(overrides = {}) {
  return {
    form: {
      name: 'Mara',
      race: 'Human',
      char_class: 'Fighter',
    },
    setForm: vi.fn(),
    options: {
      races: ['Human', 'Elf'],
      classes: ['Fighter', 'Rogue'],
      racial_ability_bonuses: {
        Human: { str: 1, dex: 1 },
      },
    },
    classEnKey: 'Fighter',
    classInfo: {
      hit_die: 'd10',
      primary_ability: 'Strength or Dexterity',
      armor_proficiency: 'All armor, shields',
      description: 'A master of arms and armor.',
    },
    raceEnKey: 'Human',
    saveProfs: ['str', 'con'],
    openModal: vi.fn(),
    ...overrides,
  }
}

describe('CharacterCreateStepBasicsIdentity', () => {
  it('uses stable race detail chrome and preserves race selection and modal callbacks', () => {
    const ctx = makeCtx()
    const { container } = render(<CharacterCreateStepBasicsIdentity ctx={ctx} />)

    const raceCards = container.querySelectorAll('.race-card')
    expect(raceCards).toHaveLength(2)
    expect(raceCards[0]).toHaveClass('sel')

    fireEvent.click(raceCards[1])
    const raceUpdater = ctx.setForm.mock.calls[0][0]
    expect(raceUpdater({ race: 'Human', keep: true })).toEqual({ race: 'Elf', keep: true })

    const raceDetailButton = screen.getByRole('button', { name: 'Human race details' })
    expect(raceDetailButton).toHaveClass('create-basics-detail-button')

    fireEvent.click(raceDetailButton)
    expect(ctx.openModal).toHaveBeenCalledWith('race', 'Human')
  })

  it('moves class portrait and detail button styling into stable classes without changing handoffs', () => {
    const ctx = makeCtx()
    const { container } = render(<CharacterCreateStepBasicsIdentity ctx={ctx} />)

    const classCards = container.querySelectorAll('.class-card')
    expect(classCards).toHaveLength(2)
    expect(classCards[0]).toHaveClass('sel')
    expect(within(classCards[0]).getByText('Fighter')).toHaveClass('class-name')

    const classPortraits = container.querySelectorAll('.create-basics-class-portrait')
    expect(classPortraits).toHaveLength(2)
    expect(classPortraits[0]).toHaveClass('portrait', 'portrait-fighter', 'portrait-sm')

    fireEvent.click(classCards[1])
    const classUpdater = ctx.setForm.mock.calls[0][0]
    expect(classUpdater({ char_class: 'Fighter', subclass: 'Champion', keep: true })).toEqual({
      char_class: 'Rogue',
      subclass: '',
      keep: true,
    })

    const classDetailButton = screen.getByRole('button', { name: 'Fighter class details' })
    expect(classDetailButton).toHaveClass('create-basics-detail-button', 'create-basics-class-detail-button')

    fireEvent.click(classDetailButton)
    expect(ctx.openModal).toHaveBeenCalledWith('class', 'Fighter')
  })
})
