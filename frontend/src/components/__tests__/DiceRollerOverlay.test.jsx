import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { normalizeDiceRollResult } from '../DiceRollerOverlay'
import DiceRollerOverlay from '../DiceRollerOverlay'
import { useGameStore } from '../../store/gameStore'

describe('normalizeDiceRollResult', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    useGameStore.setState({
      diceRoll: null,
      dicePrompt: null,
      combatActive: false,
    })
  })

  it('expands DiceBox grouped rollsArray into raw dice values', () => {
    const result = normalizeDiceRollResult([
      {
        value: 22,
        qty: 2,
        rollsArray: [
          { sides: 20, value: 18 },
          { sides: 20, value: 4 },
        ],
      },
    ], 20, 2)

    expect(result).toEqual({ total: 22, rolls: [18, 4] })
  })

  it('uses child roll values before grouped value totals', () => {
    const result = normalizeDiceRollResult([
      {
        value: 12,
        rolls: {
          first: { value: 8 },
          second: { value: 4 },
        },
      },
    ], 20, 2)

    expect(result).toEqual({ total: 12, rolls: [8, 4] })
  })

  it('pads missing dice with bounded fallback rolls', () => {
    vi.spyOn(Math, 'random')
      .mockReturnValueOnce(0)
      .mockReturnValueOnce(0.99)

    const result = normalizeDiceRollResult(null, 20, 2)

    expect(result).toEqual({ total: 21, rolls: [1, 20] })
  })

  it('renders result chrome through stable classes while preserving dynamic result color', async () => {
    useGameStore.setState({ combatActive: true })

    const { container } = render(<DiceRollerOverlay />)
    useGameStore.getState().showDice({ faces: 20, result: 20, label: 'Attack roll' })

    const resultNumber = await screen.findByText('20')
    expect(resultNumber).toHaveClass('dice-result-number')
    const resultStack = resultNumber.closest('.dice-result-stack')
    expect(resultStack).toHaveAttribute('style', '--dice-result-color: #22c55e;')

    expect(screen.getByText('Attack roll')).toHaveClass('dice-result-label')
    expect(screen.getByText('Attack roll')).toHaveAttribute('data-combat', 'true')
    expect(container.querySelector('.dice-result-badge')).toHaveAttribute('data-outcome', 'crit')
    expect(container.querySelector('.dice-result-badge-text')).toHaveTextContent('大成功')
    expect(screen.getByText('点击任意处关闭')).toHaveClass('dice-result-dismiss-hint')
  })
  it('renders prompt shell chrome through stable classes and keeps rolling state visible after throw', async () => {
    useGameStore.setState({ combatActive: true })

    const { container } = render(<DiceRollerOverlay />)
    const persistent = container.querySelector('#dice-roller-persistent')
    expect(persistent).toHaveClass('dice-roller-persistent')
    expect(persistent).toHaveAttribute('data-visible', 'false')

    useGameStore.getState().showDicePrompt({ faces: 12, count: 2 })

    await waitFor(() => {
      expect(container.querySelector('.dice-overlay-shell')).toHaveAttribute('data-phase', 'waiting')
    })
    expect(persistent).toHaveAttribute('data-visible', 'true')
    expect(container.querySelector('.dice-overlay-shell')).toHaveAttribute('data-combat', 'true')
    expect(container.querySelector('.dice-surface')).toHaveAttribute('data-phase', 'waiting')
    expect(container.querySelector('.dice-throw-panel')).toBeInTheDocument()

    const throwButton = container.querySelector('.dice-throw-button')
    expect(throwButton).toHaveAttribute('data-combat', 'true')
    expect(throwButton).not.toHaveAttribute('style')
    expect(container.querySelector('.dice-throw-helper')).toHaveAttribute('data-combat', 'true')

    fireEvent.click(throwButton)

    await waitFor(() => {
      expect(container.querySelector('.dice-rolling-copy')).toHaveAttribute('data-combat', 'true')
    })
  })
})
