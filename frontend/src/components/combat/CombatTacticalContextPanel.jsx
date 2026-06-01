export default function CombatTacticalContextPanel({ context }) {
  if (!context?.hasContext) return null

  const objective = context.objectives?.[0] || '守住阵地'
  const terrain = compactLabel([
    context.cover?.[0],
    context.terrain?.[0],
  ]) || '开阔地'
  const hazard = context.hazards?.[0] || (context.counts?.hazard ? '已标记危险' : '无')
  const balance = compactLabel([
    context.difficulty && difficultyLabel(context.difficulty),
    context.targetDifficulty && `目标 ${difficultyLabel(context.targetDifficulty)}`,
    context.environmentAdjustedDifficulty && `环境 ${difficultyLabel(context.environmentAdjustedDifficulty)}`,
  ])

  return (
    <aside className="tactical-context-panel" aria-label="战术上下文">
      <div className="tactical-context-head">
        <span>战术</span>
        <b>{context.title}</b>
      </div>
      <div className="tactical-context-grid">
        <ContextMetric label="目标" value={objective} />
        <ContextMetric label="地形" value={terrain} />
        <ContextMetric label="风险" value={hazard} />
        <ContextMetric label="强度" value={balance || '未知'} />
      </div>
      {context.detailGroups?.length > 0 && (
        <div className="tactical-context-details" aria-label="战术要素明细">
          {context.detailGroups.map(group => (
            <div key={group.key} title={group.title}>
              <span>{group.label}</span>
              <b>{group.value}</b>
            </div>
          ))}
        </div>
      )}
      <div className="tactical-context-pills" aria-label="战术计数">
        <span>掩护 {context.counts?.cover || 0}</span>
        <span>困难地形 {context.counts?.difficult || 0}</span>
        <span>危险 {context.counts?.hazard || 0}</span>
        <span>目标点 {context.counts?.objective || 0}</span>
        {context.roleSummary && <span>{context.roleSummary}</span>}
        {context.environmentPressure && <span>环境 {pressureLabel(context.environmentPressure)}</span>}
        {context.stagedCount > 0 && <span>预置 {context.stagedCount}</span>}
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

function difficultyLabel(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return ({
    easy: '简单',
    medium: '中等',
    hard: '困难',
    deadly: '致命',
  })[normalized] || String(value || '')
}

function pressureLabel(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return ({
    low: '低压',
    light: '低压',
    moderate: '中压',
    medium: '中压',
    heavy: '高压',
    severe: '严峻',
  })[normalized] || String(value || '')
}
