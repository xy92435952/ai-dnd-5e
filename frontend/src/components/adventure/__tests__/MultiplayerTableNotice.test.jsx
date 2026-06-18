import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import MultiplayerTableNotice from '../MultiplayerTableNotice'

const room = {
  is_multiplayer: true,
  active_group_id: 'tavern',
  members: [
    { user_id: 'me', display_name: '我' },
    { user_id: 'u2', display_name: '凯伦' },
  ],
  party_groups: [
    { id: 'alley', name: '后巷组', member_user_ids: ['me'] },
    { id: 'tavern', name: '酒馆组', member_user_ids: ['u2'] },
  ],
  pending_actions_by_group: {
    tavern: [{ user_id: 'u2', display_name: '凯伦', text: '我继续套老板的话。' }],
  },
  group_readiness: {
    tavern: { u2: 'ready' },
  },
}

describe('MultiplayerTableNotice', () => {
  it('shows table coordination reason from the current DM segment', () => {
    render(
      <MultiplayerTableNotice
        room={room}
        myUserId="me"
        currentSeg={{
          role: 'dm',
          text: 'DM 将镜头切到酒馆组。',
          table_reason: '酒馆组已有待处理行动，玩家明确要求切镜头。',
          table_decision: {
            decision: 'switch_focus',
            reason_code: 'switch_focus',
            target_group_id: 'tavern',
          },
        }}
        logs={[]}
      />
    )

    const notice = screen.getByRole('region', { name: '多人调度提示' })
    expect(notice).toHaveClass('multiplayer-table-notice')
    expect(within(notice).getByText('DM 调度原因')).toBeInTheDocument()
    expect(within(notice).getByText('切换镜头')).toBeInTheDocument()
    expect(within(notice).getByText('酒馆组已有待处理行动，玩家明确要求切镜头。')).toBeInTheDocument()
    expect(within(notice).getByText('当前镜头：酒馆组')).toBeInTheDocument()
    expect(within(notice).getByText('下一处理：酒馆组 · 1 条待处理 · 全员已确认')).toBeInTheDocument()
    expect(within(notice).queryByText('主持')).not.toBeInTheDocument()
  })

  it('falls back to the latest visible log reason after theatre playback', () => {
    render(
      <MultiplayerTableNotice
        room={room}
        myUserId="me"
        currentSeg={null}
        logs={[
          { role: 'dm', content: '旧场景', table_reason: '旧原因' },
          { role: 'dm', content: '切镜头', table_reason: '等待后巷组补充行动。' },
        ]}
      />
    )

    const notice = screen.getByRole('region', { name: '多人调度提示' })
    expect(within(notice).getByText('等待后巷组补充行动。')).toBeInTheDocument()
  })

  it('stays hidden when there is no coordination reason or ready group', () => {
    const { container } = render(
      <MultiplayerTableNotice
        room={{
          ...room,
          pending_actions_by_group: {},
          group_readiness: {},
        }}
        myUserId="me"
        currentSeg={null}
        logs={[]}
      />
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('stays hidden for single-player sessions even if stale table metadata exists', () => {
    const { container } = render(
      <MultiplayerTableNotice
        room={{ ...room, is_multiplayer: false }}
        myUserId="me"
        currentSeg={{
          role: 'dm',
          text: 'DM 将镜头切到酒馆组。',
          table_reason: '旧的多人调度原因不应污染单人体验。',
          table_decision: { reason_code: 'switch_focus' },
        }}
        logs={[]}
      />
    )

    expect(container).toBeEmptyDOMElement()
  })
})
