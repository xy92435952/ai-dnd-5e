import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react'
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
    expect(screen.getByRole('button', { name: '重温教程' })).toHaveClass('home-tutorial-replay')
    const tabs = screen.getByRole('tablist', { name: '大厅内容' })
    expect(tabs).toHaveClass('home-tabs')
    expect(within(tabs).getAllByRole('tab')).toHaveLength(2)
    expect(within(tabs).getByRole('tab', { name: '✦ 模组库' })).toHaveAttribute('data-active', 'true')
    expect(within(tabs).getByRole('tab', { name: '❦ 存档档案' })).toHaveAttribute('data-active', 'false')
    const upload = screen.getByRole('button', { name: '上传新模组' })
    expect(upload).toHaveClass('home-upload-panel')
    expect(upload.querySelector('.home-upload-input')).toBeInTheDocument()
    expect(upload.querySelector('.home-upload-icon')).toHaveTextContent('✦')
    expect(upload.querySelector('.home-upload-title')).toHaveTextContent('点击上传新模组')
    expect(upload.querySelector('.home-upload-formats')).toHaveTextContent('支持 PDF · DOCX · Markdown · TXT')
    expect(container.querySelector('.home-module-grid')).toBeInTheDocument()
    expect(container.querySelectorAll('.home-module-card')).toHaveLength(2)
    expect(container.querySelector('.home-module-card.is-featured')).toBeInTheDocument()
    expect(container.querySelector('.home-card-actions')).toBeInTheDocument()

    cleanup()
  })

  it('switches to saves with responsive save cards and wrapping metadata', async () => {
    const { container } = renderHome()

    await screen.findByText('Road to Candlekeep With An Exceptionally Long Module Name')
    const tabs = screen.getByRole('tablist', { name: '大厅内容' })
    fireEvent.click(within(tabs).getByRole('tab', { name: '❦ 存档档案' }))

    await waitFor(() => {
      expect(screen.getByText('A very long save name that should wrap cleanly across narrow home cards')).toBeInTheDocument()
    })

    expect(within(tabs).getByRole('tab', { name: '✦ 模组库' })).toHaveAttribute('data-active', 'false')
    expect(within(tabs).getByRole('tab', { name: '❦ 存档档案' })).toHaveAttribute('data-active', 'true')
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

  it('renders stable empty-state shells for modules and saves', async () => {
    modulesListMock.mockResolvedValue([])
    sessionsListMock.mockResolvedValue([])
    const { container } = renderHome()

    expect(await screen.findByRole('status', { name: '暂无模组' })).toHaveClass('home-empty-state')
    expect(screen.getByText('还没有模组，上传一个开始冒险吧')).toHaveClass('home-empty-text')

    fireEvent.click(screen.getByRole('tab', { name: '❦ 存档档案' }))
    expect(await screen.findByRole('status', { name: '暂无存档' })).toHaveClass('home-empty-state')
    expect(screen.getByText('还没有存档，选择一个模组开始冒险吧')).toHaveClass('home-empty-text')
    expect(container.querySelectorAll('.home-empty-icon')).toHaveLength(1)

    cleanup()
  })

  it('opens the upload picker from click and keyboard activation', async () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {})
    renderHome()

    const upload = await screen.findByRole('button', { name: '上传新模组' })
    fireEvent.click(upload)
    fireEvent.keyDown(upload, { key: 'Enter' })
    fireEvent.keyDown(upload, { key: ' ' })
    fireEvent.keyDown(upload, { key: 'Escape' })

    expect(clickSpy).toHaveBeenCalledTimes(3)
    clickSpy.mockRestore()
    cleanup()
  })
})
