import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'

vi.mock('./components/AtmosphereBG', () => ({
  default: () => <div data-testid="atmosphere-bg" />,
}))

vi.mock('./pages/Login', () => ({ default: () => <main>Login page</main> }))
vi.mock('./pages/Home', () => ({ default: () => <main>Home page</main> }))
vi.mock('./pages/CharacterCreate', () => ({ default: () => <main>Create page</main> }))
vi.mock('./pages/Adventure', () => ({ default: () => <main>Adventure page</main> }))
vi.mock('./pages/Combat', () => ({ default: () => <main>Combat page</main> }))
vi.mock('./pages/CharacterSheet', () => ({ default: () => <main>Sheet page</main> }))
vi.mock('./pages/RoomLobby', () => ({ default: () => <main>Lobby page</main> }))
vi.mock('./pages/Room', () => ({ default: () => <main>Room page</main> }))
vi.mock('./pages/ClassGallery', () => ({ default: () => <main>Gallery page</main> }))

import App from './App'

function renderAt(pathname) {
  window.history.pushState({}, '', pathname)
  return render(<App />)
}

describe('App scenic backdrop', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    document.body.removeAttribute('data-theme')
  })

  afterEach(() => {
    cleanup()
    localStorage.clear()
  })

  it('renders the scenic backdrop chrome through classes on non-core routes', () => {
    const { container } = renderAt('/')

    expect(screen.getByText('Home page')).toBeInTheDocument()
    const backdrop = container.querySelector('.scenic-backdrop')
    expect(backdrop).toBeInTheDocument()
    expect(backdrop).toHaveAttribute('data-core-route', 'false')
    expect(backdrop).not.toHaveAttribute('style')
    expect(screen.getByTestId('atmosphere-bg')).toBeInTheDocument()
    expect(document.body).toHaveAttribute('data-theme', 'bg3')
  })

  it('dims the scenic backdrop through route state on Adventure and Combat routes', () => {
    let view = renderAt('/adventure/session-1')

    expect(screen.getByText('Adventure page')).toBeInTheDocument()
    expect(view.container.querySelector('.scenic-backdrop')).toHaveAttribute('data-core-route', 'true')
    expect(view.container.querySelector('.scenic-backdrop')).not.toHaveAttribute('style')

    view.unmount()
    view = renderAt('/combat/session-1')

    expect(screen.getByText('Combat page')).toBeInTheDocument()
    expect(view.container.querySelector('.scenic-backdrop')).toHaveAttribute('data-core-route', 'true')
    expect(view.container.querySelector('.scenic-backdrop')).not.toHaveAttribute('style')
  })
})
