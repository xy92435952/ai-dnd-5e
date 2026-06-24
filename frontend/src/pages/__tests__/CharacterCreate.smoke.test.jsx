import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const {
  moduleGetMock,
  optionsMock,
  createMock,
  generatePartyMock,
  createSessionMock,
} = vi.hoisted(() => ({
  moduleGetMock: vi.fn(),
  optionsMock: vi.fn(),
  createMock: vi.fn(),
  generatePartyMock: vi.fn(),
  createSessionMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  modulesApi: {
    get: moduleGetMock,
  },
  charactersApi: {
    options: optionsMock,
    create: createMock,
    generateParty: generatePartyMock,
  },
  gameApi: {
    createSession: createSessionMock,
  },
  roomsApi: {
    claimChar: vi.fn(),
  },
}))

vi.mock('../../components/LegendForge', () => ({
  default: ({ open, onDone }) => open ? (
    <button type="button" data-testid="legend-forge" onClick={onDone}>
      forge done
    </button>
  ) : null,
}))

vi.mock('../../components/character-create/CharacterCreateStepBasics', () => ({
  default: ({ ctx }) => (
    <div data-testid="mock-basics">
      <button
        type="button"
        onClick={() => {
          ctx.setForm((form) => ({
            ...form,
            name: 'Mira',
            race: '人类',
            char_class: '战士',
            background: '士兵',
          }))
        }}
      >
        填充基础信息
      </button>
    </div>
  ),
}))

vi.mock('../../components/character-create/CharacterCreateStepAbilities', () => ({
  default: () => <div data-testid="mock-abilities">能力值占位</div>,
}))

vi.mock('../../components/character-create/CharacterCreateStepSkills', () => ({
  default: () => <div data-testid="mock-skills">技能占位</div>,
}))

vi.mock('../../components/character-create/CharacterCreateStepEquipment', () => ({
  default: () => <div data-testid="mock-equipment">装备占位</div>,
}))

vi.mock('../../components/character-create/CharacterCreateStepSpells', () => ({
  default: () => <div data-testid="mock-spells">法术占位</div>,
}))

vi.mock('../../components/character-create/CharacterCreateStepFeats', () => ({
  default: () => <div data-testid="mock-feats">专长占位</div>,
}))

vi.mock('../../components/character-create/CharacterCreateStepParty', () => ({
  default: ({ ctx }) => (
    <div data-testid="mock-party">
      <button type="button" onClick={() => ctx.setStep(ctx.styleStep)}>
        前往 DM 风格
      </button>
    </div>
  ),
}))

import CharacterCreate from '../CharacterCreate'

function makeOptions(overrides = {}) {
  return {
    races: ['人类'],
    classes: ['战士'],
    backgrounds: ['士兵'],
    alignments: ['中立善良'],
    racial_bonuses: { '人类': { str: 1, dex: 1 } },
    racial_ability_bonuses: { '人类': { str: 1, dex: 1 } },
    class_skill_choices: {
      '战士': { count: 0, options: ['运动', '察觉'] },
      Fighter: { count: 0, options: ['运动', '察觉'] },
    },
    class_save_proficiencies: {
      '战士': ['str', 'con'],
      Fighter: ['str', 'con'],
    },
    all_skills: ['运动', '察觉'],
    class_cantrips: {},
    class_spells: {},
    starting_cantrips_count: {},
    starting_spells_count: {},
    spellcaster_classes: [],
    fighting_style_classes: {},
    asi_levels: [4, 8, 12, 16, 19],
    asi_levels_fighter: [4, 6, 8, 12, 14, 16, 19],
    asi_levels_rogue: [4, 8, 10, 12, 16, 19],
    ...overrides,
  }
}

function renderCreate(route = '/setup/mod-1') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/setup/:moduleId" element={<CharacterCreate />} />
        <Route path="/adventure/:sessionId" element={<div data-testid="adventure-route">adventure loaded</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function loadCharacterCreate() {
  const view = renderCreate()
  expect(screen.getByRole('status')).toHaveClass('create-loading-text')
  await screen.findByText('A Very Long Candlekeep Forge Module Name')
  return view
}

async function fillAndAdvanceToConfirm() {
  await screen.findByText('A Very Long Candlekeep Forge Module Name')
  fireEvent.click(screen.getByRole('button', { name: '填充基础信息' }))
  await waitFor(() => {
    expect(screen.getByLabelText('英雄预览：Mira')).toHaveClass('hero-preview')
  })
  fireEvent.click(screen.getByRole('button', { name: /能力值/ }))
  fireEvent.click(screen.getByRole('button', { name: /技能熟练/ }))
  fireEvent.click(screen.getByRole('button', { name: /装备选择/ }))
}

describe('CharacterCreate shell polish', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    moduleGetMock.mockResolvedValue({
      id: 'mod-1',
      name: 'A Very Long Candlekeep Forge Module Name',
      level_min: 1,
      level_max: 3,
      recommended_party_size: 4,
    })
    optionsMock.mockResolvedValue(makeOptions())
    createMock.mockResolvedValue({
      id: 'char-1',
      name: 'Mira',
      race: '人类',
      char_class: '战士',
      level: 1,
    })
    generatePartyMock.mockResolvedValue({
      companions: [
        { id: 'ally-1', name: 'Kara', char_class: '牧师', race: '矮人', level: 1 },
      ],
    })
    createSessionMock.mockResolvedValue({ session_id: 'session-1' })
  })

  it('renders the loading state and stable create shell after module load', async () => {
    const { container } = await loadCharacterCreate()

    const page = screen.getByRole('main', { name: '角色创建' })
    expect(page).toHaveClass('create-scene')
    expect(screen.getByRole('banner', { name: '角色创建概要' })).toHaveClass('create-header')
    expect(screen.getByRole('button', { name: /返回/ })).toHaveClass('create-back-button')
    expect(container.querySelector('.create-module-title')).toHaveTextContent('A Very Long Candlekeep Forge Module Name')
    expect(container.querySelector('.create-module-meta')).toHaveTextContent('推荐等级 Lv 1-3')

    const steps = screen.getByRole('navigation', { name: '角色创建步骤' })
    expect(steps).toHaveClass('create-steps')
    expect(steps.querySelector('.step-dot.cur')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('region', { name: '角色创建当前步骤' })).toHaveClass('create-scroll')
    expect(screen.getByRole('navigation', { name: '角色创建导航' })).toHaveClass('create-nav')
    expect(container.querySelector('.step-counter-label')).toHaveTextContent('基础信息')
    expect(screen.getByRole('button', { name: /能力值/ })).toHaveClass('create-nav-next')

    cleanup()
  })

  it('shows hero preview, confirm action, and DM style shell without changing creation contracts', async () => {
    const { container } = renderCreate()
    await fillAndAdvanceToConfirm()

    const confirm = screen.getByRole('button', { name: /确认并生成队伍/ })
    expect(confirm).toHaveClass('create-nav-confirm')
    fireEvent.click(confirm)

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(expect.objectContaining({
        module_id: 'mod-1',
        name: 'Mira',
        race: '人类',
        char_class: '战士',
        proficient_skills: [],
      }))
      expect(generatePartyMock).toHaveBeenCalledWith(expect.objectContaining({
        module_id: 'mod-1',
        player_character_id: 'char-1',
        party_size: 4,
      }))
    })

    fireEvent.click(await screen.findByRole('button', { name: '前往 DM 风格' }))

    const styles = screen.getByRole('list', { name: 'DM 风格选项' })
    expect(styles).toHaveClass('create-dm-style-grid')
    const classic = within(styles).getByRole('button', { name: /经典桌游/ })
    const epic = within(styles).getByRole('button', { name: /史诗 CRPG/ })
    expect(classic).toHaveClass('create-dm-style-card')
    expect(classic).toHaveAttribute('aria-pressed', 'true')
    expect(classic).toHaveAttribute('data-style-key', 'classic')
    expect(classic.querySelector('.create-dm-style-label')).toHaveTextContent('经典桌游')
    fireEvent.click(epic)
    expect(epic).toHaveAttribute('data-selected', 'true')
    expect(epic).toHaveAttribute('data-style-key', 'epic_crpg')
    expect(container.querySelector('.create-dm-style-current')).toHaveAttribute('data-style-key', 'epic_crpg')
    expect(container.querySelector('.create-dm-style-current')).toHaveTextContent('史诗 CRPG')

    const start = screen.getByRole('button', { name: /开始冒险/ })
    expect(start).toHaveClass('create-nav-start')
    fireEvent.click(start)
    await waitFor(() => {
      expect(createSessionMock).toHaveBeenCalledWith(expect.objectContaining({
        module_id: 'mod-1',
        player_character_id: 'char-1',
        companion_ids: ['ally-1'],
        save_name: 'Mira的冒险',
        dm_style: 'epic_crpg',
      }))
    })
    fireEvent.click(await screen.findByTestId('legend-forge'))
    expect(await screen.findByTestId('adventure-route')).toHaveTextContent('adventure loaded')

    cleanup()
  })

  it('renders a stable error alert when character creation fails', async () => {
    createMock.mockRejectedValue(new Error('创建失败'))
    renderCreate()
    await fillAndAdvanceToConfirm()

    fireEvent.click(screen.getByRole('button', { name: /确认并生成队伍/ }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveClass('create-error')
    expect(alert.querySelector('.create-error-text')).toHaveTextContent('! 创建失败')
    expect(screen.getByRole('button', { name: /确认并生成队伍/ })).toHaveClass('create-nav-confirm')

    cleanup()
  })
})
