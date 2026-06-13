import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const {
  characterFixture,
  charactersGetMock,
  charactersOptionsMock,
  equipItemMock,
  levelUpMock,
  useItemMock,
  gameGetSessionMock,
} = vi.hoisted(() => ({
  characterFixture: {
    id: 'char-1',
    is_player: true,
    name: '测试战士',
    race: 'Human',
    char_class: 'Fighter',
    level: 1,
    ability_scores: { str: 16, dex: 14, con: 15, int: 10, wis: 12, cha: 8 },
    derived: {
      hp_max: 12,
      ac: 12,
      initiative: 2,
      proficiency_bonus: 2,
      ability_modifiers: { str: 3, dex: 2, con: 2, int: 0, wis: 1, cha: -1 },
      saving_throws: { str: 5, con: 4 },
      spell_slots_max: {},
    },
    hp_current: 4,
    equipment: {
      gold: 10,
      shield: { name: 'Shield', zh: '盾牌', ac: 2, equipped: false },
      gear: [{ name: 'Healing Potion', zh: '治疗药水', consumable: true, cost: 50 }],
    },
    spell_slots: {},
    proficient_skills: ['运动', '感知'],
    proficient_saves: ['str', 'con'],
    conditions: [],
  },
  charactersGetMock: vi.fn(),
  charactersOptionsMock: vi.fn(),
  equipItemMock: vi.fn(),
  levelUpMock: vi.fn(),
  useItemMock: vi.fn(),
  gameGetSessionMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  charactersApi: {
    get: charactersGetMock,
    options: charactersOptionsMock,
    getShopInventory: vi.fn(),
    equipItem: equipItemMock,
    levelUp: levelUpMock,
    useItem: useItemMock,
    sellItem: vi.fn(),
    transferItem: vi.fn(),
    buyItem: vi.fn(),
    updateAmmo: vi.fn(),
  },
  gameApi: {
    getSession: gameGetSessionMock,
  },
}))

vi.mock('../../components/Portrait', () => ({
  default: () => <div data-testid="portrait" />,
}))

import CharacterSheet from '../CharacterSheet'

describe('CharacterSheet inventory integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    charactersGetMock.mockResolvedValue(characterFixture)
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Fighter: null },
      class_spell_details: {},
      class_cantrips: {},
    })
    gameGetSessionMock.mockResolvedValue({
      player: characterFixture,
      companions: [{ id: 'ally-1', name: '测试队友' }],
    })
    equipItemMock.mockResolvedValue({
      equipment: {
        ...characterFixture.equipment,
        shield: { name: 'Shield', zh: '盾牌', ac: 2, equipped: true },
      },
      derived: { ...characterFixture.derived, ac: 14 },
    })
    useItemMock.mockResolvedValue({
      item: 'Healing Potion',
      heal_amount: 5,
      hp_after: 9,
      equipment: {
        ...characterFixture.equipment,
        gear: [],
      },
    })
  })

  it('renders responsive sheet shell and major stat grids', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText(characterFixture.name)

    expect(container.querySelector('.character-sheet-page')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-header')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-header-title')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-content')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-identity-row')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-identity-body')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-core-grid')).toBeInTheDocument()
    expect(container.querySelectorAll('.character-sheet-core-grid .panel')).toHaveLength(4)
    expect(container.querySelector('.character-sheet-ability-grid')).toBeInTheDocument()
    expect(container.querySelectorAll('.character-sheet-ability-grid .ability-card')).toHaveLength(6)
    expect(container.querySelectorAll('.character-sheet-two-column-grid').length).toBeGreaterThanOrEqual(2)

    cleanup()
  })

  it('refreshes sheet stats after equipping an item', async () => {
    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText('测试战士')
    fireEvent.click(screen.getByRole('button', { name: '装备' }))

    await waitFor(() => {
      expect(equipItemMock).toHaveBeenCalledWith('char-1', 'Shield', 'shield', true)
      expect(screen.getByText('已装备 盾牌')).toBeInTheDocument()
      expect(screen.getAllByText('14').length).toBeGreaterThan(0)
    })

    cleanup()
  })

  it('refreshes sheet hit points after using a consumable', async () => {
    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText('治疗药水')
    fireEvent.click(screen.getByRole('button', { name: '使用' }))

    await waitFor(() => {
      expect(useItemMock).toHaveBeenCalledWith('char-1', 'Healing Potion')
      expect(screen.getByText('治疗药水 恢复 5 HP')).toBeInTheDocument()
      expect(screen.getByText('9 / 12')).toBeInTheDocument()
    })

    cleanup()
  })

  it('submits selected level-up spell and cantrip choices', async () => {
    const wizard = {
      ...characterFixture,
      name: 'Spellbook Wizard',
      char_class: 'Wizard',
      level: 3,
      known_spells: ['Magic Missile'],
      cantrips: ['Fire Bolt', 'Mage Hand', 'Light'],
      prepared_spells: ['Magic Missile'],
      derived: {
        ...characterFixture.derived,
        spell_slots_max: { '1st': 4, '2nd': 2 },
      },
      spell_slots: { '1st': 2, '2nd': 1 },
    }
    const leveledWizard = {
      ...wizard,
      level: 4,
      known_spells: ['Magic Missile', 'Shield', 'Shatter'],
      cantrips: ['Fire Bolt', 'Mage Hand', 'Light', 'Ray of Frost'],
    }
    charactersGetMock.mockResolvedValue(wizard)
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Wizard: 'spellbook' },
      class_spell_details: {
        Wizard: [
          { name: 'Magic Missile', level: 1 },
          { name: 'Shield', level: 1 },
          { name: 'Shatter', level: 2 },
          { name: 'Fireball', level: 3 },
        ],
      },
      class_cantrips: { Wizard: ['Fire Bolt', 'Mage Hand', 'Light', 'Ray of Frost'] },
    })
    levelUpMock.mockResolvedValue({
      character: leveledWizard,
      level_up_details: {
        learned_spells: ['Shield', 'Shatter'],
        learned_cantrips: ['Ray of Frost'],
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText('Spellbook Wizard')
    expect(screen.queryByLabelText('Learn Fireball')).not.toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Learn Shield'))
    fireEvent.click(screen.getByLabelText('Learn Shatter'))
    fireEvent.click(screen.getByLabelText('Learn cantrip Ray of Frost'))
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        learned_spells: ['Shield', 'Shatter'],
        learned_cantrips: ['Ray of Frost'],
      })
      expect(screen.getByRole('status')).toHaveTextContent('Level up complete')
    })

    cleanup()
  })

  it('submits known-spell replacement choices during level up', async () => {
    const warlock = {
      ...characterFixture,
      name: 'Pact Warlock',
      char_class: 'Warlock',
      level: 9,
      known_spells: ['Hellish Rebuke'],
      prepared_spells: ['Hellish Rebuke'],
      cantrips: ['Eldritch Blast'],
      derived: {
        ...characterFixture.derived,
        spell_slots_max: { '5th': 2 },
      },
      spell_slots: { '5th': 1 },
    }
    charactersGetMock.mockResolvedValue(warlock)
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Warlock: 'known' },
      class_spell_details: {
        Warlock: [
          { name: 'Hellish Rebuke', level: 1 },
          { name: 'Hex', level: 1 },
        ],
      },
      class_cantrips: { Warlock: ['Eldritch Blast'] },
    })
    levelUpMock.mockResolvedValue({
      character: {
        ...warlock,
        level: 10,
        known_spells: ['Hex'],
        prepared_spells: ['Hex'],
      },
      level_up_details: {
        spell_replacements: [{ old_spell: 'Hellish Rebuke', new_spell: 'Hex' }],
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText('Pact Warlock')
    fireEvent.change(screen.getByLabelText('Replace known spell'), {
      target: { value: 'Hellish Rebuke' },
    })
    fireEvent.change(screen.getByLabelText('Replacement spell'), {
      target: { value: 'Hex' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        spell_replacements: [{ old_spell: 'Hellish Rebuke', new_spell: 'Hex' }],
      })
    })

    cleanup()
  })
})
