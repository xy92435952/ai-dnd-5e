import Portrait from '../Portrait'
import { classKey } from '../Crests'

export default function AdventurePartyHud({ allMembers, onOpenCharacter }) {
  return (
    <div className="party-hud">
      {allMembers.map((p, idx) => {
        const derived = p.derived || {}
        const hpMax = derived.hp_max || p.hp_current || 1
        const pct = Math.max(0, Math.min(100, (p.hp_current / hpMax) * 100))
        const tone = pct < 34 ? 'low' : pct < 67 ? 'mid' : ''
        const active = p.isPlayer
        const ck = classKey(p.char_class)
        const label = p.name ? `打开角色 ${p.name}` : '打开角色'
        return (
          <button
            key={p.id || idx}
            type="button"
            className={`party-slot ${active ? 'active' : ''} ${tone}`}
            title={`${p.name} HP ${p.hp_current}/${hpMax}`}
            aria-label={label}
            data-testid={p.id ? `party-member-${p.id}` : undefined}
            onClick={() => p.id && onOpenCharacter(p.id)}
            disabled={!p.id}
            style={{
              cursor: p.id ? 'pointer' : 'default',
              background: 'none',
              border: 'none',
              padding: 0,
            }}
          >
            <div className="frame" />
            <div style={{ position: 'absolute', inset: 3, borderRadius: '50%', overflow: 'hidden' }}>
              <Portrait cls={ck} size="sm" style={{ width: '100%', height: '100%' }} />
              {pct > 0 && pct <= 25 && <span className="avatar-crack" />}
            </div>
            <div className="hp-micro"><div className="fill" style={{ width: `${pct}%` }} /></div>
          </button>
        )
      })}
    </div>
  )
}
