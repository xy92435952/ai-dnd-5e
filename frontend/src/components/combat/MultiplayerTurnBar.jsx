export default function MultiplayerTurnBar({ room, currentTurnLabel, isMyTurnMP }) {
  if (!room || !currentTurnLabel) return null

  return (
    <div style={{
      background: isMyTurnMP
        ? 'linear-gradient(90deg, rgba(74,138,74,0.4), rgba(74,138,74,0.15))'
        : 'linear-gradient(90deg, rgba(58,122,170,0.3), rgba(58,122,170,0.1))',
      borderBottom: '1px solid var(--amber)',
      padding: '5px 16px', color: 'var(--amber)',
      fontSize: 12, fontWeight: 'bold',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      zIndex: 5, flexShrink: 0,
    }}>
      <span>{currentTurnLabel}</span>
      <span style={{ fontSize: 11, opacity: 0.8 }}>
        {isMyTurnMP ? '你的回合' : '观战中…'} · 房间 {room.room_code}
      </span>
    </div>
  )
}
