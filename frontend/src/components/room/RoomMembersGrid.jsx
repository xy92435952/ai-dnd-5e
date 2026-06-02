import Portrait from '../Portrait'
import { classKey } from '../Crests'

export default function RoomMembersGrid({
  members,
  myUserId,
  isHost,
  roomVotes = [],
  disabledHostControls = false,
  disabledReason = '',
  onTransfer,
  onKick,
}) {
  return (
    <div className="room-members-grid">
      {(members || []).map((member) => {
        const vote = (roomVotes || []).find(item => (
          item.type === 'kick'
          && item.status === 'open'
          && item.target_user_id === member.user_id
        ))
        const yesCount = vote?.yes_user_ids?.length || 0
        const threshold = vote?.threshold || 0
        const hasVoted = !!vote?.yes_user_ids?.includes(myUserId)
        const voteLabel = vote
          ? (hasVoted ? `已赞成 ${yesCount}/${threshold}` : `赞成移出 ${yesCount}/${threshold}`)
          : '发起移出投票'
        const kickDisabled = hasVoted || disabledHostControls

        return (
          <div
            key={member.user_id}
            className="panel-ornate room-member-card"
            style={{
              padding: 14,
              opacity: member.is_online ? 1 : 0.5,
            }}
          >
            <div style={{ position: 'relative' }}>
              <Portrait cls={classKey(member.character_name ? 'fighter' : 'dm')} size="md" />
              <span style={{
                position: 'absolute',
                bottom: 0,
                right: 0,
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: member.is_online ? 'var(--emerald-light)' : 'var(--bark-light)',
                border: '2px solid var(--void)',
                boxShadow: member.is_online ? '0 0 8px var(--emerald-light)' : 'none',
              }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{
                  fontFamily: 'var(--font-heading)',
                  color: 'var(--parchment)',
                  fontSize: 14,
                  fontWeight: 600,
                }}>{member.display_name}</span>
                {member.role === 'host' && <span className="tag tag-gold" style={{ fontSize: 9 }}>★ 房主</span>}
                {member.user_id === myUserId && <span className="tag tag-blue" style={{ fontSize: 9 }}>我</span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                {member.character_name
                  ? `角色：${member.character_name}`
                  : (member.is_online ? '○ 尚未选择角色' : '◌ 离线')}
              </div>
              {vote && (
                <div style={{ fontSize: 10, color: 'var(--amber)', fontFamily: 'var(--font-mono)', marginTop: 6 }}>
                  移出投票：{yesCount}/{threshold}
                </div>
              )}
            </div>
            {member.user_id !== myUserId && (
              <div className="room-member-actions">
                {isHost && (
                  <button
                    onClick={() => {
                      if (!disabledHostControls) onTransfer(member.user_id)
                    }}
                    disabled={disabledHostControls}
                    title={disabledHostControls ? disabledReason : '转让房主'}
                    className="btn-ghost"
                    style={{ fontSize: 10, padding: '4px 8px', opacity: disabledHostControls ? 0.6 : 1 }}
                  >
                    转让
                  </button>
                )}
                <button
                  onClick={() => {
                    if (!kickDisabled) onKick(member.user_id)
                  }}
                  disabled={kickDisabled}
                  title={disabledHostControls ? disabledReason : voteLabel}
                  className="btn-ghost"
                  style={{ fontSize: 10, padding: '4px 8px', borderColor: 'var(--blood)', color: '#ffaaaa', opacity: kickDisabled ? 0.6 : 1 }}
                >
                  {voteLabel}
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
