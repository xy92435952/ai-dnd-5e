import { getLuckyPointsRemaining } from '../../utils/lucky'

export default function DialoguePendingCheck({
  pendingCheck,
  checkRolling,
  onDiceRoll,
  disabled = false,
  player = null,
  onToggleLucky = null,
}) {
  const luckyRemaining = getLuckyPointsRemaining(player)
  const luckyActive = Boolean(pendingCheck.use_lucky)
  const canToggleLucky = luckyRemaining > 0 && !checkRolling && !disabled && typeof onToggleLucky === 'function'

  return (
    <div style={{ padding: 16, textAlign: 'center' }}>
      <div className="eyebrow" style={{ color: 'var(--arcane-light)' }}>🎲 {pendingCheck.check_type}检定 · DC {pendingCheck.dc}</div>
      <p style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)', fontSize: 13, marginTop: 6 }}>
        {pendingCheck.context || '请投骰决定结果'}
      </p>
      {luckyRemaining > 0 && (
        <button
          type="button"
          className={luckyActive ? 'btn-gold' : 'btn-ghost'}
          aria-pressed={luckyActive}
          onClick={onToggleLucky}
          disabled={!canToggleLucky}
          title={`Lucky points remaining: ${luckyRemaining}`}
          style={{ marginTop: 8, marginRight: 8, padding: '8px 14px', letterSpacing: '.08em' }}
        >
          Lucky {luckyActive ? 'ON' : 'OFF'} · {luckyRemaining}
        </button>
      )}
      <button className="btn-gold" onClick={onDiceRoll} disabled={checkRolling || disabled} style={{ marginTop: 10, padding: '10px 24px', letterSpacing: '.2em' }}>
        {checkRolling ? '✦ 骰子翻滚中… ✦' : disabled ? '✦ 等待同步恢复 ✦' : '✦ 投掷 d20 ✦'}
      </button>
    </div>
  )
}
