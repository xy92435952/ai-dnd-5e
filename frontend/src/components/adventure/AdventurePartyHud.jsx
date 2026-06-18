import Portrait from '../Portrait'
import { classKey } from '../Crests'

export default function AdventurePartyHud({ allMembers, onOpenCharacter }) {
  return (
    <div className="party-hud" role="list" aria-label="冒险队伍状态">
      {allMembers.map((p, idx) => {
        const derived = p.derived || {}
        const hpMax = p.hp_max || derived.hp_max || p.hp_current || 1
        const pct = Math.max(0, Math.min(100, (p.hp_current / hpMax) * 100))
        const tone = pct < 34 ? 'low' : pct < 67 ? 'mid' : ''
        const active = p.isPlayer
        const ck = classKey(p.char_class)
        const hpLabel = `${p.name} HP ${p.hp_current}/${hpMax}`
        const slotLabel = `${p.name}${active ? ' 当前角色' : ''}，${hpLabel}`
        const canOpenCharacter = Boolean(p.id && onOpenCharacter)
        return (
          <div key={p.id || idx} className="party-slot-item" role="listitem">
            <div className={`party-slot ${active ? 'active' : ''} ${tone}`} aria-hidden="true">
              <div className="frame" />
              <div className="party-slot-avatar">
                <Portrait cls={ck} size="sm" style={{ width: '100%', height: '100%' }} />
                {pct > 0 && pct <= 25 && <span className="avatar-crack" />}
              </div>
              <div className="hp-micro" aria-hidden="true"><div className="fill" style={{ '--hp-pct': `${pct}%` }} /></div>
            </div>
            <button
              type="button"
              className="party-slot-action"
              title={hpLabel}
              aria-label={slotLabel}
              aria-current={active ? 'true' : undefined}
              disabled={!canOpenCharacter}
              onClick={() => canOpenCharacter && onOpenCharacter(p.id)}
            >
              <span className="party-slot-hp-label">{hpLabel}</span>
            </button>
          </div>
        )
      })}
    </div>
  )
}
