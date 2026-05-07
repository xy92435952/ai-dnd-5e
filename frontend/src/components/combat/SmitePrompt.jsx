export default function SmitePrompt({ open, playerSpellSlots, onSmite, onCancel }) {
  if (!open) return null

  return (
    <div className="fixed inset-0" style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)' }}>
      <div style={{ padding: 18, width: 320, background: 'var(--obsidian)', border: '1px solid var(--amber)' }}>
        <p style={{ color: 'var(--amber)', fontFamily: 'var(--font-display)', fontSize: 14, marginBottom: 10 }}>
          命中！是否使用神圣斩击？
        </p>
        <p style={{ color: 'var(--parchment-dark)', fontSize: 12, marginBottom: 12 }}>
          消耗 1 环法术位造成 +2d8 辐光伤害（每升一环 +1d8）
        </p>
        <div style={{ display: 'flex', gap: 6 }}>
          {[1, 2, 3, 4, 5].filter(l => (playerSpellSlots[['1st','2nd','3rd','4th','5th'][l-1]] || 0) > 0).map(l => (
            <button key={l} className="btn-gold" style={{ flex: 1, padding: 8, fontSize: 11 }} onClick={() => onSmite(l)}>
              {l}环
            </button>
          ))}
          <button className="btn-ghost" style={{ padding: 8, fontSize: 11 }} onClick={onCancel}>取消</button>
        </div>
      </div>
    </div>
  )
}
