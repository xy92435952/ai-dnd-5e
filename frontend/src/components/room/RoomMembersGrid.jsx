import Portrait from '../Portrait'
import { classKey } from '../Crests'

export default function RoomMembersGrid({
  members,
  myUserId,
  isHost,
  onTransfer,
  onKick,
}) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14, marginTop: 18 }}>
      {(members || []).map((member) => (
        <div
          key={member.user_id}
          className="panel-ornate"
          style={{
            padding: 14,
            display: 'flex',
            gap: 14,
            alignItems: 'center',
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
          </div>
          {isHost && member.user_id !== myUserId && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <button onClick={() => onTransfer(member.user_id)} className="btn-ghost" style={{ fontSize: 10, padding: '4px 8px' }}>转让</button>
              <button onClick={() => onKick(member.user_id)} className="btn-ghost" style={{ fontSize: 10, padding: '4px 8px', borderColor: 'var(--blood)', color: '#ffaaaa' }}>踢出</button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
