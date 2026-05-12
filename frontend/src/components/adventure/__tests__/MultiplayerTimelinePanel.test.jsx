import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import MultiplayerTimelinePanel from '../MultiplayerTimelinePanel'

describe('MultiplayerTimelinePanel', () => {
  it('renders visible multiplayer timeline lanes without host-only labels', () => {
    const room = {
      host_user_id: 'u1',
      active_group_id: 'alley',
      party_groups: [{ id: 'alley', name: '后巷组', member_user_ids: ['u1'] }],
    }
    const logs = [
      { role: 'dm', content: '全队听见钟声。', visibility: { scope: 'party' } },
      { role: 'dm', content: '后巷门锁弹开。', visibility: { scope: 'group', group_id: 'alley', visible_to_user_ids: ['u1'] } },
      { role: 'dm', content: '只有你注意到暗号。', visibility: { scope: 'private', visible_to_user_ids: ['u1'] } },
    ]

    render(<MultiplayerTimelinePanel room={room} logs={logs} myUserId="u1" />)

    expect(screen.getByText('分队时间线')).toBeInTheDocument()
    expect(screen.getByText('公共 1')).toBeInTheDocument()
    expect(screen.getByText('我的分队 1')).toBeInTheDocument()
    expect(screen.getByText('私密 1')).toBeInTheDocument()
    expect(screen.getByText('全队听见钟声。')).toBeInTheDocument()
    expect(screen.getByText('后巷门锁弹开。')).toBeInTheDocument()
    expect(screen.getByText('只有你注意到暗号。')).toBeInTheDocument()
    expect(screen.queryByText('主持')).not.toBeInTheDocument()
  })

  it('returns nothing outside multiplayer room context', () => {
    const { container } = render(<MultiplayerTimelinePanel room={null} logs={[]} myUserId="u1" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows active camera by group name when focus is another group', () => {
    const room = {
      active_group_id: 'tavern',
      party_groups: [
        { id: 'alley', name: '后巷组', member_user_ids: ['u1'] },
        { id: 'tavern', name: '酒馆组', member_user_ids: ['u2'] },
      ],
    }

    render(<MultiplayerTimelinePanel room={room} logs={[]} myUserId="u1" />)

    expect(screen.getByText('当前镜头：酒馆组')).toBeInTheDocument()
  })
})
