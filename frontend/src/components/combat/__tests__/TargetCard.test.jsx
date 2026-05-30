import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import TargetCard from '../TargetCard'

describe('TargetCard', () => {
  it('renders enemy inspect details with unknown gated stats', () => {
    render(
      <TargetCard
        entity={{
          id: 'enemy-1',
          name: 'Veiled Stalker',
          is_enemy: true,
          hp_current: 11,
          hp_max: 20,
          ac: 14,
          cr: '2',
          speed: 40,
          actions: [{ name: 'Shadow Strike' }],
        }}
        prediction={null}
      />,
    )

    const sheet = screen.getByLabelText('Enemy inspect Veiled Stalker')
    expect(sheet).toHaveTextContent('INSPECT')
    expect(sheet).toHaveTextContent('PARTIAL')
    expect(within(sheet).getAllByText('Unknown').length).toBeGreaterThan(0)
    expect(sheet).not.toHaveTextContent('Shadow Strike')
  })

  it('renders revealed enemy stats and actions', () => {
    render(
      <TargetCard
        entity={{
          id: 'enemy-2',
          name: 'Clockwork Sentry',
          is_enemy: true,
          hp_current: 22,
          hp_max: 22,
          ac: 14,
          cr: '1',
          speed: 30,
          resistances: ['poison'],
          condition_immunities: ['poisoned'],
          actions: [{ name: 'Slam' }],
          special_abilities: [{ name: 'Immutable Form' }],
          tactics: 'Hold the gate line.',
          identified: true,
        }}
        prediction={null}
      />,
    )

    const sheet = screen.getByLabelText('Enemy inspect Clockwork Sentry')
    expect(sheet).toHaveTextContent('IDENTIFIED')
    expect(sheet).toHaveTextContent('poison')
    expect(sheet).toHaveTextContent('poisoned')
    expect(sheet).toHaveTextContent('Slam')
    expect(sheet).toHaveTextContent('Immutable Form')
    expect(sheet).toHaveTextContent('Hold the gate line.')
  })

  it('offers perception and investigation inspect actions when provided', () => {
    const onInspect = vi.fn()
    render(
      <TargetCard
        entity={{
          id: 'enemy-3',
          name: 'Masked Cultist',
          is_enemy: true,
          hp_current: 9,
          hp_max: 9,
          ac: 12,
        }}
        prediction={null}
        canInspect
        onInspect={onInspect}
      />,
    )

    const actions = screen.getByLabelText('Inspect actions Masked Cultist')
    fireEvent.click(within(actions).getByRole('button', { name: 'PER' }))
    fireEvent.click(within(actions).getByRole('button', { name: 'INV' }))

    expect(onInspect).toHaveBeenCalledWith('perception')
    expect(onInspect).toHaveBeenCalledWith('investigation')
  })
})
