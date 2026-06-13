import { formatThrownRecoverySummary } from '../../utils/thrownRecovery'

export default function CombatOutcomeOverlay({
  combatOver,
  onReturn,
  recoverableThrownWeapons = [],
  recoveredThrownWeapons = [],
  isRecoveringThrownWeapons = false,
  onRecoverThrownWeapons = null,
  recoveryError = '',
}) {
  if (!combatOver) return null

  const isVictory = combatOver === 'victory'
  const recoverableSummary = formatThrownRecoverySummary(recoverableThrownWeapons)
  const recoveredSummary = formatThrownRecoverySummary(recoveredThrownWeapons)
  const canRecoverThrownWeapons = (
    isVictory
    && recoverableThrownWeapons.length > 0
    && typeof onRecoverThrownWeapons === 'function'
  )

  return (
    <div style={{
      position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
      padding: '24px 40px', background: 'rgba(10,6,4,.95)',
      border: `2px solid ${isVictory ? 'var(--emerald)' : 'var(--blood)'}`,
      textAlign: 'center', zIndex: 10,
    }}>
      <div style={{ fontSize: 48, marginBottom: 8 }}>{isVictory ? '胜' : '败'}</div>
      <div className="display-title" style={{ fontSize: 22, color: isVictory ? 'var(--emerald-light)' : 'var(--blood-light)' }}>
        {isVictory ? '战斗胜利' : '全队阵亡'}
      </div>

      {isVictory && (canRecoverThrownWeapons || recoveredSummary || recoveryError) && (
        <div
          data-testid="thrown-recovery-panel"
          style={{
            marginTop: 14,
            paddingTop: 12,
            borderTop: '1px solid rgba(212,175,55,.28)',
            minWidth: 240,
          }}
        >
          {recoverableSummary && (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              可回收 {recoverableSummary}
            </div>
          )}
          {recoveredSummary && (
            <div style={{ color: 'var(--emerald-light)', fontSize: 13 }}>
              已回收 {recoveredSummary}
            </div>
          )}
          {recoveryError && (
            <div style={{ color: 'var(--blood-light)', fontSize: 12, marginTop: 6 }}>
              {recoveryError}
            </div>
          )}
          {canRecoverThrownWeapons && (
            <button
              type="button"
              onClick={onRecoverThrownWeapons}
              className="btn-secondary"
              disabled={isRecoveringThrownWeapons}
              style={{ marginTop: 10 }}
            >
              {isRecoveringThrownWeapons ? '回收中...' : '回收投掷武器'}
            </button>
          )}
        </div>
      )}

      <button type="button" onClick={onReturn} className="btn-gold" style={{ marginTop: 16 }}>
        返回冒险
      </button>
    </div>
  )
}
