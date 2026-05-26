export default function InitiativeRibbon({ initiativeChips, onSelectTarget }) {
  return (
    <div className="init-ribbon">
      {initiativeChips.map(({ ent, t, pct, isCur, dead, low, lifeState }) => (
        <div
          key={t.character_id}
          className={`unit-chip ${t.is_enemy ? 'enemy' : ''} ${isCur ? 'active' : ''} ${dead ? 'dead' : ''} ${low ? 'low' : ''} life-${lifeState || 'alive'}`}
          onClick={() => !dead && onSelectTarget(t.character_id)}
          style={{ cursor: dead ? 'default' : 'pointer' }}
        >
          <div className="init-no">{t.initiative ?? '?'}</div>
          <div className="avatar" style={{ position: 'relative' }}>
            {(ent?.name || t.name || '?').slice(0, 1)}{dead && '×'}
            {low && !dead && <span className="avatar-crack" />}
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment)', letterSpacing: '.08em', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {(ent?.name || t.name || '?').slice(0, 4)}
          </div>
          <div className="hp-tick"><div className="fill" style={{ width: `${pct}%` }} /></div>
          {ent?.conditions?.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 1, marginTop: 2 }}>
              {ent.conditions.slice(0, 3).map((c, ci) => (
                <span key={ci} style={{ fontSize: 8, color: '#f4a0a0' }} title={c}>⚠</span>
              ))}
            </div>
          )}
        </div>
      ))}
      <div style={{ flex: 1 }} />
    </div>
  )
}
