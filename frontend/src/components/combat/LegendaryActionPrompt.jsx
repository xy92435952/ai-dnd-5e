import { formatConditionWithDuration } from '../../utils/conditionRules'

export default function LegendaryActionPrompt({
  prompt,
  onUse,
  onSkip,
  variant = 'legendary',
}) {
  if (!prompt) return null

  const actions = Array.isArray(prompt.actions) ? prompt.actions : []
  const isLair = variant === 'lair'
  const actorName = isLair
    ? (prompt.source_name || prompt.actor_name || 'Lair')
    : (prompt.actor_name || '传奇敌人')
  const remaining = prompt.remaining ?? 0
  const uses = prompt.uses ?? 0
  const dialogLabel = isLair ? '巢穴动作窗口' : '传奇动作窗口'
  const title = isLair ? '巢穴动作' : '传奇动作'
  const contextLine = isLair
    ? `${actorName}${prompt.round_number ? ` · 第 ${prompt.round_number} 轮` : ''}`
    : `${actorName} · ${remaining}/${uses}`
  const skipLabel = isLair ? '跳过巢穴动作' : '跳过传奇动作'

  return (
    <div className="reaction-prompt-layer" role="dialog" aria-modal="true" aria-label={dialogLabel}>
      <section className="reaction-prompt-card legendary-action-prompt-card">
        <header className="reaction-prompt-head">
          <span className="reaction-prompt-icon" aria-hidden="true">*</span>
          <div>
            <p className="reaction-prompt-title">{title}</p>
            <p className="reaction-prompt-context">{contextLine}</p>
          </div>
        </header>

        {prompt.context && (
          <div className="reaction-prompt-meta">
            <span>{prompt.context}</span>
          </div>
        )}

        <div className="reaction-prompt-actions">
          {actions.length > 0 ? actions.map(action => {
            const targetRef = Array.isArray(action.target_ids) && action.target_ids.length
              ? action.target_ids
              : action.target_id
            return (
              <button
                key={action.id || action.name}
                className="btn-gold reaction-prompt-action"
                title={legendaryActionTitle(action)}
                onClick={() => onUse?.(isLair ? (prompt.source_id || prompt.actor_id) : prompt.actor_id, action.id, targetRef)}
              >
                <span>{action.name || action.id}</span>
                <small>{legendaryActionMeta(action)}</small>
              </button>
            )
          }) : (
            <div style={{ color: 'var(--parchment-dark)', fontSize: 12 }}>
              {isLair ? '当前没有可用巢穴动作。' : '当前没有可用传奇动作。'}
            </div>
          )}
          <button className="btn-ghost reaction-prompt-decline" onClick={() => onSkip?.(prompt)}>
            {skipLabel}
          </button>
        </div>
      </section>
    </div>
  )
}

function legendaryActionTitle(action = {}) {
  return [
    action.name,
    ...legendaryActionParts(action),
    action.description,
  ].filter(Boolean).join(' · ')
}

function legendaryActionMeta(action = {}) {
  return legendaryActionParts(action).join(' · ')
}

function legendaryActionParts(action = {}) {
  const saveAbility = action.save_ability || action.saving_throw || action.save
  const targetNames = Array.isArray(action.target_names)
    ? action.target_names.filter(Boolean).join('、')
    : ''
  const targetCount = Number(action.target_count || action.target_ids?.length || 0)
  const failedSaveConditions = legendaryActionFailedSaveConditions(action)
  const failedSaveMovement = legendaryActionFailedSaveMovement(action)
  const areaTemplate = legendaryActionAreaTemplate(action)
  return [
    action.cost !== undefined ? `消耗 ${action.cost}` : '',
    action.remaining_after !== undefined ? `剩余 ${action.remaining_after}` : '',
    targetCount > 1 ? `影响 ${targetCount}` : '',
    (targetNames || action.target_name) ? `目标 ${targetNames || action.target_name}` : '',
    saveAbility ? `${formatSaveAbility(saveAbility)}豁免` : '',
    action.save_dc !== undefined ? `DC ${action.save_dc}` : '',
    action.half_on_save ? '成功半伤' : '',
    failedSaveConditions ? `失败附加 ${failedSaveConditions}` : '',
    areaTemplate,
    failedSaveMovement,
    action.attack_bonus !== undefined ? `命中 ${formatSigned(action.attack_bonus)}` : '',
    action.damage_dice ? `伤害 ${action.damage_dice}${action.damage_type ? ` ${action.damage_type}` : ''}` : '',
  ].filter(Boolean)
}

function legendaryActionFailedSaveConditions(action = {}) {
  const rawConditions = Array.isArray(action.conditions_on_failed_save)
    ? action.conditions_on_failed_save
    : action.condition_on_failed_save
      ? [action.condition_on_failed_save]
      : []
  const duration = action.condition_duration_rounds ?? action.duration_rounds ?? action.condition_duration
  const durations = {}
  rawConditions.forEach(condition => {
    if (duration !== undefined && duration !== null) durations[condition] = duration
  })
  return rawConditions
    .map(condition => formatConditionWithDuration(condition, durations))
    .filter(Boolean)
    .join('、')
}

function legendaryActionFailedSaveMovement(action = {}) {
  const pushDistance = numericDistance(action.push_distance_ft ?? action.pushDistanceFt ?? action.push_ft ?? action.pushFeet)
  if (pushDistance !== null) return `失败推开 ${pushDistance}ft`
  const pullDistance = numericDistance(action.pull_distance_ft ?? action.pullDistanceFt ?? action.pull_ft ?? action.pullFeet)
  return pullDistance !== null ? `失败拉近 ${pullDistance}ft` : ''
}

function legendaryActionAreaTemplate(action = {}) {
  const template = action.area_template || action.template || action.shape
  if (!template) return ''
  const range = numericDistance(action.area_range_ft ?? action.areaRangeFt ?? action.radius_ft ?? action.radiusFt)
  return range !== null ? `范围 ${range}ft ${template}` : `范围 ${template}`
}

function numericDistance(value) {
  if (value === undefined || value === null || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatSaveAbility(value) {
  const labels = {
    str: '力量',
    dex: '敏捷',
    con: '体质',
    int: '智力',
    wis: '感知',
    cha: '魅力',
  }
  return labels[String(value || '').toLowerCase()] || value
}

function formatSigned(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return `${value}`
  return number >= 0 ? `+${number}` : `${number}`
}
