import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const {
  characterFixture,
  charactersGetMock,
  equipItemMock,
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
  equipItemMock: vi.fn(),
  useItemMock: vi.fn(),
  gameGetSessionMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  charactersApi: {
    get: charactersGetMock,
    getShopInventory: vi.fn(),
    equipItem: equipItemMock,
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
})
