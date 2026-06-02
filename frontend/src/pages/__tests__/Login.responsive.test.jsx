import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const {
  loginMock,
  registerMock,
  setUserMock,
} = vi.hoisted(() => ({
  loginMock: vi.fn(),
  registerMock: vi.fn(),
  setUserMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  authApi: {
    login: loginMock,
    register: registerMock,
  },
}))

vi.mock('../../hooks/useUser', () => ({
  setUser: setUserMock,
}))

import Login from '../Login'

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  )
}

describe('Login responsive shell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a responsive login card and keeps register/error states inside the shell', () => {
    const { container } = renderLogin()

    expect(container.querySelector('.login-page')).toBeInTheDocument()
    expect(container.querySelector('.login-runes')).toBeInTheDocument()
    expect(container.querySelectorAll('.login-rune')).toHaveLength(2)
    expect(container.querySelector('.login-card')).toBeInTheDocument()
    expect(container.querySelector('.login-title')).toBeInTheDocument()
    expect(container.querySelector('.login-copy')).toBeInTheDocument()
    expect(container.querySelector('.login-form')).toBeInTheDocument()
    expect(container.querySelectorAll('.login-form .input-fantasy')).toHaveLength(2)
    expect(container.querySelector('.login-submit')).toBeInTheDocument()
    expect(container.querySelector('.login-toggle')).toBeInTheDocument()
    expect(container.querySelector('.login-hint')).toBeInTheDocument()

    fireEvent.click(container.querySelector('.login-toggle'))
    expect(container.querySelectorAll('.login-form .input-fantasy')).toHaveLength(3)

    fireEvent.click(container.querySelector('.login-submit'))
    expect(container.querySelector('.login-error')).toBeInTheDocument()
    expect(loginMock).not.toHaveBeenCalled()
    expect(registerMock).not.toHaveBeenCalled()
  })
})
