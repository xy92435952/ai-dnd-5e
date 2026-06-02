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

    const sheet = screen.getByLabelText('敌人检视 Veiled Stalker')
    expect(sheet).toHaveTextContent('检视')
    expect(sheet).toHaveTextContent('部分')
    expect(sheet).toHaveTextContent('动作')
    expect(sheet).toHaveTextContent('特性')
    expect(sheet).toHaveTextContent('战术')
    expect(within(sheet).getAllByText('未知').length).toBeGreaterThan(0)
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

    const sheet = screen.getByLabelText('敌人检视 Clockwork Sentry')
    expect(sheet).toHaveTextContent('已识别')
    expect(sheet).toHaveTextContent('poison')
    expect(sheet).toHaveTextContent('poisoned')
    expect(sheet).toHaveTextContent('Slam')
    expect(sheet).toHaveTextContent('Immutable Form')
    expect(sheet).toHaveTextContent('Hold the gate line.')
  })

  it('marks inspect-heavy target cards for scroll-safe battlefield overlay layout', () => {
    const { container } = render(
      <TargetCard
        entity={{
          id: 'enemy-scroll',
          name: 'Verbose Tactician',
          is_enemy: true,
          hp_current: 35,
          hp_max: 35,
          ac: 15,
          actions: [
            { name: 'Long Tactical Sequence' },
            { name: 'Second Option' },
          ],
          special_abilities: [
            { name: 'Layered Defensive Routine' },
            { name: 'Reactive Footwork' },
          ],
          tactics: 'Hold the choke point, punish isolated backliners, and retreat behind cover when bloodied.',
          identified: true,
        }}
        prediction={null}
      />,
    )

    const wrap = container.querySelector('.target-card-wrap')
    expect(wrap).toHaveClass('has-inspect')
    expect(container.querySelector('.enemy-inspect-sheet')).toHaveTextContent('Hold the choke point')
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

    const actions = screen.getByLabelText('检视操作 Masked Cultist')
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
          tactical_role: 'skirmisher',
          conditions: ['frightened', 'marked', 'slowed'],
          condition_durations: { frightened: 2 },
        }}
        prediction={{ hit_rate: 0.7, advantage: true }}
      />,
    )

    const summary = screen.getByLabelText('目标摘要 Wounded Hobgoblin')
    expect(summary).toHaveTextContent('敌人')
    expect(summary).toHaveTextContent('危急')
    expect(summary).toHaveTextContent('游击')
    expect(summary).toHaveTextContent('AC 16')
    expect(summary).toHaveTextContent('命中 70%')
    expect(summary).toHaveTextContent('恐慌')
    expect(summary).toHaveTextContent('标记')
    expect(summary).toHaveTextContent('+1 状态')
    expect(within(summary).getByTitle('战术定位：游击。倾向攻击边缘或后排，并在安全时撤步拉开距离。')).toBeInTheDocument()
    expect(within(summary).getByTitle('恐慌：来源可见时攻击骰和属性检定处于劣势；不能主动靠近来源。 持续：2 轮。')).toBeInTheDocument()
    expect(within(summary).getByTitle('迟缓：速度和动作选项减少；敏捷豁免可能受罚。')).toBeInTheDocument()

    const impacts = screen.getByLabelText('状态影响 Wounded Hobgoblin')
    expect(impacts).toHaveTextContent('攻击劣势')
    expect(impacts).toHaveTextContent('移动受限')
    expect(impacts).toHaveTextContent('集火标记')
    expect(impacts).toHaveTextContent('动作受限')
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

    const tags = screen.getByLabelText('攻击规则标签 Guard Behind Pillar')
    expect(tags).toHaveTextContent('劣势')
    expect(tags).toHaveTextContent('劣势: 攻击者中毒 +1')
    expect(tags).toHaveTextContent('3/4 掩护 +5 AC')
    expect(tags).toHaveTextContent('有效 AC 19')
    expect(within(tags).getByTitle(/掷两个 d20，取较低结果/)).toBeInTheDocument()
    expect(within(tags).getByTitle('劣势来源：攻击者中毒 / 目标隐形。')).toBeInTheDocument()
    expect(within(tags).getByTitle('掩护使本次攻击的 AC 从 14 提升到 19。路径经过 3_0 total_cover。')).toBeInTheDocument()
  })
})
