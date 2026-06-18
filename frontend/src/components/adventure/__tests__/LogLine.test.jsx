import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import LogLine from '../LogLine'


describe('LogLine', () => {
  it('shows a group visibility badge for group-scoped DM logs', () => {
    render(<LogLine entry={{
      role: 'dm',
      content: '后巷门锁弹开。',
      visibility: { scope: 'group', group_id: 'alley', visible_to_user_ids: ['u1'] },
    }} />)

    expect(screen.getByRole('listitem', { name: '日志 DM' })).toHaveClass('dialogue-log-item', 'dm')
    expect(screen.getByText('分队')).toHaveClass('dialogue-log-visibility', 'group')
    expect(screen.getByText('后巷门锁弹开。')).toBeInTheDocument()
  })

  it('shows a private visibility badge for private DM logs', () => {
    render(<LogLine entry={{
      role: 'dm',
      content: '只有你注意到暗号。',
      visibility: { scope: 'private', visible_to_user_ids: ['u1'] },
    }} />)

    expect(screen.getByText('私密')).toBeInTheDocument()
  })

  it('does not show moderator labels because room host is still a player', () => {
    render(<LogLine entry={{
      role: 'dm',
      content: '只有你注意到暗号。',
      visibility: { scope: 'private', visible_to_user_ids: ['u1'] },
    }} />)

    expect(screen.getByText('私密')).toHaveClass('dialogue-log-visibility', 'private')
    expect(screen.queryByText('主持')).not.toBeInTheDocument()
  })

  it('shows companion speaker names when companion reactions are logged', () => {
    render(<LogLine entry={{
      role: 'companion',
      speaker: '艾莉',
      content: '我盯着后门。',
    }} />)

    expect(screen.getByRole('listitem', { name: '日志 队友 艾莉' })).toHaveClass('dialogue-log-item', 'companion')
    expect(screen.getByText(/艾莉/)).toHaveClass('dialogue-log-line-companion')
    expect(screen.getByText(/我盯着后门/)).toBeInTheDocument()
  })

  it('marks long DM log lines with the wrapping layout class', () => {
    render(<LogLine entry={{
      role: 'dm',
      content: `${'obsidian-corridor-'.repeat(28)}\n第二段继续说明。`,
    }} />)

    const line = screen.getByText(/obsidian-corridor/)
    expect(line).toHaveClass('dialogue-log-line', 'dialogue-log-line-dm')
  })

  it('uses stable role classes for player, dice, and system logs', () => {
    const { rerender } = render(<LogLine entry={{
      role: 'player',
      content: '我靠近石门。',
    }} />)

    expect(screen.getByRole('listitem', { name: '日志 玩家' })).toHaveClass('dialogue-log-item', 'player')
    expect(screen.getByText(/我靠近石门/)).toHaveClass('dialogue-log-line-player')

    rerender(<LogLine entry={{
      role: 'dice',
      content: 'd20 = 17',
    }} />)

    expect(screen.getByRole('listitem', { name: '日志 骰子' })).toHaveClass('dialogue-log-item', 'dice')
    expect(screen.getByText(/d20 = 17/)).toHaveClass('dialogue-log-line-dice')

    rerender(<LogLine entry={{
      role: 'system',
      content: '自动保存完成。',
    }} />)

    expect(screen.getByRole('listitem', { name: '日志 系统' })).toHaveClass('dialogue-log-item', 'system')
    expect(screen.getByText('自动保存完成。')).toHaveClass('dialogue-log-line-system')
  })
})
