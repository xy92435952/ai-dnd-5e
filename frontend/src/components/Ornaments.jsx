/**
 * Divider — 装饰分隔线
 * HpBar — HP 条 (high/mid/low 三档颜色)
 * DiceBadge — 骰子徽章
 *
 * 来源：design v0.10 prototype shared.jsx
 */

export function Divider({ children }) {
  return (
    <div className="divider">
      <span className="divider-glyph">{children || '✦ ❧ ✦'}</span>
    </div>
  )
}

export function DiceBadge({ children, crit, fumble }) {
  const cls = crit ? 'dice-badge crit' : fumble ? 'dice-badge fumble' : 'dice-badge'
  return <span className={cls}>🎲 {children}</span>
}

export function HpBar({ cur, max }) {
  const pct = Math.max(0, Math.min(100, (cur / max) * 100))
  const tone = pct > 60 ? 'high' : pct > 30 ? 'mid' : 'low'
  return (
    <div>
      <div className={`hp-bar ${tone}`}>
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 10, marginTop: 3,
        fontFamily: 'var(--font-mono)', color: 'var(--parchment-dark)',
      }}>
        <span>HP {cur}/{max}</span>
        <span>{tone === 'low' ? '⚠ 危急' : tone === 'mid' ? '受伤' : '健康'}</span>
      </div>
    </div>
  )
}
