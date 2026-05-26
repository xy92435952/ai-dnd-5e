export default function DialoguePendingCheck({ pendingCheck, checkRolling, onDiceRoll, disabled = false }) {
  return (
    <div style={{ padding: 16, textAlign: 'center' }}>
      <div className="eyebrow" style={{ color: 'var(--arcane-light)' }}>🎲 {pendingCheck.check_type}检定 · DC {pendingCheck.dc}</div>
      <p style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)', fontSize: 13, marginTop: 6 }}>
        {pendingCheck.context || '请投骰决定结果'}
      </p>
      <button className="btn-gold" onClick={onDiceRoll} disabled={checkRolling || disabled} style={{ marginTop: 10, padding: '10px 24px', letterSpacing: '.2em' }}>
        {checkRolling ? '✦ 骰子翻滚中… ✦' : disabled ? '✦ 等待同步恢复 ✦' : '✦ 投掷 d20 ✦'}
      </button>
    </div>
  )
}
