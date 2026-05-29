import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import CombatDeathSavePanel from '../CombatDeathSavePanel'

describe('CombatDeathSavePanel', () => {
  it('shows a roll button for dying characters on their turn', () => {
    const onDeathSave = vi.fn()
    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'dying',
          death_saves: { successes: 1, failures: 2, stable: false },
        }}
        isPlayerTurn
        isProcessing={false}
        onDeathSave={onDeathSave}
      />,
    )

    expect(screen.getByText('濒死豁免')).toBeTruthy()
    const button = screen.getByRole('button', { name: '掷死亡豁免' })
    expect(button).not.toBeDisabled()
    fireEvent.click(button)
    expect(onDeathSave).toHaveBeenCalledTimes(1)
  })

  it('shows stable status without allowing another roll', () => {
    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'stable',
          death_saves: { successes: 3, failures: 0, stable: true },
        }}
        isPlayerTurn
        isProcessing={false}
        onDeathSave={vi.fn()}
      />,
    )

    expect(screen.getByText('已稳定')).toBeTruthy()
    const button = screen.getByRole('button', { name: '无需检定' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', '角色已稳定')
  })

  it('explains why a dying character cannot roll yet', () => {
    const onDeathSave = vi.fn()

    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'dying',
          death_saves: { successes: 0, failures: 1, stable: false },
        }}
        isPlayerTurn={false}
        isProcessing={false}
        onDeathSave={onDeathSave}
      />,
    )

    const button = screen.getByRole('button', { name: '掷死亡豁免' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', '等待你的回合')
    expect(screen.getByText('等待你的回合后进行死亡豁免。')).toBeInTheDocument()

    fireEvent.click(button)
    expect(onDeathSave).not.toHaveBeenCalled()
  })

  it('explains sync-blocked death saves', () => {
    render(
      <CombatDeathSavePanel
        character={{
          hp_current: 0,
          life_state: 'dying',
          death_saves: { successes: 0, failures: 1, stable: false },
        }}
        isPlayerTurn
        isProcessing={false}
        syncBlocked
        onDeathSave={vi.fn()}
      />,
    )

    const button = screen.getByRole('button', { name: '同步中' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', '等待战斗同步恢复')
    expect(screen.getByText('等待战斗同步恢复后进行死亡豁免。')).toBeInTheDocument()
  })
})
