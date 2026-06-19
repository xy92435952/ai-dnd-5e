import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, cleanup, within } from '@testing-library/react'
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

    expect(screen.getByRole('status')).toHaveClass('character-sheet-loading-text')
    await screen.findByText(characterFixture.name)

    expect(screen.getByRole('main', { name: `角色卡：${characterFixture.name}` })).toHaveClass('character-sheet-page')
    expect(screen.getByRole('banner', { name: '角色卡顶部栏' })).toHaveClass('character-sheet-header')
    expect(screen.getByRole('button', { name: /返回/ })).toHaveClass('character-sheet-back')
    expect(container.querySelector('.character-sheet-header-title')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-content')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '角色身份' })).toHaveClass('character-sheet-identity-card')
    expect(container.querySelector('.character-sheet-identity-row')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-identity-body')).toBeInTheDocument()
    expect(container.querySelector('.character-sheet-name')).toHaveTextContent(characterFixture.name)
    expect(container.querySelector('.character-sheet-identity-meta')).toHaveTextContent('Human · Fighter · Lv1')
    const stats = screen.getByRole('list', { name: '核心数值' })
    expect(stats).toHaveClass('character-sheet-core-grid')
    expect(within(stats).getAllByRole('listitem')).toHaveLength(4)
    expect(within(stats).getByRole('listitem', { name: '生命值 4 / 12' })).toHaveClass('character-sheet-stat-card-hp')
    expect(within(stats).getByRole('meter', { name: '生命值比例' })).toHaveAttribute('aria-valuenow', '4')
    expect(within(stats).getByRole('listitem', { name: '护甲等级 12' })).toHaveClass('character-sheet-stat-card-ac')
    expect(within(stats).getByRole('listitem', { name: '先攻 +2' })).toHaveClass('character-sheet-stat-card-initiative')
    expect(container.querySelector('.character-sheet-stat-separator')).toHaveTextContent('/')
    expect(container.querySelector('.character-sheet-section-title')).toHaveTextContent('能力值')
    const abilities = screen.getByRole('list', { name: '能力值列表' })
    expect(abilities).toHaveClass('character-sheet-ability-grid')
    expect(within(abilities).getAllByRole('listitem')).toHaveLength(6)
    expect(within(abilities).getByRole('listitem', { name: '力量 16 +3' })).toHaveClass('character-sheet-ability-card')
    expect(within(abilities).getByText('力量')).toHaveClass('character-sheet-ability-label')
    expect(within(abilities).getByText('16')).toHaveClass('character-sheet-ability-score')
    expect(within(abilities).getByText('-1')).toHaveClass('character-sheet-ability-mod', 'neg')
    const saves = screen.getByRole('list', { name: '豁免检定列表' })
    expect(saves).toHaveClass('character-sheet-check-list')
    expect(within(saves).getAllByRole('listitem')).toHaveLength(6)
    expect(within(saves).getByRole('listitem', { name: '力量 +5 熟练' })).toHaveAttribute('data-proficient', 'true')
    expect(within(saves).getByRole('listitem', { name: '敏捷 +2' })).toHaveAttribute('data-proficient', 'false')
    const skills = screen.getByRole('list', { name: '技能列表' })
    expect(skills).toHaveClass('character-sheet-skill-list')
    expect(within(skills).getAllByRole('listitem').length).toBeGreaterThan(10)
    const athletics = within(skills).getByRole('listitem', { name: '运动 STR +5 熟练' })
    expect(athletics).toHaveClass('character-sheet-skill-row')
    expect(within(athletics).getByText('(STR)')).toHaveClass('character-sheet-skill-ability')
    expect(container.querySelectorAll('.character-sheet-two-column-grid').length).toBeGreaterThanOrEqual(2)

    cleanup()
  })

  it('renders a stable load-failure shell', async () => {
    charactersGetMock.mockRejectedValue(new Error('角色不存在'))
    render(
      <MemoryRouter initialEntries={['/character/missing']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    const shell = await screen.findByRole('main', { name: '角色卡加载失败' })
    expect(shell).toHaveClass('character-sheet-state-shell')
    expect(screen.getByRole('alert')).toHaveClass('character-sheet-state-error')
    expect(screen.getByRole('alert')).toHaveTextContent('角色不存在')
    expect(screen.getByRole('button', { name: /返回/ })).toHaveClass('character-sheet-state-back')

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
    fireEvent.click(screen.getByLabelText('Increase INT'))
    fireEvent.click(screen.getByLabelText('Increase INT'))
    fireEvent.click(screen.getByLabelText('Learn Shield'))
    fireEvent.click(screen.getByLabelText('Learn Shatter'))
    fireEvent.click(screen.getByLabelText('Learn cantrip Ray of Frost'))
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        ability_score_increases: { int: 2 },
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

  it('does not submit a replacement spell that is also learned during level up', async () => {
    const warlock = {
      ...characterFixture,
      name: 'Growing Warlock',
      char_class: 'Warlock',
      level: 10,
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
        level: 11,
        known_spells: ['Hellish Rebuke', 'Hex'],
        prepared_spells: ['Hellish Rebuke', 'Hex'],
      },
      level_up_details: {
        learned_spells: ['Hex'],
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText('Growing Warlock')
    fireEvent.change(screen.getByLabelText('Replace known spell'), {
      target: { value: 'Hellish Rebuke' },
    })
    fireEvent.change(screen.getByLabelText('Replacement spell'), {
      target: { value: 'Hex' },
    })
    fireEvent.click(screen.getByLabelText('Learn Hex'))
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        learned_spells: ['Hex'],
      })
    })

    cleanup()
  })

  it('submits subclass expanded spell choices during level up', async () => {
    const warlock = {
      ...characterFixture,
      name: 'Fiend Warlock',
      char_class: 'Warlock',
      subclass: 'Fiend',
      level: 2,
      known_spells: ['Hellish Rebuke', 'Hex', 'Armor of Agathys'],
      prepared_spells: ['Hellish Rebuke', 'Hex', 'Armor of Agathys'],
      cantrips: ['Eldritch Blast'],
      derived: {
        ...characterFixture.derived,
        spell_slots_max: { '1st': 2 },
      },
      spell_slots: { '1st': 1 },
    }
    charactersGetMock.mockResolvedValue(warlock)
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Warlock: 'known' },
      class_spell_details: {
        Warlock: [
          { name: 'Hellish Rebuke', level: 1 },
          { name: 'Hex', level: 1 },
          { name: 'Armor of Agathys', level: 1 },
        ],
      },
      subclass_bonus_spell_details: {
        Fiend: {
          1: [
            { name: 'Burning Hands', level: 1 },
            { name: 'Command', level: 1 },
          ],
        },
      },
      class_cantrips: { Warlock: ['Eldritch Blast'] },
    })
    levelUpMock.mockResolvedValue({
      character: {
        ...warlock,
        level: 3,
        known_spells: [...warlock.known_spells, 'Command'],
        prepared_spells: [...warlock.known_spells, 'Command'],
      },
      level_up_details: {
        learned_spells: ['Command'],
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText('Fiend Warlock')
    fireEvent.click(screen.getByLabelText('Learn Command'))
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        learned_spells: ['Command'],
      })
    })

    cleanup()
  })

  it('submits ability score increases during level up', async () => {
    const fighter = {
      ...characterFixture,
      level: 3,
      ability_scores: { str: 16, dex: 14, con: 15, int: 10, wis: 12, cha: 8 },
    }
    charactersGetMock.mockResolvedValue(fighter)
    levelUpMock.mockResolvedValue({
      character: {
        ...fighter,
        level: 4,
        ability_scores: { ...fighter.ability_scores, str: 17, con: 16 },
      },
      level_up_details: {
        ability_score_increases: { str: 1, con: 1 },
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText(fighter.name)
    fireEvent.click(screen.getByLabelText('Increase STR'))
    fireEvent.click(screen.getByLabelText('Increase CON'))
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        ability_score_increases: { str: 1, con: 1 },
      })
    })

    cleanup()
  })

  it('submits feat choice instead of ability score increases during level up', async () => {
    const fighter = {
      ...characterFixture,
      level: 3,
      feats: [{ name: 'Alert' }],
    }
    charactersGetMock.mockResolvedValue(fighter)
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Fighter: null },
      class_spell_details: {},
      class_cantrips: {},
      feats: {
        Alert: { desc: '+5 initiative' },
        'Ritual Caster': { prereq: 'Intelligence or Wisdom 13', desc: 'Cast rituals' },
        Tough: { desc: '+2 HP per level' },
      },
    })
    levelUpMock.mockResolvedValue({
      character: {
        ...fighter,
        level: 4,
        feats: [...fighter.feats, { name: 'Tough' }],
      },
      level_up_details: {
        feat_choice: { name: 'Tough' },
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText(fighter.name)
    expect(screen.getByRole('option', {
      name: /Ritual Caster.*Requires INT or WIS 13/,
    })).toBeDisabled()
    fireEvent.click(screen.getByLabelText('Increase STR'))
    fireEvent.change(screen.getByLabelText('Feat choice'), {
      target: { value: 'Tough' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        feat_choice: { name: 'Tough' },
      })
    })

    cleanup()
  })

  it('submits Resilient feat ability choice during level up', async () => {
    const fighter = {
      ...characterFixture,
      level: 3,
      feats: [],
    }
    charactersGetMock.mockResolvedValue(fighter)
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Fighter: null },
      class_spell_details: {},
      class_cantrips: {},
      feats: {
        Resilient: { prereq: 'Choose one ability', desc: 'Ability +1 and save proficiency' },
      },
    })
    levelUpMock.mockResolvedValue({
      character: {
        ...fighter,
        level: 4,
        ability_scores: { ...fighter.ability_scores, dex: 15 },
        proficient_saves: [...fighter.proficient_saves, 'dex'],
        feats: [{ name: 'Resilient', ability: 'dex' }],
      },
      level_up_details: {
        feat_choice: { name: 'Resilient', ability: 'dex' },
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText(fighter.name)
    fireEvent.change(screen.getByLabelText('Feat choice'), {
      target: { value: 'Resilient' },
    })
    fireEvent.change(screen.getByLabelText('Feat ability choice'), {
      target: { value: 'dex' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        feat_choice: { name: 'Resilient', ability: 'dex' },
      })
    })

    cleanup()
  })

  it('submits Magic Initiate feat spell choices during level up', async () => {
    const fighter = {
      ...characterFixture,
      level: 3,
      feats: [],
    }
    charactersGetMock.mockResolvedValue(fighter)
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Fighter: null },
      class_spell_details: {},
      class_cantrips: {},
      feats: {
        'Magic Initiate': { desc: 'Learn limited magic' },
      },
      magic_initiate_spell_options: {
        Wizard: {
          cantrips: [
            { name: 'Mage Hand', name_en: 'Mage Hand' },
            { name: 'Light', name_en: 'Light' },
          ],
          spells: [
            { name: 'Shield', name_en: 'Shield' },
          ],
        },
      },
    })
    levelUpMock.mockResolvedValue({
      character: {
        ...fighter,
        level: 4,
        feats: [{
          name: 'Magic Initiate',
          spellcasting_class: 'Wizard',
          cantrips: ['Mage Hand', 'Light'],
          spell: 'Shield',
        }],
      },
      level_up_details: {
        feat_choice: {
          name: 'Magic Initiate',
          spellcasting_class: 'Wizard',
          cantrips: ['Mage Hand', 'Light'],
          spell: 'Shield',
        },
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText(fighter.name)
    fireEvent.change(screen.getByLabelText('Feat choice'), {
      target: { value: 'Magic Initiate' },
    })
    expect(screen.getByRole('button', { name: 'Level Up' })).toBeDisabled()
    fireEvent.click(screen.getByLabelText('Magic Initiate cantrip Mage Hand'))
    fireEvent.click(screen.getByLabelText('Magic Initiate cantrip Light'))
    fireEvent.change(screen.getByLabelText('Magic Initiate spell'), {
      target: { value: 'Shield' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Level Up' }))

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        feat_choice: {
          name: 'Magic Initiate',
          spellcasting_class: 'Wizard',
          cantrips: ['Mage Hand', 'Light'],
          spell: 'Shield',
        },
      })
    })

    cleanup()
  })

  it('submits subclass, fighting style, and maneuver choices during level up', async () => {
    const fighter = {
      ...characterFixture,
      level: 2,
      subclass: '',
      fighting_style: '',
      class_resources: { second_wind_used: true, action_surge_used: true },
    }
    charactersGetMock.mockResolvedValue(fighter)
    charactersOptionsMock.mockResolvedValue({
      spell_preparation_type: { Fighter: null },
      class_spell_details: {},
      class_cantrips: {},
      subclass_unlock_levels: { Fighter: 3 },
      subclass_options: {
        Fighter: [
          'Champion',
          {
            name: 'Battle Master',
            desc: 'Battle Master turns superiority dice into tactical techniques.',
          },
        ],
      },
      fighting_styles: {
        Defense: { desc: 'AC +1 while wearing armor.' },
        Dueling: { desc: 'Damage +2' },
      },
      fighting_style_classes: {
        Fighter: { level: 1, styles: ['Defense', 'Dueling'] },
      },
      maneuvers: {
        precision: { name: 'Precision Attack', desc: 'Add superiority die to an attack roll.' },
        trip: { name: 'Trip Attack', desc: 'Knock a target prone after a weapon hit.' },
        disarm: { name: 'Disarming Attack', desc: 'Force a target to drop one held item.' },
        riposte: { name: 'Riposte' },
      },
      battle_master_maneuvers_known_by_level: { 3: 3, 7: 5 },
    })
    levelUpMock.mockResolvedValue({
      character: {
        ...fighter,
        level: 3,
        subclass: 'Battle Master',
        fighting_style: 'Defense',
        class_resources: {
          ...fighter.class_resources,
          superiority_dice_remaining: 4,
          maneuvers_known: ['precision', 'trip', 'disarm'],
        },
      },
      level_up_details: {
        subclass: 'Battle Master',
        fighting_style: 'Defense',
        maneuver_choices: ['precision', 'trip', 'disarm'],
      },
    })

    render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText(fighter.name)
    const levelUpButton = screen.getByRole('button', { name: 'Level Up' })
    expect(levelUpButton).toBeDisabled()

    fireEvent.change(screen.getByLabelText('Subclass choice'), {
      target: { value: 'Battle Master' },
    })
    expect(screen.getByText('Battle Master turns superiority dice into tactical techniques.')).toBeInTheDocument()
    expect(await screen.findByText('Add superiority die to an attack roll.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Fighting style choice'), {
      target: { value: 'Defense' },
    })
    expect(screen.getByText('AC +1 while wearing armor.')).toBeInTheDocument()
    fireEvent.click(await screen.findByLabelText('Learn maneuver Precision Attack'))
    fireEvent.click(screen.getByLabelText('Learn maneuver Trip Attack'))
    fireEvent.click(screen.getByLabelText('Learn maneuver Disarming Attack'))
    expect(levelUpButton).not.toBeDisabled()
    fireEvent.click(levelUpButton)

    await waitFor(() => {
      expect(levelUpMock).toHaveBeenCalledWith('char-1', {
        use_average_hp: true,
        subclass_choice: 'Battle Master',
        fighting_style_choice: 'Defense',
        maneuver_choices: ['precision', 'trip', 'disarm'],
      })
    })

    cleanup()
  })
})
