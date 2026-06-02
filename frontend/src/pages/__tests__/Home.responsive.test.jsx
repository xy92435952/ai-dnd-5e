import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const {
  modulesListMock,
  sessionsListMock,
  getTutorialProgressMock,
} = vi.hoisted(() => ({
  modulesListMock: vi.fn(),
  sessionsListMock: vi.fn(),
  getTutorialProgressMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  modulesApi: {
    list: modulesListMock,
    upload: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
  },
  gameApi: {
    listSessions: sessionsListMock,
    deleteSession: vi.fn(),
  },
}))

vi.mock('../../hooks/useUser', () => ({
  useUser: () => ({ displayName: 'Test Player' }),
}))

vi.mock('../../components/Tutorial', () => ({
  TutorialEntryCard: ({ onOpen }) => (
    <button type="button" className="tutorial-entry-card" onClick={onOpen}>
      Tutorial entry
    </button>
  ),
  TutorialHost: ({ open }) => open ? <div data-testid="tutorial-host" /> : null,
  getTutorialProgress: getTutorialProgressMock,
}))

import Home from '../Home'

function renderHome() {
  return render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>
  )
}

describe('Home responsive shell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('tutorial_seen', '1')
    getTutorialProgressMock.mockReturnValue(4)
    modulesListMock.mockResolvedValue([
      {
        id: 'module-1',
        name: 'Road to Candlekeep With An Exceptionally Long Module Name',
        setting: 'A coastal road, a locked archive, and far too many rumors.',
        parse_status: 'done',
        level_min: 1,
        level_max: 3,
        recommended_party_size: 4,
      },
      {
        id: 'module-2',
        name: 'Parsing Module',
        setting: 'Still being prepared.',
        parse_status: 'processing',
      },
    ])
    sessionsListMock.mockResolvedValue([
      {
        id: 'session-1',
        save_name: 'A very long save name that should wrap cleanly across narrow home cards',
        player_name: 'Mira',
        player_race: 'Human',
        player_class: 'Wizard',
        module_name: 'Road to Candlekeep',
        is_multiplayer: true,
        room_code: '123456',
        combat_active: true,
        updated_at: '2026-06-02T10:20:30Z',
      },
    ])
  })

  it('renders the module hub with responsive page, header, tabs, and card actions', async () => {
    const { container } = renderHome()

    await screen.findByText('Road to Candlekeep With An Exceptionally Long Module Name')

    expect(container.querySelector('.home-page')).toBeInTheDocument()
    expect(container.querySelector('.home-header')).toBeInTheDocument()
    expect(container.querySelector('.home-header-actions')).toBeInTheDocument()
    expect(container.querySelector('.home-tutorial-complete')).toBeInTheDocument()
    expect(container.querySelector('.home-tabs')).toBeInTheDocument()
    expect(container.querySelectorAll('.home-tab')).toHaveLength(2)
    expect(container.querySelector('.home-module-grid')).toBeInTheDocument()
    expect(container.querySelectorAll('.home-module-card')).toHaveLength(2)
    expect(container.querySelector('.home-module-card.is-featured')).toBeInTheDocument()
    expect(container.querySelector('.home-card-actions')).toBeInTheDocument()

    cleanup()
  })

  it('switches to saves with responsive save cards and wrapping metadata', async () => {
    const { container } = renderHome()

    await screen.findByText('Road to Candlekeep With An Exceptionally Long Module Name')
    fireEvent.click(container.querySelectorAll('.home-tab')[1])

    await waitFor(() => {
      expect(screen.getByText('A very long save name that should wrap cleanly across narrow home cards')).toBeInTheDocument()
    })

    expect(container.querySelector('.home-save-grid')).toBeInTheDocument()
    expect(container.querySelector('.home-save-card')).toBeInTheDocument()
    expect(container.querySelector('.home-save-title')).toBeInTheDocument()
    expect(container.querySelector('.home-save-subtitle')).toBeInTheDocument()
    expect(container.querySelector('.home-save-meta')).toBeInTheDocument()
    expect(container.querySelector('.home-save-room')).toBeInTheDocument()
    expect(container.querySelector('.home-save-status.combat')).toBeInTheDocument()
    expect(container.querySelector('.home-save-date')).toBeInTheDocument()
    expect(container.querySelector('.home-save-action')).toBeInTheDocument()

    cleanup()
  })
})
