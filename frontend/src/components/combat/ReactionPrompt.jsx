function normalizeReactionOptions(prompt) {
  const rawOptions = Array.isArray(prompt?.options)
    ? prompt.options
    : Array.isArray(prompt?.available_reactions)
      ? prompt.available_reactions
      : []

  return rawOptions
    .map((opt) => {
      const reactionType = opt.id || opt.reaction_type || opt.type
      return {
        ...opt,
        reactionType,
        targetId: opt.target_id || opt.targetId || prompt.attacker_id || null,
        label: opt.label || opt.name || reactionType,
      }
    })
    .filter(opt => opt.reactionType)
}

export default function ReactionPrompt({ prompt, onReact, onCancel }) {
  if (!prompt) return null

  const options = normalizeReactionOptions(prompt)

  return (
    <div
      data-testid="combat-reaction-prompt"
      role="dialog"
      aria-modal="true"
      aria-label="Reaction prompt"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.7)',
      }}
    >
      <div style={{ padding: 20, width: 360, background: 'var(--obsidian)', border: '1px solid var(--flame)' }}>
        <p style={{ color: 'var(--flame)', fontFamily: 'var(--font-display)', fontSize: 14, marginBottom: 8 }}>
          Reaction Triggered
        </p>
        <p style={{ color: 'var(--parchment)', fontSize: 12, marginBottom: 12 }}>
          {prompt.context || 'Choose a reaction'}
        </p>
        {prompt.attacker_name && (
          <p style={{ color: 'var(--ash)', fontSize: 11, marginBottom: 10 }}>
            Attacker: {prompt.attacker_name}
          </p>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {options.map((opt, i) => (
            <button
              key={`${opt.reactionType}-${i}`}
              data-testid={`combat-reaction-${opt.reactionType}`}
              className="btn-gold"
              style={{ padding: 8, fontSize: 12, textAlign: 'left' }}
              onClick={() => onReact(opt.reactionType, opt.targetId)}
            >
              <span style={{ display: 'block' }}>{opt.label}</span>
              {(opt.cost || opt.effect) && (
                <span style={{ display: 'block', opacity: 0.8, fontSize: 10, marginTop: 3 }}>
                  {[opt.cost, opt.effect].filter(Boolean).join(' - ')}
                </span>
              )}
            </button>
          ))}
          <button
            data-testid="combat-reaction-cancel"
            className="btn-ghost"
            style={{ padding: 6, fontSize: 11 }}
            onClick={() => onReact('skip', prompt.attacker_id || null)}
          >
            Skip reaction
          </button>
        </div>
      </div>
    </div>
  )
}
