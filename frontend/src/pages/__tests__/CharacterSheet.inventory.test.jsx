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
    const detailedCharacter = {
      ...characterFixture,
      fighting_style: 'Defense',
      feats: [{ name: 'Alert' }],
      subclass: 'Champion',
      languages: ['Common', 'Elvish'],
      tool_proficiencies: ['Thieves Tools'],
      conditions: ['Poisoned'],
      condition_durations: { Poisoned: 2 },
      derived: {
        ...characterFixture.derived,
        caster_type: 'martial',
      },
    }
    charactersGetMock.mockResolvedValue(detailedCharacter)
    gameGetSessionMock.mockResolvedValue({
      player: detailedCharacter,
      companions: [{ id: 'ally-1', name: '测试队友' }],
    })
    const { container } = render(
      <MemoryRouter initialEntries={['/character/char-1?sessionId=sess-1']}>
        <Routes>
          <Route path="/character/:characterId" element={<CharacterSheet />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('status')).toHaveClass('character-sheet-loading-text')
    await screen.findByText(detailedCharacter.name)

    expect(screen.getByRole('main', { name: `角色卡：${detailedCharacter.name}` })).toHaveClass('character-sheet-page')
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
    const features = screen.getByRole('list', { name: '职业特性列表' })
    expect(features).toHaveClass('character-sheet-feature-list')
    expect(within(features).getByRole('listitem', { name: '战斗风格 Defense' })).toHaveAttribute('data-tone', 'red')
    expect(within(features).getByRole('listitem', { name: '专长 Alert' })).toHaveAttribute('data-tone', 'gold')
    expect(within(features).getByRole('listitem', { name: '子职业 Champion' })).toHaveAttribute('data-tone', 'arcane')
    expect(within(features).getByRole('listitem', { name: '施法类型 martial' })).toHaveAttribute('data-tone', 'blue')
    const languages = screen.getByRole('list', { name: '语言列表' })
    expect(languages).toHaveClass('character-sheet-proficiency-tag-list')
    expect(within(languages).getByRole('listitem', { name: 'Elvish' })).toHaveClass('character-sheet-proficiency-tag')
    const tools = screen.getByRole('list', { name: '工具熟练列表' })
    expect(tools).toHaveClass('character-sheet-proficiency-tag-list')
    expect(within(tools).getByRole('listitem', { name: 'Thieves Tools' })).toHaveClass('character-sheet-proficiency-tag')
    const conditions = screen.getByRole('list', { name: '状态条件列表' })
    expect(conditions).toHaveClass('character-sheet-condition-list')
    expect(within(conditions).getByRole('listitem', { name: 'Poisoned 2 回合' })).toHaveClass('character-sheet-condition-tag')

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
    const levelUpPanel = screen.getByRole('region', { name: 'Level Up 3 to 4' })
    expect(levelUpPanel).toHaveClass('character-sheet-level-up-panel')
    expect(levelUpPanel.querySelector('.character-sheet-level-up-header')).toHaveClass('has-progress')
    expect(within(levelUpPanel).getByText('Lv3 -> Lv4')).toHaveClass('character-sheet-level-up-level')
    expect(within(levelUpPanel).getByLabelText('Level 3 to Level 4')).toHaveTextContent('Lv3 -> Lv4')
    expect(within(levelUpPanel).getByText('Wizard / spellbook')).toHaveClass('character-sheet-level-up-class')
    expect(within(levelUpPanel).getByRole('button', { name: 'Level Up' })).toHaveClass('character-sheet-level-up-submit')
    const spellSlots = screen.getByRole('list', { name: '法术位列表' })
    expect(spellSlots).toHaveClass('character-sheet-spell-slot-grid')
    expect(within(spellSlots).getAllByRole('listitem')).toHaveLength(2)
    const firstLevelSlots = within(spellSlots).getByRole('listitem', { name: '1环法术位 2/4' })
    expect(firstLevelSlots).toHaveClass('character-sheet-spell-slot-card')
    expect(within(firstLevelSlots).getByText('1环')).toHaveClass('character-sheet-spell-slot-level')
    expect(within(firstLevelSlots).getByText('2/4')).toHaveClass('character-sheet-spell-slot-count')
    expect(firstLevelSlots.querySelectorAll('.character-sheet-spell-slot-pip.filled')).toHaveLength(2)
    expect(firstLevelSlots.querySelectorAll('.character-sheet-spell-slot-pip')).toHaveLength(4)
    expect(within(spellSlots).getByRole('listitem', { name: '2环法术位 1/2' })).toHaveClass('character-sheet-spell-slot-card')
    const cantrips = screen.getByRole('list', { name: '戏法列表' })
    expect(cantrips).toHaveClass('character-sheet-spell-tag-list')
    expect(within(cantrips).getByRole('listitem', { name: 'Fire Bolt' })).toHaveClass('character-sheet-spell-tag-cantrip')
    const preparedSpells = screen.getByRole('list', { name: '已准备法术列表' })
    expect(within(preparedSpells).getByRole('listitem', { name: 'Magic Missile' })).toHaveClass('character-sheet-spell-tag-prepared')
    const knownSpells = screen.getByRole('list', { name: '已知法术列表' })
    expect(within(knownSpells).getByRole('listitem', { name: 'Magic Missile' })).toHaveClass('character-sheet-spell-tag-known')
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
    const replacementOld = screen.getByLabelText('Replace known spell')
    const replacementNew = screen.getByLabelText('Replacement spell')
    const replacementGrid = replacementOld.closest('.character-sheet-level-up-replacement-grid')
    expect(replacementGrid).toBeInTheDocument()
    expect(replacementOld).toHaveClass('character-sheet-level-up-select')
    expect(replacementNew).toHaveClass('character-sheet-level-up-select')
    expect(replacementOld.closest('.character-sheet-level-up-replacement-label')).toBeInTheDocument()
    expect(replacementNew.closest('.character-sheet-level-up-replacement-label')).toBeInTheDocument()
    expect(replacementNew).toBeDisabled()
    fireEvent.change(replacementOld, {
      target: { value: 'Hellish Rebuke' },
    })
    expect(replacementNew).not.toBeDisabled()
    fireEvent.change(replacementNew, {
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
    const asiGrid = screen.getByRole('list', { name: 'ASI 0/2' })
    expect(asiGrid).toHaveClass('character-sheet-level-up-asi-grid')
    expect(within(asiGrid).getAllByRole('listitem')).toHaveLength(6)
    const strCard = within(asiGrid).getByRole('listitem', { name: 'STR 16 to 16 selected 0' })
    expect(strCard).toHaveClass('character-sheet-level-up-asi-card')
    expect(within(strCard).getByText('STR')).toHaveClass('character-sheet-level-up-asi-label')
    expect(within(strCard).getByText('16 -> 16')).toHaveClass('character-sheet-level-up-asi-projection')
    expect(within(strCard).getByText('0')).toHaveClass('character-sheet-level-up-asi-count')
    const increaseStr = within(strCard).getByLabelText('Increase STR')
    expect(increaseStr).toHaveClass('character-sheet-level-up-asi-stepper')
    expect(within(strCard).getByLabelText('Decrease STR')).toBeDisabled()
    fireEvent.click(increaseStr)
    expect(within(strCard).getByText('1')).toHaveClass('character-sheet-level-up-asi-count')
    const conCard = within(asiGrid).getByRole('listitem', { name: 'CON 15 to 15 selected 0' })
    fireEvent.click(within(conCard).getByLabelText('Increase CON'))
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
    const featSelect = screen.getByLabelText('Feat choice')
    expect(featSelect).toHaveClass('character-sheet-level-up-select')
    expect(featSelect.closest('.character-sheet-level-up-feat-field')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Increase STR'))
    fireEvent.change(featSelect, {
      target: { value: 'Tough' },
    })
    expect(screen.getByText('+2 HP per level')).toHaveClass('character-sheet-level-up-feat-note-desc')
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
    expect(screen.getByText('Prerequisite: Choose one ability')).toHaveClass('character-sheet-level-up-feat-note-prereq')
    expect(screen.getByText('Ability +1 and save proficiency')).toHaveClass('character-sheet-level-up-feat-note-desc')
    const featAbilitySelect = screen.getByLabelText('Feat ability choice')
    expect(featAbilitySelect).toHaveClass('character-sheet-level-up-select')
    expect(featAbilitySelect.closest('.character-sheet-level-up-feat-ability-label')).toBeInTheDocument()
    fireEvent.change(featAbilitySelect, {
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
    const subclassSelect = screen.getByLabelText('Subclass choice')
    const fightingStyleSelect = screen.getByLabelText('Fighting style choice')
    expect(subclassSelect).toHaveClass('character-sheet-level-up-select')
    expect(fightingStyleSelect).toHaveClass('character-sheet-level-up-select')
    expect(subclassSelect.closest('.character-sheet-level-up-field')).toBeInTheDocument()
    expect(fightingStyleSelect.closest('.character-sheet-level-up-field')).toBeInTheDocument()

    fireEvent.change(subclassSelect, {
      target: { value: 'Battle Master' },
    })
    expect(screen.getByText('Battle Master turns superiority dice into tactical techniques.')).toHaveClass('character-sheet-level-up-option-detail')
    expect(await screen.findByText('Add superiority die to an attack roll.')).toHaveClass('character-sheet-level-up-choice-description')
    const maneuvers = screen.getByRole('list', { name: 'Maneuvers 0/3' })
    expect(maneuvers).toHaveClass('character-sheet-level-up-choice-list')
    expect(within(maneuvers).getAllByRole('listitem')).toHaveLength(4)
    const precision = within(maneuvers).getByRole('listitem', { name: /Precision Attack/ })
    expect(precision).toHaveClass('character-sheet-level-up-choice', 'has-description')
    expect(precision).toHaveAttribute('data-selected', 'false')
    fireEvent.change(fightingStyleSelect, {
      target: { value: 'Defense' },
    })
    expect(screen.getByText('AC +1 while wearing armor.')).toHaveClass('character-sheet-level-up-option-detail')
    fireEvent.click(await screen.findByLabelText('Learn maneuver Precision Attack'))
    expect(precision).toHaveAttribute('data-selected', 'true')
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
