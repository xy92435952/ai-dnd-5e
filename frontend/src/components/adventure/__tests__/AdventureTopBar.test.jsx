import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AdventureTopBar from '../AdventureTopBar'

function renderTopBar(overrides = {}) {
  const props = {
    session: { save_name: 'Echoes', module_name: 'Moonwell' },
    player: { id: 'char-1' },
    isLoading: false,
    canPrepareSpells: true,
    onHome: vi.fn(),
    onCheckpoint: vi.fn(),
    onShowHistory: vi.fn(),
    onOpenJournal: vi.fn(),
    onOpenRest: vi.fn(),
    onOpenPrepare: vi.fn(),
    onOpenCharacter: vi.fn(),
    ...overrides,
  }

  render(<AdventureTopBar {...props} />)
  return props
}

describe('AdventureTopBar', () => {
  it('disables shared campaign actions without disabling personal spell prep', () => {
    const reason = 'Only the current speaker can change shared campaign state.'
    renderTopBar({
      sharedMutationBlocked: true,
      sharedMutationBlockedReason: reason,
    })

    const checkpoint = screen.getByRole('button', { name: /存档/ })
    const rest = screen.getByRole('button', { name: /休息/ })
    const prepare = screen.getByRole('button', { name: /备法/ })

    expect(checkpoint).toBeDisabled()
    expect(checkpoint).toHaveAttribute('title', reason)
    expect(rest).toBeDisabled()
    expect(rest).toHaveAttribute('title', reason)
    expect(prepare).not.toBeDisabled()
  })
})
