import {
  getGroupPendingActions,
  getGroupStatusSummary,
  getMemberName,
  getMultiplayerTableStatus,
} from '../../utils/multiplayerGroups'
import MultiplayerSessionStatusBar from '../multiplayer/MultiplayerSessionStatusBar'
import WebSocketStatusPill from '../multiplayer/WebSocketStatusPill'

const READINESS_PROMPT_TONES = new Set(['urgent', 'pending', 'ready'])

function getReadinessPromptBadge(summary) {
  if (summary.readinessReset) return '需重新确认'
  if (summary.readinessPromptTone === 'ready') return '已就绪'
  return '确认提示'
}

export default function RoomMultiplayerStatusPanel({
  room,
  claimedCount,
  memberCount,
  busy,
  wsConnected = false,
  wsStatus = null,
  syncBlocked = false,
  syncBlockedReason = '',
  onFocusGroup,
}) {
  if (!room?.is_multiplayer) return null

  const tableStatus = getMultiplayerTableStatus({ room })
  const controlsDisabled = busy || syncBlocked
  const blockReason = syncBlockedReason || '房间正在重新同步，请恢复连接后再调整分组。'

  return (
    <section className="panel-ornate room-multiplayer-status-panel" aria-label="多人房间准备状态">
      <div className="room-multiplayer-status-bar">
        <MultiplayerSessionStatusBar
          room={room}
          label="联机准备"
          title={`${claimedCount}/${memberCount} 已认领角色`}
          reason={`当前焦点：${tableStatus.activeGroupLabel || '主队'}`}
          focusLabel={syncBlocked ? '同步中 · 暂停房间变更' : ''}
          nextLabel={tableStatus.nextReadySummary}
        >
          <WebSocketStatusPill status={wsStatus} connected={wsConnected} />
        </MultiplayerSessionStatusBar>
      </div>

      {syncBlocked && (
        <div role="status" className="multiplayer-sync-guard room-multiplayer-sync-guard">
          <strong>同步暂停</strong>
          <span>{blockReason}</span>
        </div>
      )}

      <div className="room-multiplayer-groups">
        {(room.party_groups || []).map(group => {
          const groupSummary = getGroupStatusSummary(room, group)
          const pending = getGroupPendingActions(room, group)
          const readinessPromptTone = READINESS_PROMPT_TONES.has(groupSummary.readinessPromptTone)
            ? groupSummary.readinessPromptTone
            : 'pending'
          return (
            <article
              key={group.id}
              className="room-multiplayer-group-card"
              data-active={groupSummary.isActive ? 'true' : 'false'}
            >
              <div className="room-multiplayer-group-head">
                <strong className="room-multiplayer-group-name">
                  {group.name || group.id}
                </strong>
                {groupSummary.isActive ? (
                  <span className="tag tag-gold room-multiplayer-focus-tag">焦点</span>
                ) : (
                  <button
                    onClick={() => {
                      if (!controlsDisabled) onFocusGroup(group.id)
                    }}
                    disabled={controlsDisabled}
                    title={syncBlocked ? blockReason : '设为当前焦点分队'}
                    className="btn-ghost room-multiplayer-focus-btn"
                  >
                    设为焦点
                  </button>
                )}
              </div>
              <div className="room-multiplayer-group-location">
                {group.location || '当前位置'}
              </div>
              <div className="room-multiplayer-group-members">
                {groupSummary.membersLabel}
              </div>
              {groupSummary.readinessPrompt && (
                <div
                  className="room-multiplayer-readiness-prompt"
                  data-tone={readinessPromptTone}
                  aria-label={`${group.name || group.id}确认提示`}
                >
                  <strong>{getReadinessPromptBadge(groupSummary)}</strong>
                  <span>{groupSummary.readinessPrompt}</span>
                </div>
              )}
              {pending.length > 0 && (
                <div className="room-multiplayer-pending-list">
                  {pending.slice(0, 3).map((action, idx) => (
                    <div key={`${action.user_id}-${idx}`} className="room-multiplayer-pending-item">
                      <b>{action.display_name || getMemberName(room, action.user_id)}</b>
                      <span>：{action.text}</span>
                    </div>
                  ))}
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
