import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import CombatHudCombatLog from '../CombatHudCombatLog'

describe('CombatHudCombatLog', () => {
  it('renders a compact latest combat summary above the visible log entries', () => {
    const { container } = render(
      <CombatHudCombatLog
        logs={[
          ...Array.from({ length: 8 }, (_, index) => ({
            id: `old-${index}`,
            role: 'system',
            content: `old log ${index}`,
            log_type: 'system',
          })),
          {
            id: 'latest-hit',
            role: 'player',
            content: 'Latest strike lands.',
            log_type: 'combat',
            dice_result: {
              attack: {
                d20: 17,
                attack_bonus: 6,
                attack_total: 23,
                target_ac: 14,
                hit: true,
              },
              damage: 9,
            },
            state_changes: ['Goblin HP 12 -> 3', 'Action spent'],
          },
        ]}
      />,
    )

    const summary = container.querySelector('.combat-log-summary')
    expect(summary).toBeTruthy()
    expect(summary).toHaveClass('dmg')
    expect(summary).toHaveTextContent('Latest strike lands.')
    expect(container.querySelector('.combat-log-summary-feedback.hit')).toBeTruthy()
    expect(container.querySelectorAll('.combat-log-summary-sections i').length).toBeGreaterThan(0)
    expect(container.querySelector('.combat-log-summary-count')).toHaveTextContent('8/9')
  })

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
    expect(entry).toHaveClass('feedback-hit')
    expect(within(entry).getByLabelText('战斗反馈')).toBeInTheDocument()
    expect(within(entry).getByText('命中')).toHaveClass('log-feedback', 'hit')
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

  it('renders multiple outcome feedback badges on one log entry', () => {
    render(
      <CombatHudCombatLog
        logs={[
          {
            id: 'save-1',
            role: 'system',
            content: '集中被打断。',
            log_type: 'dice',
            dice_result: { save_result: { success: false } },
            state_changes: ['专注中断：祝福术'],
          },
        ]}
      />,
    )

    const entry = screen.getByText('系统').closest('.log-entry')
    expect(entry).toHaveClass('feedback-save-failure')
    expect(entry).toHaveClass('feedback-concentration-break')
    expect(within(entry).getByText('豁免失败')).toHaveClass('log-feedback', 'save-failure')
    expect(within(entry).getByText('专注中断')).toHaveClass('log-feedback', 'concentration-break')
  })

  it('renders defender interception as a visible combat feedback badge', () => {
    render(
      <CombatHudCombatLog
        logs={[
          {
            id: 'guard-1',
            role: 'player',
            content: '护卫以盾缘压低了你的剑锋。',
            log_type: 'combat',
            dice_result: {
              attack: {
                d20: 11,
                attack_bonus: 5,
                attack_total: 16,
                target_ac: 16,
                hit: false,
                defender_interception: {
                  defender_name: 'Shield Guard',
                  protected_target_name: 'Cult Priest',
                },
              },
            },
          },
        ]}
      />,
    )

    const entry = screen.getByText('玩家').closest('.log-entry')
    expect(entry).toHaveClass('feedback-defender-interception')
    expect(within(entry).getByText('护卫干扰')).toHaveClass('log-feedback', 'defender-interception')
    expect(within(entry).getByText('Shield Guard 护卫干扰：保护 Cult Priest，本次攻击劣势')).toBeInTheDocument()
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
