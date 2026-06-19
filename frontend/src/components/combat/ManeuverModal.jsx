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
  const handleUse = (maneuverId) => {
    if (!hasDice) return
    onUse(maneuverId)
    onClose()
  }

  return (
    <div
      className="maneuver-modal-backdrop"
      onClick={onClose}
    >
      <section
        className="maneuver-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="maneuver-modal-title"
        aria-describedby="maneuver-modal-meta"
        onClick={e => e.stopPropagation()}
      >
        <div className="maneuver-modal-head">
          <h2 id="maneuver-modal-title" className="maneuver-modal-title">战技选择</h2>
          <div id="maneuver-modal-meta" className="maneuver-modal-meta">
            优越骰: {diceType} × {remaining}
          </div>
        </div>
        <div className="maneuver-modal-list" role="list" aria-label="可用战技">
          {MANEUVERS.map(m => (
            <div
              key={m.id}
              className="maneuver-modal-item"
              role="listitem"
              aria-label={`${m.name}：${m.desc}`}
            >
              <button
                type="button"
                className="maneuver-modal-action"
                disabled={!hasDice}
                title={unavailableReason || m.name}
                aria-disabled={!hasDice}
                aria-label={`发动战技 ${m.name}。${m.desc}`}
                onClick={() => handleUse(m.id)}
              >
                <span className="maneuver-modal-icon" aria-hidden="true">{m.icon}</span>
                <span className="maneuver-modal-copy">
                  <span className="maneuver-modal-name">{m.name}</span>
                  <span className="maneuver-modal-desc">{m.desc}</span>
                </span>
              </button>
            </div>
          ))}
        </div>
        {!hasDice && (
          <div className="maneuver-modal-status" role="status" aria-live="polite">
            {unavailableReason}，无法发动战技。
          </div>
        )}
        <button type="button" className="btn-fantasy maneuver-modal-cancel" onClick={onClose}>取消</button>
      </section>
    </div>
  )
}
