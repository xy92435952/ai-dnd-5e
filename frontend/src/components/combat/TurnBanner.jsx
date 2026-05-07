export default function TurnBanner({
  roundNumber,
  currentTurnName,
  combatOver,
  showThreat,
  onToggleThreat,
}) {
  return (
    <div className="turn-banner">
      <span className="round-tag">R {roundNumber || 1}</span>
      <span style={{ color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '.2em', marginRight: 8 }}>轮到</span>
      <span className="active-name">{currentTurnName || '—'}</span>
      {combatOver && (
        <span style={{ marginLeft: 14, color: combatOver === 'victory' ? 'var(--emerald-light)' : 'var(--blood-light)', fontFamily: 'var(--font-display)', fontSize: 13 }}>
          · {combatOver === 'victory' ? '🏆 胜利' : '💀 全灭'} ·
        </span>
      )}
      <span style={{ flex: 1 }} />
      <button
        onClick={onToggleThreat}
        title="显示/隐藏敌人攻击范围"
        style={{
          background: showThreat ? 'rgba(240,64,64,.2)' : 'transparent',
          border: `1px solid ${showThreat ? 'rgba(240,80,80,.75)' : 'rgba(138,90,24,.5)'}`,
          color: showThreat ? '#ff9090' : 'var(--parchment-dark)',
          padding: '4px 10px',
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '.15em',
          textTransform: 'uppercase',
          cursor: 'pointer',
          transition: 'all .15s',
        }}
      >⚔ 威胁区</button>
    </div>
  )
}
