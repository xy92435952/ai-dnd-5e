export default function CombatTacticalContextPanel({ context }) {
  if (!context?.hasContext) return null

  const objective = context.objectives?.[0] || 'Hold the field'
  const terrain = compactLabel([
    context.cover?.[0],
    context.terrain?.[0],
  ]) || 'Open ground'
  const hazard = context.hazards?.[0] || (context.counts?.hazard ? 'Mapped hazard' : 'None')
  const balance = compactLabel([
    context.difficulty && context.difficulty.toUpperCase(),
    context.targetDifficulty && `target ${context.targetDifficulty}`,
    context.environmentAdjustedDifficulty && `env ${context.environmentAdjustedDifficulty}`,
  ])

  return (
    <aside className="tactical-context-panel" aria-label="Tactical context">
      <div className="tactical-context-head">
        <span>TACTICS</span>
        <b>{context.title}</b>
      </div>
      <div className="tactical-context-grid">
        <ContextMetric label="OBJ" value={objective} />
        <ContextMetric label="TER" value={terrain} />
        <ContextMetric label="HZD" value={hazard} />
        <ContextMetric label="BAL" value={balance || 'Unknown'} />
      </div>
      {context.detailGroups?.length > 0 && (
        <div className="tactical-context-details" aria-label="Tactical feature details">
          {context.detailGroups.map(group => (
            <div key={group.key} title={group.title}>
              <span>{group.label}</span>
              <b>{group.value}</b>
            </div>
          ))}
        </div>
      )}
      <div className="tactical-context-pills" aria-label="Tactical counts">
        <span>Cover {context.counts?.cover || 0}</span>
        <span>Difficult {context.counts?.difficult || 0}</span>
        <span>Hazard {context.counts?.hazard || 0}</span>
        <span>Objective {context.counts?.objective || 0}</span>
        {context.environmentPressure && <span>Env {context.environmentPressure}</span>}
        {context.stagedCount > 0 && <span>Staged {context.stagedCount}</span>}
      </div>
    </aside>
  )
}

function ContextMetric({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}

function compactLabel(parts) {
  return parts.filter(Boolean).join(' / ')
}
