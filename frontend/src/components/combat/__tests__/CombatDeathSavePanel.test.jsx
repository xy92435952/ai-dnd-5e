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
    expect(screen.getByRole('button', { name: '无需检定' })).toBeDisabled()
  })
})
