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
  const badges = buildTargetBadges(entity, prediction)

  return (
    <div className="target-card-wrap">
      <div className="target-card">
        <div className="target-head">
          <span className="name">{entity.name}</span>
          <span className="tag">TARGET</span>
        </div>
        <div className="target-summary-strip" aria-label={`Target summary ${entity.name}`}>
          {badges.map(badge => (
            <span key={`${badge.tone}-${badge.label}`} className={badge.tone || ''}>{badge.label}</span>
          ))}
        </div>
        <div className="target-hp-bar">
          <div style={{ width: `${Math.max(0, Math.min(100, (entity.hp_current / (entity.hp_max || 1)) * 100))}%` }} />
        </div>
        <div className="hit-pred">
          <span>HP <b>{entity.hp_current}/{entity.hp_max}</b> / AC <b>{entity.ac}</b></span>
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

function buildTargetBadges(entity = {}, prediction = null) {
  const badges = [
    { label: entity.is_enemy ? 'Enemy' : entity.is_companion ? 'Companion' : 'Ally', tone: entity.is_enemy ? 'danger' : 'good' },
    { label: targetHealthLabel(entity), tone: targetHealthTone(entity) },
  ]

  if (entity.ac !== null && entity.ac !== undefined) badges.push({ label: `AC ${entity.ac}` })
  if (prediction?.hit_rate !== null && prediction?.hit_rate !== undefined) {
    badges.push({ label: `Hit ${formatHitRate(prediction.hit_rate)}`, tone: prediction.advantage ? 'good' : prediction.disadvantage ? 'bad' : '' })
  }

  const conditions = Array.isArray(entity.conditions)
    ? entity.conditions.map(formatCondition).filter(Boolean)
    : []
  for (const condition of conditions.slice(0, 2)) {
    badges.push({ label: condition, tone: 'bad' })
  }

  if (conditions.length > 2) badges.push({ label: `+${conditions.length - 2} cond`, tone: 'bad' })
  return badges
}

function targetHealthLabel(entity = {}) {
  const current = Number(entity.hp_current ?? 0)
  const max = Number(entity.hp_max || 0)
  if (current <= 0) return entity.is_enemy ? 'Defeated' : 'Down'
  if (!max) return 'Unknown HP'
  const pct = current / max
  if (pct <= 0.25) return 'Critical'
  if (pct <= 0.5) return 'Bloodied'
  if (pct < 1) return 'Wounded'
  return 'Fresh'
}

function targetHealthTone(entity = {}) {
  const current = Number(entity.hp_current ?? 0)
  const max = Number(entity.hp_max || 0)
  if (current <= 0) return 'dead'
  if (!max) return ''
  const pct = current / max
  if (pct <= 0.25) return 'bad'
  if (pct <= 0.5) return 'warning'
  return 'good'
}

function formatHitRate(value) {
  const number = Number(value)
  if (Number.isNaN(number)) return '--'
  return `${Math.round((number <= 1 ? number * 100 : number))}%`
}

function formatCondition(value) {
  if (typeof value === 'string') return value
  if (!value || typeof value !== 'object') return ''
  return String(value.name || value.condition || value.type || value.id || '')
}
