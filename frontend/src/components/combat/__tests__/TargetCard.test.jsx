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
    expect(sheet).toHaveTextContent('Actions')
    expect(sheet).toHaveTextContent('Traits')
    expect(sheet).toHaveTextContent('Tactics')
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
    const perception = within(actions).getByRole('button', { name: '察觉' })
    const investigation = within(actions).getByRole('button', { name: '调查' })
    expect(perception).toHaveAttribute('title', '用察觉检视敌人态势')
    expect(investigation).toHaveAttribute('title', '用调查分析敌人信息')

    fireEvent.click(perception)
    fireEvent.click(investigation)

    expect(onInspect).toHaveBeenCalledWith('perception')
    expect(onInspect).toHaveBeenCalledWith('investigation')
  })

  it('renders a compact target summary strip', () => {
    render(
      <TargetCard
        entity={{
          id: 'enemy-4',
          name: 'Wounded Hobgoblin',
          is_enemy: true,
          hp_current: 6,
          hp_max: 24,
          ac: 16,
          conditions: ['frightened', 'marked', 'slowed'],
          condition_durations: { frightened: 2 },
        }}
        prediction={{ hit_rate: 0.7, advantage: true }}
      />,
    )

    const summary = screen.getByLabelText('Target summary Wounded Hobgoblin')
    expect(summary).toHaveTextContent('Enemy')
    expect(summary).toHaveTextContent('Critical')
    expect(summary).toHaveTextContent('AC 16')
    expect(summary).toHaveTextContent('Hit 70%')
    expect(summary).toHaveTextContent('Frightened')
    expect(summary).toHaveTextContent('Marked')
    expect(summary).toHaveTextContent('+1 cond')
    expect(within(summary).getByTitle('Frightened: Disadvantage while source is visible; cannot willingly move closer. Duration: 2 rounds.')).toBeInTheDocument()
    expect(within(summary).getByTitle('Slowed: Speed and action options are reduced; Dex saves may be penalized.')).toBeInTheDocument()

    const impacts = screen.getByLabelText('Condition impacts Wounded Hobgoblin')
    expect(impacts).toHaveTextContent('Atk disadv')
    expect(impacts).toHaveTextContent('Move block')
    expect(impacts).toHaveTextContent('Focus fire')
    expect(impacts).toHaveTextContent('Action limit')
  })

  it('renders readable attack rule tags for cover and roll state', () => {
    render(
      <TargetCard
        entity={{
          id: 'enemy-5',
          name: 'Guard Behind Pillar',
          is_enemy: true,
          hp_current: 18,
          hp_max: 18,
          ac: 14,
        }}
        prediction={{
          hit_rate: 0.55,
          disadvantage: true,
          target_ac: 14,
          effective_target_ac: 19,
          cover_bonus: 5,
          cover_detail: {
            bonus: 5,
            raw_bonus: 5,
            cells: [{ cell: '3_0', terrain: 'total_cover', weight: 2 }],
          },
          disadvantage_sources: ['attacker poisoned', 'target invisible'],
          modifiers: ['Three-quarters cover'],
        }}
      />,
    )

    const tags = screen.getByLabelText('Attack rule tags Guard Behind Pillar')
    expect(tags).toHaveTextContent('Disadvantage')
    expect(tags).toHaveTextContent('Dis: attacker poisoned +1')
    expect(tags).toHaveTextContent('3/4 cover +5 AC')
    expect(tags).toHaveTextContent('Eff AC 19')
    expect(within(tags).getByTitle(/Roll two d20 and use the lower result/)).toBeInTheDocument()
    expect(within(tags).getByTitle('Disadvantage sources: attacker poisoned / target invisible.')).toBeInTheDocument()
    expect(within(tags).getByTitle('Cover raises AC from 14 to 19 for this attack. Path crosses 3_0 total_cover.')).toBeInTheDocument()
  })
})
