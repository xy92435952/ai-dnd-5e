export default function ReactionPrompt({ prompt, onReact, onCancel }) {
  if (!prompt) return null
  const options = prompt.options || (prompt.available_reactions || []).map(reaction => ({
    type: reaction.type || reaction.id,
    target_id: prompt.target_id || prompt.attacker_id,
    character_id: prompt.reactor_character_id,
    label: `${reaction.name || reaction.id}${reaction.effect ? ` - ${reaction.effect}` : ''}`,
  }))

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)' }}>
      <div style={{ padding: 20, width: 360, background: 'var(--obsidian)', border: '1px solid var(--flame)' }}>
        <p style={{ color: 'var(--flame)', fontFamily: 'var(--font-display)', fontSize: 14, marginBottom: 8 }}>⚡ 反应触发</p>
        <p style={{ color: 'var(--parchment)', fontSize: 12, marginBottom: 12 }}>{prompt.context || '选择反应'}</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {options.map((opt, i) => (
            <button key={i} className="btn-gold" style={{ padding: 8, fontSize: 12, textAlign: 'left' }}
              onClick={() => onReact(opt.type, opt.target_id, opt.character_id || prompt.reactor_character_id)}>
              {opt.label}
            </button>
          ))}
          <button className="btn-ghost" style={{ padding: 6, fontSize: 11 }} onClick={onCancel}>
            放弃反应
          </button>
        </div>
      </div>
    </div>
  )
}
