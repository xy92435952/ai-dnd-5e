/**
 * ManeuverModal — 战斗宗师战技选择弹窗。
 *
 * Props:
 *   diceType  - '1d6' | '1d8' | '1d10' | '1d12' 优越骰大小
 *   remaining - number 剩余优越骰次数
 *   onUse     - (maneuverId: string) => void
 *   onClose   - () => void
 */
import { MANEUVERS } from '../../data/combat'

export default function ManeuverModal({ diceType, remaining, onUse, onClose }) {
  const hasDice = remaining > 0
  const unavailableReason = hasDice ? '' : '没有可用优越骰'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.7)' }}
      onClick={onClose}
    >
      <div
        className="panel p-5"
        style={{ background: 'var(--bg2)', borderColor: 'var(--gold)', maxWidth: 400, width: '90%' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <p style={{ color: 'var(--gold)', fontWeight: 700, fontSize: 15, margin: 0 }}>战技选择</p>
          <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>优越骰: {diceType} × {remaining}</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {MANEUVERS.map(m => (
            <button
              key={m.id}
              className="panel"
              disabled={!hasDice}
              title={unavailableReason || m.name}
              aria-disabled={!hasDice}
              style={{
                padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10,
                border: '1px solid var(--wood-light)', background: 'var(--bg)', textAlign: 'left',
                transition: 'border-color 0.2s',
                opacity: hasDice ? 1 : 0.45,
                cursor: hasDice ? 'pointer' : 'not-allowed',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--gold)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--wood-light)'}
              onClick={() => { if (hasDice) { onUse(m.id); onClose() } }}
            >
              <span style={{ fontSize: 20 }}>{m.icon}</span>
              <div>
                <p style={{ color: 'var(--text-bright)', fontWeight: 600, fontSize: 13, margin: 0 }}>{m.name}</p>
                <p style={{ color: 'var(--text-dim)', fontSize: 11, margin: 0 }}>{m.desc}</p>
              </div>
            </button>
          ))}
        </div>
        {!hasDice && (
          <div style={{ color: 'var(--parchment-dark)', fontSize: 11, marginTop: 10 }}>
            {unavailableReason}，无法发动战技。
          </div>
        )}
        <button className="btn-fantasy" style={{ width: '100%', marginTop: 12, fontSize: 12 }} onClick={onClose}>取消</button>
      </div>
    </div>
  )
}
