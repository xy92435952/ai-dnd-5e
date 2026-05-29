import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import CombatHudCombatLog from '../CombatHudCombatLog'

describe('CombatHudCombatLog', () => {
  it('renders combat logs as structured rules, dice, narration, and state rows', () => {
    render(
      <CombatHudCombatLog
        logs={[
          {
            id: 'hit-1',
            role: 'player',
            content: 'Tester 劈中训练假人。',
            log_type: 'combat',
            dice_result: {
              attack: {
                d20: 16,
                attack_bonus: 5,
                attack_total: 21,
                target_ac: 13,
                hit: true,
              },
              damage: 8,
            },
            state_changes: ['训练假人 HP 11 -> 3', '动作已用'],
          },
        ]}
      />,
    )

    const entry = screen.getByText('玩家').closest('.log-entry')
    expect(entry).toHaveClass('dmg')
    expect(within(entry).getByText('规则')).toBeInTheDocument()
    expect(within(entry).getByText('命中 · 21 vs AC13')).toBeInTheDocument()
    expect(within(entry).getByText('骰子')).toBeInTheDocument()
    expect(within(entry).getByText('d20 16 +5 = 21')).toBeInTheDocument()
    expect(within(entry).getByText('伤害 8')).toBeInTheDocument()
    expect(within(entry).getByText('叙事')).toBeInTheDocument()
    expect(within(entry).getByText('Tester 劈中训练假人。')).toBeInTheDocument()
    expect(within(entry).getByText('状态')).toBeInTheDocument()
    expect(within(entry).getByText('训练假人 HP 11 -> 3')).toBeInTheDocument()
    expect(within(entry).getByText('动作已用')).toBeInTheDocument()
  })

  it('keeps only the newest eight visible entries', () => {
    render(
      <CombatHudCombatLog
        logs={Array.from({ length: 10 }, (_, index) => ({
          id: `log-${index}`,
          role: 'system',
          content: `日志 ${index}`,
          log_type: 'system',
        }))}
      />,
    )

    expect(screen.queryByText('日志 0')).not.toBeInTheDocument()
    expect(screen.queryByText('日志 1')).not.toBeInTheDocument()
    expect(screen.getByText('日志 2')).toBeInTheDocument()
    expect(screen.getByText('日志 9')).toBeInTheDocument()
  })
})
