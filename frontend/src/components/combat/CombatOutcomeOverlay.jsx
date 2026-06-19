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
    <section
      className={`combat-outcome-overlay ${isVictory ? 'victory' : 'defeat'}`}
      role="dialog"
      aria-modal="true"
      aria-label={isVictory ? '战斗胜利结算' : '战斗失败结算'}
    >
      <div className="combat-outcome-mark" aria-hidden="true">{isVictory ? '胜' : '败'}</div>
      <div className="display-title combat-outcome-title">
        {isVictory ? '战斗胜利' : '全队阵亡'}
      </div>

      {isVictory && (canRecoverThrownWeapons || recoveredSummary || recoveryError) && (
        <div
          data-testid="thrown-recovery-panel"
          className="thrown-recovery-panel"
          role="region"
          aria-label="投掷武器回收"
        >
          {recoverableSummary && (
            <div className="thrown-recovery-row pending" role="status">
              可回收 {recoverableSummary}
            </div>
          )}
          {recoveredSummary && (
            <div className="thrown-recovery-row recovered" role="status">
              已回收 {recoveredSummary}
            </div>
          )}
          {recoveryError && (
            <div className="thrown-recovery-row error" role="alert">
              {recoveryError}
            </div>
          )}
          {canRecoverThrownWeapons && (
            <button
              type="button"
              onClick={onRecoverThrownWeapons}
              className="btn-secondary"
              disabled={isRecoveringThrownWeapons}
              aria-busy={isRecoveringThrownWeapons || undefined}
            >
              {isRecoveringThrownWeapons ? '回收中...' : '回收投掷武器'}
            </button>
          )}
        </div>
      )}

      <button type="button" onClick={onReturn} className="btn-gold combat-outcome-return">
        返回冒险
      </button>
    </section>
  )
}
