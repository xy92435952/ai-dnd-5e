import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import CombatHudControls from '../CombatHudControls'

function renderControls(overrides = {}) {
  const props = {
    isProcessing: false,
    isPlayerTurn: true,
    moveMode: false,
    isRanged: false,
    onEndTurn: vi.fn(),
    onToggleMove: vi.fn(),
    onToggleRanged: vi.fn(),
    onOpenCharacter: vi.fn(),
    onReturnAdventure: vi.fn(),
    onForceEndCombat: vi.fn(),
    ...overrides,
  }
  render(<CombatHudControls {...props} />)
  return props
}

describe('CombatHudControls', () => {
  it('disables turn actions when it is another multiplayer player turn', () => {
    const props = renderControls({ isPlayerTurn: false })

    const endTurn = screen.getByTestId('combat-end-turn')
    const move = screen.getByTestId('combat-move-toggle')

    expect(endTurn).toBeDisabled()
    expect(move).toBeDisabled()

    fireEvent.click(endTurn)
    fireEvent.click(move)
    expect(props.onEndTurn).not.toHaveBeenCalled()
    expect(props.onToggleMove).not.toHaveBeenCalled()
  })

  it('keeps turn actions enabled on the local player turn', () => {
    const props = renderControls({ isPlayerTurn: true })

    fireEvent.click(screen.getByTestId('combat-end-turn'))
    fireEvent.click(screen.getByTestId('combat-move-toggle'))

    expect(props.onEndTurn).toHaveBeenCalledTimes(1)
    expect(props.onToggleMove).toHaveBeenCalledTimes(1)
  })
})
