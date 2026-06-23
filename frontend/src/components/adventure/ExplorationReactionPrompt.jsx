function reactionOption(prompt) {
  return prompt?.available_reactions?.[0] || prompt?.options?.[0] || {}
}

export default function ExplorationReactionPrompt({
  prompt,
  disabled = false,
  onResolve,
}) {
  if (!prompt) return null

  const option = reactionOption(prompt)
  const trapName = prompt.trap_name || 'Trap'
  const reactorName = prompt.reactor_character_name || 'Caster'
  const targetName = prompt.target_character_name || 'Target'
  const prevented = option.damage_prevented ?? prompt.damage_prevented ?? prompt.damage_before ?? 0
  const slot = option.slot_level || prompt.slot_level || ''
  const cost = option.cost || (slot ? `${slot} spell slot + reaction` : 'reaction')
  const damageLabel = `${prevented} fall damage`

  const titleId = 'exploration-reaction-prompt-title'
  const bodyId = 'exploration-reaction-prompt-body'
  const metaId = 'exploration-reaction-prompt-meta'
  const outcomesId = 'exploration-reaction-prompt-outcomes'

  return (
    <div
      className="exploration-reaction-prompt"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={`${bodyId} ${metaId} ${outcomesId}`}
      aria-live="polite"
    >
      <div className="exploration-reaction-prompt__eyebrow">Reaction</div>
      <div id={titleId} className="exploration-reaction-prompt__title">Feather Fall</div>
      <div id={bodyId} className="exploration-reaction-prompt__body">
        <b>{reactorName}</b> can protect <b>{targetName}</b> from <b>{trapName}</b>.
      </div>
      <div id={metaId} className="exploration-reaction-prompt__meta">
        <span>Prevents {damageLabel}</span>
        <span>Costs {cost}</span>
      </div>
      <div id={outcomesId} className="exploration-reaction-prompt__outcomes" aria-label="Reaction outcome preview">
        <span><b>Cast</b> prevents {damageLabel}.</span>
        <span><b>Decline</b> lets {targetName} take the saved fall damage.</span>
      </div>
      <div className="exploration-reaction-prompt__actions">
        <button
          type="button"
          className="choice action"
          disabled={disabled}
          onClick={() => onResolve?.('feather_fall', prompt)}
        >
          <span className="idx" aria-hidden="true">FF</span>
          <span className="body">Cast Feather Fall</span>
        </button>
        <button
          type="button"
          className="choice"
          disabled={disabled}
          onClick={() => onResolve?.('decline', prompt)}
        >
          <span className="idx" aria-hidden="true">No</span>
          <span className="body">Decline</span>
        </button>
      </div>
    </div>
  )
}
