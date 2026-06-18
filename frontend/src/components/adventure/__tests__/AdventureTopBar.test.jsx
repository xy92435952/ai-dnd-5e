import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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
  it('keeps primary navigation and personal tools accessible', () => {
    const props = renderTopBar()

    const home = screen.getByRole('button', { name: 'Home' })
    const history = screen.getByRole('button', { name: 'Dialogue history' })
    const journal = screen.getByRole('button', { name: 'Open journal' })
    const character = screen.getByRole('button', { name: 'Open character sheet' })

    expect(home).toHaveClass('adventure-topbar-button')
    expect(home).toHaveAttribute('title', 'Return to the home screen.')
    expect(history).toHaveClass('adventure-topbar-button', 'arcane')
    expect(history).toHaveAttribute('title', 'Review recent dialogue.')
    expect(journal).toHaveAttribute('title', 'Open the generated adventure journal.')
    expect(character).toHaveAttribute('title', 'Open your character sheet.')

    fireEvent.click(home)
    fireEvent.click(history)
    fireEvent.click(journal)
    fireEvent.click(character)

    expect(props.onHome).toHaveBeenCalledTimes(1)
    expect(props.onShowHistory).toHaveBeenCalledTimes(1)
    expect(props.onOpenJournal).toHaveBeenCalledTimes(1)
    expect(props.onOpenCharacter).toHaveBeenCalledTimes(1)
  })

  it('disables shared campaign actions without disabling personal spell prep', () => {
    const reason = 'Only the current speaker can change shared campaign state.'
    renderTopBar({
      sharedMutationBlocked: true,
      sharedMutationBlockedReason: reason,
    })

    const checkpoint = screen.getByRole('button', { name: 'Save checkpoint' })
    const rest = screen.getByRole('button', { name: 'Open rest menu' })
    const prepare = screen.getByRole('button', { name: 'Prepare spells' })

    expect(checkpoint).toBeDisabled()
    expect(checkpoint).toHaveAttribute('title', reason)
    expect(rest).toBeDisabled()
    expect(rest).toHaveAttribute('title', reason)
    expect(prepare).not.toBeDisabled()
    expect(prepare).toHaveAttribute('title', '准备法术')
  })

  it('blocks personal mutation tools while the room is resynchronizing', () => {
    const reason = '房间正在重新同步，请恢复连接后再发言。'
    renderTopBar({
      syncBlocked: true,
      syncBlockedReason: reason,
    })

    const checkpoint = screen.getByRole('button', { name: 'Save checkpoint' })
    const rest = screen.getByRole('button', { name: 'Open rest menu' })
    const prepare = screen.getByRole('button', { name: 'Prepare spells' })

    expect(checkpoint).toBeDisabled()
    expect(checkpoint).toHaveAttribute('title', reason)
    expect(rest).toBeDisabled()
    expect(rest).toHaveAttribute('title', reason)
    expect(prepare).toBeDisabled()
    expect(prepare).toHaveAttribute('title', reason)
  })
})
