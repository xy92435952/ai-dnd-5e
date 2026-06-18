import { getLuckyPointsRemaining } from '../../utils/lucky'
import { getBardicInspiration } from '../../utils/bardicInspiration'

export default function DialoguePendingCheck({
  pendingCheck,
  checkRolling,
  onDiceRoll,
  disabled = false,
  player = null,
  onToggleLucky = null,
  onToggleBardicInspiration = null,
}) {
  const luckyRemaining = getLuckyPointsRemaining(player)
  const luckyActive = Boolean(pendingCheck.use_lucky)
  const canToggleLucky = luckyRemaining > 0 && !checkRolling && !disabled && typeof onToggleLucky === 'function'
  const bardic = getBardicInspiration(player)
  const bardicActive = Boolean(pendingCheck.use_bardic_inspiration)
  const canToggleBardic = Boolean(bardic) && !checkRolling && !disabled && typeof onToggleBardicInspiration === 'function'

  return (
    <section className="dialogue-pending-check" aria-label="待处理技能检定">
      <div className="eyebrow dialogue-pending-check-title" role="status" aria-live="polite">
        🎲 {pendingCheck.check_type}检定 · DC {pendingCheck.dc}
      </div>
      <p className="dialogue-pending-check-context">
        {pendingCheck.context || '请投骰决定结果'}
      </p>
      {(luckyRemaining > 0 || bardic) && (
        <div className="dialogue-pending-check-modifiers" role="group" aria-label="检定资源修正">
          {luckyRemaining > 0 && (
            <button
              type="button"
              className={`${luckyActive ? 'btn-gold' : 'btn-ghost'} dialogue-pending-check-toggle`}
              aria-pressed={luckyActive}
              onClick={onToggleLucky}
              disabled={!canToggleLucky}
              title={`Lucky points remaining: ${luckyRemaining}`}
            >
              Lucky {luckyActive ? 'ON' : 'OFF'} · {luckyRemaining}
            </button>
          )}
          {bardic && (
            <button
              type="button"
              className={`${bardicActive ? 'btn-gold' : 'btn-ghost'} dialogue-pending-check-toggle`}
              aria-pressed={bardicActive}
              onClick={onToggleBardicInspiration}
              disabled={!canToggleBardic}
              title={`Bardic Inspiration ${bardic.die}`}
            >
              Bardic {bardicActive ? 'ON' : 'OFF'} · {bardic.die}
            </button>
          )}
        </div>
      )}
      <button
        className="btn-gold dialogue-pending-check-roll"
        onClick={onDiceRoll}
        disabled={checkRolling || disabled}
      >
        {checkRolling ? '✦ 骰子翻滚中… ✦' : disabled ? '✦ 等待同步恢复 ✦' : '✦ 投掷 d20 ✦'}
      </button>
    </section>
  )
}
