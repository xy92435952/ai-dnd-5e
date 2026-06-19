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
            data-online={member.is_online ? 'true' : 'false'}
          >
            <div className="room-member-portrait">
              <Portrait cls={classKey(member.character_name ? 'fighter' : 'dm')} size="md" />
              <span className="room-member-online-dot" aria-hidden="true" />
            </div>
            <div className="room-member-body">
              <div className="room-member-identity">
                <span className="room-member-name">{member.display_name}</span>
                {member.role === 'host' && <span className="tag tag-gold room-member-tag">★ 房主</span>}
                {member.user_id === myUserId && <span className="tag tag-blue room-member-tag">我</span>}
              </div>
              <div className="room-member-meta">
                {member.character_name
                  ? `角色：${member.character_name}`
                  : (member.is_online ? '○ 尚未选择角色' : '◌ 离线')}
              </div>
              {vote && (
                <div className="room-member-vote-meta">
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
                    className="btn-ghost room-member-action"
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
                  className="btn-ghost room-member-action room-member-action-danger"
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
