import { buildCombatPreviewRows } from '../../utils/combat'
import { buildCombatRuleTags } from '../../utils/combatRuleTags'
import { buildConditionImpactTags, buildConditionSummaries } from '../../utils/conditionRules'
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
  const ruleTags = buildCombatRuleTags(prediction, entity)
  const inspect = buildEnemyInspectModel(entity)
  const badges = buildTargetBadges(entity, prediction)
  const conditionImpactTags = buildConditionImpactTags(entity.conditions || [], entity.condition_durations || {})

  return (
    <div className="target-card-wrap">
      <div className="target-card">
        <div className="target-head">
          <span className="name">{entity.name}</span>
          <span className="tag">目标</span>
        </div>
        <div className="target-summary-strip" aria-label={`目标摘要 ${entity.name}`}>
          {badges.map(badge => (
            <span key={`${badge.tone}-${badge.label}`} className={badge.tone || ''} title={badge.title || ''}>
              {badge.label}
            </span>
          ))}
        </div>
        <div className="target-hp-bar">
          <div style={{ width: `${Math.max(0, Math.min(100, (entity.hp_current / (entity.hp_max || 1)) * 100))}%` }} />
        </div>
        <div className="hit-pred">
          <span>HP <b>{entity.hp_current}/{entity.hp_max}</b> / AC <b>{entity.ac}</b></span>
        </div>

        {ruleTags.length > 0 && (
          <div className="target-rule-tags" aria-label={`攻击规则标签 ${entity.name}`}>
            {ruleTags.map(tag => (
              <span key={tag.key} className={tag.tone || ''} title={tag.title}>{tag.label}</span>
            ))}
          </div>
        )}

        {conditionImpactTags.length > 0 && (
          <div className="target-condition-impacts" aria-label={`状态影响 ${entity.name}`}>
            {conditionImpactTags.map(tag => (
              <span key={tag.key} className={tag.tone || ''} title={tag.title}>{tag.label}</span>
            ))}
          </div>
        )}

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
          <div className="enemy-inspect-sheet" aria-label={`敌人检视 ${entity.name}`}>
            <div className="enemy-inspect-head">
              <span>检视</span>
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
                <span>动作</span>
                <b>{inspect.actions}</b>
              </div>
              <div className={inspect.traitsHidden ? 'hidden-stat' : ''}>
                <span>特性</span>
                <b>{inspect.traits}</b>
              </div>
              <div className={inspect.tacticsHidden ? 'hidden-stat' : ''}>
                <span>战术</span>
                <b>{inspect.tactics}</b>
              </div>
            </div>
            {onInspect && (
              <div className="enemy-inspect-actions" aria-label={`检视操作 ${entity.name}`}>
                <button
                  className="btn-fantasy"
                  disabled={!canInspect || inspectBusy}
                  title="用察觉检视敌人态势"
                  onClick={() => onInspect('perception')}
                >
                  察觉
                </button>
                <button
                  className="btn-fantasy"
                  disabled={!canInspect || inspectBusy}
                  title="用调查分析敌人信息"
                  onClick={() => onInspect('investigation')}
                >
                  调查
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
    { label: entity.is_enemy ? '敌人' : entity.is_companion ? '队友' : '友方', tone: entity.is_enemy ? 'danger' : 'good' },
    { label: targetHealthLabel(entity), tone: targetHealthTone(entity) },
  ]

  if (entity.ac !== null && entity.ac !== undefined) badges.push({ label: `AC ${entity.ac}` })
  if (prediction?.hit_rate !== null && prediction?.hit_rate !== undefined) {
    badges.push({ label: `命中 ${formatHitRate(prediction.hit_rate)}`, tone: prediction.advantage ? 'good' : prediction.disadvantage ? 'bad' : '' })
  }

  const conditions = buildConditionSummaries(entity.conditions || [], entity.condition_durations || {})
  for (const condition of conditions.slice(0, 2)) {
    badges.push({
      label: condition.label,
      tone: condition.tone === 'buff' ? 'good' : 'bad',
      title: condition.title,
    })
  }

  if (conditions.length > 2) {
    badges.push({
      label: `+${conditions.length - 2} 状态`,
      tone: 'bad',
      title: conditions.slice(2).map(condition => condition.title).join(' / '),
    })
  }
  return badges
}

function targetHealthLabel(entity = {}) {
  const current = Number(entity.hp_current ?? 0)
  const max = Number(entity.hp_max || 0)
  if (current <= 0) return entity.is_enemy ? '已击败' : '倒地'
  if (!max) return '生命未知'
  const pct = current / max
  if (pct <= 0.25) return '危急'
  if (pct <= 0.5) return '重伤'
  if (pct < 1) return '受伤'
  return '健康'
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
