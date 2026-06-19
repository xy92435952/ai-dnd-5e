import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const {
  modulesListMock,
  roomCreateMock,
  roomJoinMock,
  navigateMock,
} = vi.hoisted(() => ({
  modulesListMock: vi.fn(),
  roomCreateMock: vi.fn(),
  roomJoinMock: vi.fn(),
  navigateMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  modulesApi: {
    list: modulesListMock,
  },
  roomsApi: {
    create: roomCreateMock,
    join: roomJoinMock,
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

import RoomLobby from '../RoomLobby'

function renderLobby() {
  return render(
    <MemoryRouter initialEntries={['/lobby']}>
      <Routes>
        <Route path="/lobby" element={<RoomLobby />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RoomLobby multiplayer entry', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    modulesListMock.mockResolvedValue([
      { id: 'mod-1', name: 'Lost Mine' },
      { id: 'mod-2', name: 'Candlekeep' },
    ])
    roomCreateMock.mockResolvedValue({ session_id: 'room-1' })
    roomJoinMock.mockResolvedValue({ session_id: 'room-2' })
  })

  it('renders stable create-room shell and DM style controls', async () => {
    const { container } = renderLobby()

    expect(await screen.findByText('Lost Mine')).toBeInTheDocument()
    const page = container.querySelector('.room-lobby-page')
    expect(page?.tagName).toBe('MAIN')
    expect(page).toHaveAttribute('aria-label', '多人联机大厅')
    expect(screen.getByLabelText('多人房间入口')).toHaveClass('room-lobby-panel')
    expect(container.querySelector('.room-lobby-title')).toHaveTextContent('多人联机大厅')

    const tabs = screen.getByRole('tablist', { name: '房间入口模式' })
    expect(tabs).toHaveClass('room-lobby-tabs')
    expect(within(tabs).getByRole('tab', { name: '创建房间' })).toHaveAttribute('data-active', 'true')
    expect(within(tabs).getByRole('tab', { name: '加入房间' })).toHaveAttribute('data-active', 'false')

    const createForm = screen.getByRole('group', { name: '创建房间表单' })
    expect(createForm).toHaveClass('room-lobby-form')
    expect(screen.getByRole('list', { name: 'DM 风格选项' })).toHaveClass('room-lobby-dm-style-list')
    const styleButtons = container.querySelectorAll('.room-lobby-dm-style')
    expect(styleButtons.length).toBeGreaterThan(0)
    expect(styleButtons[0]).toHaveAttribute('data-selected', 'true')
    expect(styleButtons[0]).toHaveAttribute('aria-pressed', 'true')
    expect(styleButtons[0].querySelector('.room-lobby-dm-style-label')).toBeInTheDocument()
    expect(styleButtons[0].querySelector('.room-lobby-dm-style-summary')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /创建并进入房间/ })).toHaveClass('room-lobby-submit')
    expect(screen.getByRole('button', { name: /返回主页/ })).toHaveClass('room-lobby-back')

    cleanup()
  })

  it('creates a room with the selected module and DM style', async () => {
    const { container } = renderLobby()
    await screen.findByText('Lost Mine')

    fireEvent.change(screen.getByPlaceholderText('例如：周五跑团团'), { target: { value: 'Friday Table' } })
    const selects = screen.getByRole('group', { name: '创建房间表单' }).querySelectorAll('select')
    fireEvent.change(selects[1], { target: { value: '3' } })
    const styleButtons = container.querySelectorAll('.room-lobby-dm-style')
    fireEvent.click(styleButtons[1])
    fireEvent.click(screen.getByRole('button', { name: /创建并进入房间/ }))

    await waitFor(() => {
      expect(roomCreateMock).toHaveBeenCalledWith('mod-1', 'Friday Table', 3, expect.any(String))
    })
    expect(roomCreateMock.mock.calls[0][3]).not.toBe('')
    expect(navigateMock).toHaveBeenCalledWith('/room/room-1')

    cleanup()
  })

  it('switches to join mode and sanitizes the six-digit room code', async () => {
    renderLobby()
    await screen.findByText('Lost Mine')

    const tabs = screen.getByRole('tablist', { name: '房间入口模式' })
    fireEvent.click(within(tabs).getByRole('tab', { name: '加入房间' }))
    expect(within(tabs).getByRole('tab', { name: '创建房间' })).toHaveAttribute('data-active', 'false')
    expect(within(tabs).getByRole('tab', { name: '加入房间' })).toHaveAttribute('data-active', 'true')

    const joinForm = screen.getByRole('group', { name: '加入房间表单' })
    expect(joinForm).toHaveClass('room-lobby-form')
    const input = screen.getByPlaceholderText('6 位数字')
    expect(input).toHaveClass('room-lobby-code-input')
    fireEvent.change(input, { target: { value: '12ab345678' } })
    expect(input).toHaveValue('123456')

    fireEvent.click(screen.getByRole('button', { name: /加入房间/ }))
    await waitFor(() => {
      expect(roomJoinMock).toHaveBeenCalledWith('123456')
    })
    expect(navigateMock).toHaveBeenCalledWith('/room/room-2')

    cleanup()
  })

  it('shows a stable error alert and back action', async () => {
    modulesListMock.mockResolvedValue([])
    renderLobby()

    await screen.findByText('— 请选择 —')
    fireEvent.click(screen.getByRole('button', { name: /创建并进入房间/ }))
    expect(screen.getByRole('alert')).toHaveClass('room-lobby-error')
    expect(screen.getByRole('alert')).toHaveTextContent('请先选择模组')

    fireEvent.click(screen.getByRole('button', { name: /返回主页/ }))
    expect(navigateMock).toHaveBeenCalledWith('/')

    cleanup()
  })
})
