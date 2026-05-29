import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import CombatHudControls from '../CombatHudControls'

function renderControls(overrides = {}) {
  const props = {
    isProcessing: false,
    isPlayerTurn: true,
    syncBlocked: false,
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
  it('keeps turn action buttons enabled on the active turn', () => {
    const props = renderControls()

    fireEvent.click(screen.getByRole('button', { name: /结束回合/ }))
    fireEvent.click(screen.getByRole('button', { name: /移动/ }))
    fireEvent.click(screen.getByRole('button', { name: /远程/ }))

    expect(props.onEndTurn).toHaveBeenCalledTimes(1)
    expect(props.onToggleMove).toHaveBeenCalledTimes(1)
    expect(props.onToggleRanged).toHaveBeenCalledTimes(1)
  })

  it('explains disabled turn controls while waiting for another turn', () => {
    const props = renderControls({ isPlayerTurn: false })

    const endTurn = screen.getByRole('button', { name: /结束回合/ })
    const move = screen.getByRole('button', { name: /移动/ })
    const ranged = screen.getByRole('button', { name: /远程/ })

    expect(endTurn).toBeDisabled()
    expect(endTurn).toHaveAttribute('title', '等待你的回合')
    expect(move).toBeDisabled()
    expect(move).toHaveAttribute('title', '等待你的回合')
    expect(ranged).toBeDisabled()
    expect(ranged).toHaveAttribute('title', '等待你的回合')
    expect(screen.getByText('等待你的回合')).toBeInTheDocument()

    fireEvent.click(endTurn)
    fireEvent.click(move)
    fireEvent.click(ranged)

    expect(props.onEndTurn).not.toHaveBeenCalled()
    expect(props.onToggleMove).not.toHaveBeenCalled()
    expect(props.onToggleRanged).not.toHaveBeenCalled()
  })

  it('explains sync-blocked turn controls', () => {
    renderControls({ syncBlocked: true })

    const endTurn = screen.getByRole('button', { name: /同步中/ })
    expect(endTurn).toBeDisabled()
    expect(endTurn).toHaveAttribute('title', '等待战斗同步恢复')
    expect(screen.getByText('等待战斗同步恢复')).toBeInTheDocument()
  })
})
