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

    const panel = screen.getByRole('region', { name: '战斗日志' })
    const summary = within(panel).getByRole('status', { name: '最近战报摘要' })
    expect(summary).toHaveClass('dmg')
    expect(summary).toHaveTextContent('Latest strike lands.')
    expect(container.querySelector('.combat-log-summary-feedback.hit')).toBeTruthy()
    expect(within(summary).getAllByRole('listitem').length).toBeGreaterThan(0)
    expect(container.querySelector('.combat-log-summary-count')).toHaveTextContent('8/9')
    expect(within(panel).getByRole('log', { name: '最近战斗日志' })).toBeInTheDocument()
  })

  it('surfaces AoE and multi-target impact chips in the latest combat summary', () => {
    render(
      <CombatHudCombatLog
        logs={[
          {
            id: 'fireball-1',
            role: 'player',
            content: 'Fireball blossoms across the chamber.',
            log_type: 'combat',
            impact_summary: [
              { key: 'targets', label: '影响 3 个', tone: 'info', title: 'Goblin、Cultist、Companion' },
              { key: 'damage', label: '总伤害 37', tone: 'bad', title: 'Goblin、Cultist、Companion' },
              { key: 'allies', label: '友方 1', tone: 'warning', title: 'Companion' },
              { key: 'save-failed', label: '豁免失败 2', tone: 'bad', title: 'Goblin、Cultist' },
            ],
            state_changes: [
              'Goblin HP 20 -> 0',
              'Cultist HP 16 -> 2',
              'Companion HP 24 -> 16',
            ],
          },
        ]}
      />,
    )

    const summary = screen.getByRole('status', { name: '最近战报摘要' })
    const impacts = within(summary).getByRole('list', { name: '影响摘要' })
    expect(within(impacts).getByRole('listitem', { name: '影响 3 个：Goblin、Cultist、Companion' })).toHaveClass('info')
    expect(within(impacts).getByRole('listitem', { name: '总伤害 37：Goblin、Cultist、Companion' })).toHaveClass('bad')
    expect(within(impacts).getByRole('listitem', { name: '友方 1：Companion' })).toHaveClass('warning')
    expect(within(impacts).getByRole('listitem', { name: '豁免失败 2：Goblin、Cultist' })).toHaveClass('bad')
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

    const entry = screen.getByRole('listitem', { name: '战斗日志 玩家' })
    expect(entry).toHaveClass('dmg')
    expect(entry).toHaveClass('feedback-hit')
    const feedback = within(entry).getByRole('list', { name: '战斗反馈' })
    expect(within(feedback).getByRole('listitem', { name: '命中' })).toHaveClass('log-feedback', 'hit')
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

    const entry = screen.getByRole('listitem', { name: '战斗日志 系统' })
    expect(entry).toHaveClass('feedback-save-failure')
    expect(entry).toHaveClass('feedback-concentration-break')
    const feedback = within(entry).getByRole('list', { name: '战斗反馈' })
    expect(within(feedback).getByRole('listitem', { name: '豁免失败' })).toHaveClass('log-feedback', 'save-failure')
    expect(within(feedback).getByRole('listitem', { name: '专注中断' })).toHaveClass('log-feedback', 'concentration-break')
  })

  it('renders attack disadvantage sources in combat log rules', () => {
    render(
      <CombatHudCombatLog
        logs={[
          {
            id: 'dodge-miss-1',
            role: 'enemy',
            content: 'Dodge Pressure Duelist misses the guarded hero.',
            log_type: 'combat',
            dice_result: {
              attack: {
                d20: 6,
                attack_bonus: 5,
                attack_total: 11,
                target_ac: 16,
                hit: false,
                roll_state: 'disadvantage',
                disadvantage: true,
                disadvantage_sources: ['target dodging'],
              },
            },
          },
        ]}
      />,
    )

    const entry = screen.getByRole('listitem', { name: '战斗日志 敌人' })
    expect(within(entry).getByText('劣势')).toBeInTheDocument()
    expect(within(entry).getByText('劣势: 目标闪避')).toBeInTheDocument()
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

    const entry = screen.getByRole('listitem', { name: '战斗日志 玩家' })
    expect(entry).toHaveClass('feedback-defender-interception')
    expect(within(entry).getByRole('listitem', { name: '护卫干扰' })).toHaveClass('log-feedback', 'defender-interception')
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

    const log = screen.getByRole('log', { name: '最近战斗日志' })
    expect(within(log).queryByText('日志 0')).not.toBeInTheDocument()
    expect(within(log).queryByText('日志 1')).not.toBeInTheDocument()
    expect(within(log).getByText('日志 2')).toBeInTheDocument()
    expect(within(log).getByText('日志 9')).toBeInTheDocument()
  })
})
