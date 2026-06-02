import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import CombatHud from '../CombatHud'

const player = {
  id: 'hero-1',
  name: 'Alden',
  char_class: 'Fighter',
  hp_current: 12,
  hp_max: 12,
  derived: {
    hp_max: 12,
    ac: 16,
    initiative: 2,
    spell_slots_max: { '1st': 2 },
  },
  equipment: {
    weapons: [],
    gear: [],
  },
}

function renderHud(overrides = {}) {
  const props = {
    session: {
      session_id: 'sess-1',
      player,
      companions: [],
    },
    playerClass: 'Fighter',
    playerSubclass: '',
    playerLevel: 3,
    turnState: {
      action_used: false,
      bonus_action_used: false,
      reaction_used: false,
      movement_used: 1,
      movement_max: 6,
    },
    skillBar: [
      { k: 'dodge', label: 'Dodge', glyph: 'D', cost: 'Action', key: '1', kind: 'action', available: true },
    ],
    selectedTarget: null,
    entities: {},
    prediction: null,
    logs: [{ role: 'dm', content: 'Round begins.' }],
    logsEndRef: { current: null },
    playerSpellSlots: { '1st': 2 },
    controlledCharacter: player,
    isProcessing: false,
    isPlayerTurn: true,
    syncBlocked: false,
    moveMode: false,
    isRanged: false,
    selectedWeaponName: '',
    onSessionChange: vi.fn(),
    onTurnStateChange: vi.fn(),
    onError: vi.fn(),
    onSkillClick: vi.fn(),
    onDeathSave: vi.fn(),
    onEndTurn: vi.fn(),
    onToggleMove: vi.fn(),
    onToggleRanged: vi.fn(),
    onSelectedWeaponChange: vi.fn(),
    onOpenCharacter: vi.fn(),
    onReturnAdventure: vi.fn(),
    onForceEndCombat: vi.fn(),
    ...overrides,
  }
  const result = render(<CombatHud {...props} />)
  return { ...result, props }
}

describe('CombatHud', () => {
  it('exposes responsive HUD regions while preserving command clicks', () => {
    const { container, props } = renderHud()

    const hud = screen.getByRole('region', { name: 'Combat command HUD' })
    expect(hud).toHaveClass('combat-hud')
    expect(container.querySelector('.combat-hud-left')).toBeTruthy()
    expect(container.querySelector('.combat-hud-center')).toBeTruthy()
    expect(container.querySelector('.combat-hud-right')).toBeTruthy()
    expect(container.querySelector('.combat-turn-controls')).toBeTruthy()
    expect(container.querySelector('.combat-turn-action-grid')).toBeTruthy()

    fireEvent.click(container.querySelector('.slot-key.action'))
    fireEvent.click(container.querySelector('.end-turn-mega'))

    expect(props.onSkillClick).toHaveBeenCalledWith(expect.objectContaining({ k: 'dodge' }))
    expect(props.onEndTurn).toHaveBeenCalledTimes(1)
  })
})
