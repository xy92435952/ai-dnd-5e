import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import CombatHudIntentSummary from '../CombatHudIntentSummary'

describe('CombatHudIntentSummary', () => {
  it('summarizes the player turn and prompts for a needed target', () => {
    render(
      <CombatHudIntentSummary
        turnState={{
          action_used: false,
          bonus_action_used: true,
          reaction_used: false,
          movement_used: 2,
          movement_max: 6,
        }}
        skillBar={[{ k: 'atk', label: '攻击', kind: 'attack', available: true }]}
        isPlayerTurn
      />,
    )

    const summary = screen.getByLabelText('战斗意图摘要')
    expect(summary).toHaveClass('combat-intent-summary')
    expect(summary).toHaveTextContent('选择目标')
    expect(summary).toHaveTextContent('攻击或法术需要目标')

    const economy = screen.getByLabelText('本回合资源')
    expect(within(economy).getByText('动作')).toBeInTheDocument()
    expect(within(economy).getAllByText('可用').length).toBeGreaterThan(0)
    expect(within(economy).getByText('附赠')).toBeInTheDocument()
    expect(within(economy).getByText('已用')).toBeInTheDocument()
    expect(within(economy).queryByText('2/6')).not.toBeInTheDocument()
    expect(within(economy).getByText('4/6')).toBeInTheDocument()

    const target = screen.getByLabelText('当前战斗目标')
    expect(target).toHaveClass('empty')
    expect(target).toHaveTextContent('未选择')
    expect(target).toHaveTextContent('先点选战场单位')
  })

  it('keeps selected target, weapon mode, hit chance, and rule chips in one scan area', () => {
    const { container } = render(
      <CombatHudIntentSummary
        turnState={{
          action_used: false,
          bonus_action_used: false,
          reaction_used: false,
          movement_used: 0,
          movement_max: 6,
        }}
        skillBar={[{ k: 'atk', label: '攻击', kind: 'attack', available: true }]}
        selectedTarget="enemy-1"
        entities={{
          'enemy-1': {
            id: 'enemy-1',
            name: 'Guard Behind Pillar',
            is_enemy: true,
            hp_current: 18,
            hp_max: 24,
            ac: 14,
            conditions: ['restrained'],
            condition_durations: { restrained: 1 },
          },
        }}
        prediction={{
          hit_rate: 0.55,
          disadvantage: true,
          target_ac: 14,
          effective_target_ac: 19,
          cover_bonus: 5,
          cover_detail: { bonus: 5, raw_bonus: 5 },
        }}
        isPlayerTurn
        isRanged
        selectedWeaponName="Longbow"
      />,
    )

    const summary = screen.getByLabelText('战斗意图摘要')
    expect(summary).toHaveTextContent('目标锁定')
    expect(summary).toHaveTextContent('远程 / Longbow')
    expect(summary).toHaveTextContent('Guard Behind Pillar')
    expect(summary).toHaveTextContent('敌方 / HP 18/24 / AC 14 / 命中 55%')
    expect(container.querySelector('.combat-intent-rules')).toBeTruthy()
    expect(container.querySelectorAll('.combat-intent-rules span').length).toBeGreaterThan(0)
  })

  it('prioritizes sync-blocked guidance over normal action prompts', () => {
    render(
      <CombatHudIntentSummary
        turnState={{ action_used: false, movement_used: 0, movement_max: 6 }}
        skillBar={[{ k: 'atk', label: '攻击', kind: 'attack', available: true }]}
        isPlayerTurn
        syncBlocked
      />,
    )

    const summary = screen.getByLabelText('战斗意图摘要')
    expect(summary).toHaveTextContent('同步暂停')
    expect(summary).toHaveTextContent('等待房间状态恢复')
    expect(summary).not.toHaveTextContent('选择目标')
  })

  it('does not treat the generic spell picker as a selected-target requirement', () => {
    render(
      <CombatHudIntentSummary
        turnState={{ action_used: false, movement_used: 0, movement_max: 6 }}
        skillBar={[{ k: 'spell', label: '法术', kind: 'spell', available: true }]}
        isPlayerTurn
      />,
    )

    const summary = screen.getByLabelText('战斗意图摘要')
    expect(summary).toHaveTextContent('可行动')
    expect(summary).not.toHaveTextContent('攻击或法术需要目标')
    expect(summary).toHaveTextContent('可直接执行非目标动作')
  })
})
