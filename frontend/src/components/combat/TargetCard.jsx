export default function TargetCard({ entity, prediction }) {
  if (!entity) return null

  return (
    <div style={{ position: 'absolute', top: 20, right: 20, width: 230 }}>
      <div className="target-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="name">◈ {entity.name}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.15em' }}>TARGET</span>
        </div>
        <div style={{ height: 8, background: '#0a0604', border: '1px solid rgba(196,40,40,.5)', marginTop: 6 }}>
          <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, (entity.hp_current / (entity.hp_max || 1)) * 100))}%`, background: 'linear-gradient(90deg, #f04040, #8a1818)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.3)' }} />
        </div>
        <div className="hit-pred">
          <span>HP <b style={{ color: '#f4a0a0' }}>{entity.hp_current}/{entity.hp_max}</b> · AC <b style={{ color: 'var(--parchment)' }}>{entity.ac}</b></span>
        </div>
        {prediction && (
          <div style={{ borderTop: '1px solid rgba(138,90,24,.3)', marginTop: 8, paddingTop: 8 }}>
            <div className="hit-pred">
              <span>命中</span>
              <span className="pct">{Math.round((prediction.hit_rate || 0) * 100)}%</span>
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--parchment-dark)', letterSpacing: '.08em', marginTop: 3 }}>
              预期 <span style={{ color: 'var(--amber)', fontWeight: 700 }}>{prediction.expected_damage} {prediction.damage_type}</span>
            </div>
            {prediction.modifiers?.length > 0 && (
              <div style={{ fontSize: 9, color: 'var(--parchment-dark)', marginTop: 2 }}>{prediction.modifiers.join(' · ')}</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
