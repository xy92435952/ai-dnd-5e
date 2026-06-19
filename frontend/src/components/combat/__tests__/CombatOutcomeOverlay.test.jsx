import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CombatOutcomeOverlay from '../CombatOutcomeOverlay'

describe('CombatOutcomeOverlay', () => {
  it('renders nothing before combat is over', () => {
    const { container } = render(<CombatOutcomeOverlay combatOver={null} onReturn={vi.fn()} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('shows recoverable thrown weapons on victory and calls the recovery handler', () => {
    const onRecover = vi.fn()
    render(
      <CombatOutcomeOverlay
        combatOver="victory"
        recoverableThrownWeapons={[
          { id: 'thrown-1', weapon: 'Javelin', quantity: 1 },
        ]}
        onRecoverThrownWeapons={onRecover}
        onReturn={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '战斗胜利结算' })
    expect(dialog).toHaveClass('victory')
    expect(within(dialog).getByText('战斗胜利')).toHaveClass('combat-outcome-title')

    const recovery = within(dialog).getByRole('region', { name: '投掷武器回收' })
    expect(recovery).toHaveAttribute('data-testid', 'thrown-recovery-panel')
    expect(within(recovery).getByRole('status')).toHaveTextContent('可回收 Javelin x1')

    fireEvent.click(screen.getByRole('button', { name: '回收投掷武器' }))
    expect(onRecover).toHaveBeenCalledTimes(1)
  })

  it('shows recovered thrown weapons after recovery', () => {
    render(
      <CombatOutcomeOverlay
        combatOver="victory"
        recoveredThrownWeapons={[
          { id: 'thrown-1', weapon: 'Javelin', quantity: 1 },
        ]}
        onReturn={vi.fn()}
      />,
    )

    const recovery = screen.getByRole('region', { name: '投掷武器回收' })
    expect(within(recovery).getByRole('status')).toHaveTextContent('已回收 Javelin x1')
    expect(screen.queryByRole('button', { name: '回收投掷武器' })).not.toBeInTheDocument()
  })

  it('reports recovery errors and busy recovery state', () => {
    render(
      <CombatOutcomeOverlay
        combatOver="victory"
        recoverableThrownWeapons={[
          { id: 'thrown-1', weapon: 'Javelin', quantity: 1 },
        ]}
        recoveryError="回收失败"
        isRecoveringThrownWeapons
        onRecoverThrownWeapons={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const recovery = screen.getByRole('region', { name: '投掷武器回收' })
    expect(within(recovery).getByRole('alert')).toHaveTextContent('回收失败')
    const button = within(recovery).getByRole('button', { name: '回收中...' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })

  it('does not show recovery controls on defeat', () => {
    render(
      <CombatOutcomeOverlay
        combatOver="defeat"
        recoverableThrownWeapons={[
          { id: 'thrown-1', weapon: 'Javelin', quantity: 1 },
        ]}
        onRecoverThrownWeapons={vi.fn()}
        onReturn={vi.fn()}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '战斗失败结算' })
    expect(dialog).toHaveClass('defeat')
    expect(screen.queryByTestId('thrown-recovery-panel')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '回收投掷武器' })).not.toBeInTheDocument()
  })

  it('returns to adventure from the victory overlay', () => {
    const onReturn = vi.fn()

    render(<CombatOutcomeOverlay combatOver="victory" onReturn={onReturn} />)

    const dialog = screen.getByRole('dialog', { name: '战斗胜利结算' })
    expect(within(dialog).getByText('战斗胜利')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /返回冒险/ }))
    expect(onReturn).toHaveBeenCalledTimes(1)
  })
})
