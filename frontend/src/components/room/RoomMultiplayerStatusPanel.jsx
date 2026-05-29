import {
  getGroupPendingActions,
  getGroupStatusSummary,
  getMemberName,
  getMultiplayerTableStatus,
} from '../../utils/multiplayerGroups'
import MultiplayerSessionStatusBar from '../multiplayer/MultiplayerSessionStatusBar'
import WebSocketStatusPill from '../multiplayer/WebSocketStatusPill'

export default function RoomMultiplayerStatusPanel({
  room,
  claimedCount,
  memberCount,
  busy,
  wsConnected = false,
  wsStatus = null,
  onFocusGroup,
}) {
  if (!room?.is_multiplayer) return null

  const tableStatus = getMultiplayerTableStatus({ room })

  return (
    <div className="panel-ornate" style={{ padding: 14, marginTop: 14 }}>
      <div style={{ margin: '-8px -24px 12px' }}>
        <MultiplayerSessionStatusBar
          room={room}
          label="联机准备"
          title={`${claimedCount}/${memberCount} 已认领角色`}
          reason={`当前焦点：${tableStatus.activeGroupLabel || '主队'}`}
          nextLabel={tableStatus.nextReadySummary}
        >
          <WebSocketStatusPill status={wsStatus} connected={wsConnected} />
        </MultiplayerSessionStatusBar>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
        {(room.party_groups || []).map(group => {
          const groupSummary = getGroupStatusSummary(room, group)
          const pending = getGroupPendingActions(room, group)
          return (
            <div key={group.id} style={{
              padding: 10,
              border: `1px solid ${groupSummary.isActive ? 'var(--amber)' : 'rgba(127,232,248,.28)'}`,
              background: groupSummary.isActive ? 'rgba(138,90,24,.16)' : 'rgba(7,18,24,.58)',
              borderRadius: 4,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                <strong style={{ color: groupSummary.isActive ? 'var(--amber)' : 'var(--parchment)', fontFamily: 'var(--font-heading)' }}>
                  {group.name || group.id}
                </strong>
                {groupSummary.isActive ? (
                  <span className="tag tag-gold" style={{ fontSize: 9 }}>焦点</span>
                ) : (
                  <button
                    onClick={() => onFocusGroup(group.id)}
                    disabled={busy}
                    className="btn-ghost"
                    style={{ fontSize: 10, padding: '3px 8px' }}
                  >
                    设为焦点
                  </button>
                )}
              </div>
              <div style={{ marginTop: 4, fontSize: 11, color: 'var(--parchment-dark)' }}>
                {group.location || '当前位置'}
              </div>
              <div style={{ marginTop: 6, fontSize: 10, color: 'var(--arcane-light)', fontFamily: 'var(--font-mono)' }}>
                {groupSummary.membersLabel}
              </div>
              {pending.length > 0 && (
                <div style={{ marginTop: 8, display: 'grid', gap: 4 }}>
                  {pending.slice(0, 3).map((action, idx) => (
                    <div key={`${action.user_id}-${idx}`} style={{
                      padding: '4px 6px',
                      borderLeft: '2px solid var(--arcane-light)',
                      color: 'var(--parchment-dark)',
                      background: 'rgba(127,232,248,.08)',
                      fontSize: 10,
                    }}>
                      <b style={{ color: 'var(--parchment)' }}>{action.display_name || getMemberName(room, action.user_id)}</b>
                      <span>：{action.text}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
