export default function CombatOutcomeOverlay({ combatOver, onReturn }) {
  if (!combatOver) return null

  return (
    <div style={{
      position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
      padding: '24px 40px', background: 'rgba(10,6,4,.95)',
      border: `2px solid ${combatOver === 'victory' ? 'var(--emerald)' : 'var(--blood)'}`,
      textAlign: 'center', zIndex: 10,
    }}>
      <div style={{ fontSize: 48, marginBottom: 8 }}>{combatOver === 'victory' ? '🏆' : '💀'}</div>
      <div className="display-title" style={{ fontSize: 22, color: combatOver === 'victory' ? 'var(--emerald-light)' : 'var(--blood-light)' }}>
        {combatOver === 'victory' ? '战斗胜利' : '全队阵亡'}
      </div>
      <button onClick={onReturn} className="btn-gold" style={{ marginTop: 16 }}>
        返回冒险 ►
      </button>
    </div>
  )
}
