import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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

  it('offers a no-action control to end active concentration', () => {
    const onEndConcentration = vi.fn()
    render(
      <CombatHudSlots
        session={{ player: { derived: { spell_slots_max: {} } } }}
        character={{ concentration: 'Web', derived: { spell_slots_max: {} } }}
        playerSpellSlots={{}}
        onEndConcentration={onEndConcentration}
      />,
    )

    const button = screen.getByRole('button', { name: '结束专注 Web' })
    fireEvent.click(button)

    expect(onEndConcentration).toHaveBeenCalledTimes(1)
  })

  it('formats ready spell concentration holds for the HUD', () => {
    render(
      <CombatHudSlots
        session={{ player: { derived: { spell_slots_max: {} } } }}
        character={{ concentration: '准备法术: Magic Missile', derived: { spell_slots_max: {} } }}
        playerSpellSlots={{}}
        onEndConcentration={vi.fn()}
      />,
    )

    expect(screen.getByText('准备法术 Magic Missile')).toBeTruthy()
    expect(screen.queryByText('准备法术: Magic Missile')).toBeNull()
    expect(screen.getByRole('button', { name: '结束专注 准备法术 Magic Missile' })).toBeTruthy()
  })

  it('disables the concentration control while combat is syncing or processing', () => {
    const onEndConcentration = vi.fn()
    render(
      <CombatHudSlots
        session={{ player: { derived: { spell_slots_max: {} } } }}
        character={{ concentration: 'Web', derived: { spell_slots_max: {} } }}
        playerSpellSlots={{}}
        disabled
        onEndConcentration={onEndConcentration}
      />,
    )

    const button = screen.getByRole('button', { name: '结束专注 Web' })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(onEndConcentration).not.toHaveBeenCalled()
  })
})
