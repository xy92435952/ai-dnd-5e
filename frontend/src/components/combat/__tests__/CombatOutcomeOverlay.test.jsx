import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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

    expect(screen.getByTestId('thrown-recovery-panel')).toHaveTextContent('可回收 Javelin x1')
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

    expect(screen.getByTestId('thrown-recovery-panel')).toHaveTextContent('已回收 Javelin x1')
    expect(screen.queryByRole('button', { name: '回收投掷武器' })).not.toBeInTheDocument()
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

    expect(screen.queryByTestId('thrown-recovery-panel')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '回收投掷武器' })).not.toBeInTheDocument()
  })

  it('returns to adventure from the victory overlay', () => {
    const onReturn = vi.fn()

    render(<CombatOutcomeOverlay combatOver="victory" onReturn={onReturn} />)

    expect(screen.getByText('战斗胜利')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /返回冒险/ }))
    expect(onReturn).toHaveBeenCalledTimes(1)
  })
})
