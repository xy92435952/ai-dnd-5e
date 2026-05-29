import { buildCombatPreviewRows } from '../../utils/combat'

export default function TargetCard({ entity, prediction }) {
  if (!entity) return null

  const rows = buildCombatPreviewRows({ prediction, target: entity })

  return (
    <div className="target-card-wrap">
      <div className="target-card">
        <div className="target-head">
          <span className="name">◈ {entity.name}</span>
          <span className="tag">TARGET</span>
        </div>
        <div className="target-hp-bar">
          <div style={{ width: `${Math.max(0, Math.min(100, (entity.hp_current / (entity.hp_max || 1)) * 100))}%` }} />
        </div>
        <div className="hit-pred">
          <span>HP <b>{entity.hp_current}/{entity.hp_max}</b> · AC <b>{entity.ac}</b></span>
        </div>

        {rows.length > 0 && (
          <div className="target-preview">
            {rows.map(row => (
              <div key={`${row.label}-${row.value}`} className={`preview-row ${row.tone || ''}`}>
                <span>{row.label}</span>
                <b>{row.value}</b>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
