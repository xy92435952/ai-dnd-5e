import { buildCombatPreviewRows } from '../../utils/combat'
import { buildEnemyInspectModel } from '../../utils/enemyInspect'

export default function TargetCard({
  entity,
  prediction,
  canInspect = false,
  inspectBusy = false,
  onInspect = null,
}) {
  if (!entity) return null

  const rows = buildCombatPreviewRows({ prediction, target: entity })
  const inspect = buildEnemyInspectModel(entity)

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

        {inspect && (
          <div className="enemy-inspect-sheet" aria-label={`Enemy inspect ${entity.name}`}>
            <div className="enemy-inspect-head">
              <span>INSPECT</span>
              <b>{inspect.revealLabel}</b>
            </div>
            <div className="enemy-inspect-grid">
              {inspect.rows.map(row => (
                <div key={row.label} className={row.hidden ? 'hidden-stat' : ''}>
                  <span>{row.label}</span>
                  <b>{row.value}</b>
                </div>
              ))}
            </div>
            <div className="enemy-inspect-lines">
              <div className={inspect.actionsHidden ? 'hidden-stat' : ''}>
                <span>ACT</span>
                <b>{inspect.actions}</b>
              </div>
              <div className={inspect.traitsHidden ? 'hidden-stat' : ''}>
                <span>TRT</span>
                <b>{inspect.traits}</b>
              </div>
              <div className={inspect.tacticsHidden ? 'hidden-stat' : ''}>
                <span>TAC</span>
                <b>{inspect.tactics}</b>
              </div>
            </div>
            {onInspect && (
              <div className="enemy-inspect-actions" aria-label={`Inspect actions ${entity.name}`}>
                <button
                  className="btn-fantasy"
                  disabled={!canInspect || inspectBusy}
                  onClick={() => onInspect('perception')}
                >
                  PER
                </button>
                <button
                  className="btn-fantasy"
                  disabled={!canInspect || inspectBusy}
                  onClick={() => onInspect('investigation')}
                >
                  INV
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
