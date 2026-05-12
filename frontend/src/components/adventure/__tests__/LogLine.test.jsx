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

    expect(screen.getByText('分队')).toBeInTheDocument()
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

    expect(screen.getByText('私密')).toBeInTheDocument()
    expect(screen.queryByText('主持')).not.toBeInTheDocument()
  })
})
