import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatHudSlots from '../CombatHudSlots'

describe('CombatHudSlots', () => {
  it('uses the controlled character concentration over the session player', () => {
    render(
      <CombatHudSlots
        session={{
          player: {
            concentration: 'Shield of Faith',
            derived: { spell_slots_max: { '1st': 2 } },
          },
        }}
        character={{
          concentration: 'Bless',
          derived: { spell_slots_max: { '1st': 3 } },
        }}
        playerSpellSlots={{ '1st': 1 }}
      />,
    )

    expect(screen.getByText('Bless')).toBeTruthy()
    expect(screen.queryByText('Shield of Faith')).toBeNull()
  })

  it('uses controlled character slot max for multiplayer HUD gems', () => {
    const { container } = render(
      <CombatHudSlots
        session={{
          player: {
            derived: { spell_slots_max: { '1st': 1 } },
          },
        }}
        character={{
          derived: { spell_slots_max: { '1st': 3 } },
        }}
        playerSpellSlots={{ '1st': 1 }}
      />,
    )

    expect(container.querySelectorAll('.slot-gem')).toHaveLength(3)
    expect(container.querySelectorAll('.slot-gem.used')).toHaveLength(2)
  })
})
