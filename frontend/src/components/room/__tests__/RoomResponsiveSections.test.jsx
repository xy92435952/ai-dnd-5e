import { describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'
import RoomActionsPanel from '../RoomActionsPanel'
import RoomAiCompanionsSection from '../RoomAiCompanionsSection'
import RoomMembersGrid from '../RoomMembersGrid'

vi.mock('../../Portrait', () => ({
  default: () => <div data-testid="portrait" />,
}))

vi.mock('../../Crests', () => ({
  classKey: () => 'fighter',
}))

describe('Room responsive section wrappers', () => {
  it('exposes stable wrappers for narrow lobby layouts', () => {
    const { container } = render(
      <>
        <RoomMembersGrid
          members={[
            { user_id: 'me', display_name: 'Me', role: 'host', character_id: 'c1', character_name: 'Fighter', is_online: true },
            { user_id: 'u2', display_name: 'Scout', role: 'player', character_id: 'c2', character_name: 'Rogue', is_online: true },
          ]}
          myUserId="me"
          isHost
          onTransfer={vi.fn()}
          onKick={vi.fn()}
        />
        <RoomAiCompanionsSection
          aiCompanions={[
            { id: 'ai-1', name: 'Bryn', race: 'Human', char_class: 'Cleric', level: 1 },
          ]}
        />
        <RoomActionsPanel
          isHost
          busy={false}
          canStart
          slotsAvailable={0}
          claimedCount={2}
          memberCount={2}
          startReadyCount={2}
          myMember={{ user_id: 'me', character_id: 'c1' }}
          onCreateChar={vi.fn()}
          onToggleStartReady={vi.fn()}
          onFillAi={vi.fn()}
          onStart={vi.fn()}
          onLeave={vi.fn()}
        />
      </>,
    )

    expect(container.querySelector('.room-members-grid')).toBeInTheDocument()
    expect(container.querySelectorAll('.room-member-card')).toHaveLength(2)
    expect(container.querySelector('.room-member-actions')).toBeInTheDocument()
    expect(container.querySelector('.room-ai-grid')).toBeInTheDocument()
    expect(container.querySelector('.room-ai-card')).toBeInTheDocument()
    expect(container.querySelector('.room-actions-panel')).toBeInTheDocument()
    expect(container.querySelectorAll('.room-action-button').length).toBeGreaterThan(0)
  })
})
