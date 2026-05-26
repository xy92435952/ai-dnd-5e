import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatHudPortrait from '../CombatHudPortrait'

describe('CombatHudPortrait', () => {
  it('renders effective top-level hp max when exhaustion reduces the max', () => {
    render(
      <CombatHudPortrait
        session={{
          player: {
            name: 'Tired Hero',
            hp_current: 6,
            hp_max: 6,
            derived: { hp_max: 12, ac: 16, initiative: 2 },
            conditions: [],
          },
        }}
        playerClass="Fighter"
        playerLevel={1}
        turnState={{ movement_max: 6, movement_used: 0 }}
      />,
    )

    expect(screen.getByText('6')).toBeTruthy()
    expect(screen.getByText('/ 6', { exact: false })).toBeTruthy()
  })
})
