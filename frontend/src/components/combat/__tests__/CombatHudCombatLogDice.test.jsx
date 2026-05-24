import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatHudCombatLog from '../CombatHudCombatLog'

describe('CombatHudCombatLog dice labels', () => {
  it('shows nested attack dice without rendering undefined', () => {
    render(
      <CombatHudCombatLog
        logs={[
          {
            id: 'ai-attack',
            role: 'enemy',
            log_type: 'combat',
            content: 'Combat Goblin attacks HostBlade.',
            dice_result: {
              attack: { d20: 14, attack_bonus: 4, attack_total: 18, target_ac: 13, hit: true },
              damage: 5,
            },
          },
        ]}
      />
    )

    expect(screen.getByText('d20=14')).toBeInTheDocument()
    expect(screen.queryByText(/undefined/)).not.toBeInTheDocument()
  })
})
