import { buildCombatRuleTags } from '../../utils/combatRuleTags'
import { buildConditionImpactTags } from '../../utils/conditionRules'

export default function CombatHudIntentSummary({
  turnState,
  skillBar = [],
  selectedTarget,
  entities = {},
  prediction = null,
  isPlayerTurn = false,
  isProcessing = false,
  syncBlocked = false,
  moveMode = false,
  helpMode = false,
  isRanged = false,
  selectedWeaponName = '',
}) {
  const selectedTargetEntity = selectedTarget ? entities?.[selectedTarget] : null
  const status = buildIntentStatus({
    isPlayerTurn,
    isProcessing,
    syncBlocked,
    moveMode,
    helpMode,
    selectedTargetEntity,
    skillBar,
  })
  const economy = buildEconomy(turnState)
  const target = buildTargetSummary({ selectedTargetEntity, prediction })
  const ruleChips = selectedTargetEntity
    ? [
        ...buildCombatRuleTags(prediction, selectedTargetEntity),
        ...buildConditionImpactTags(selectedTargetEntity.conditions || [], selectedTargetEntity.condition_durations || {})
          .map(tag => ({ ...tag, key: `condition-${tag.key}` })),
      ].slice(0, 5)
    : []
  const modeLabel = buildModeLabel({ isRanged, selectedWeaponName })

  return (
    <section className="combat-intent-summary" aria-label="战斗意图摘要">
      <div className="combat-intent-head">
        <span className={`combat-intent-status ${status.tone}`} role="status" aria-live="polite">
          <b>{status.label}</b>
          <em>{status.detail}</em>
        </span>
        {modeLabel && <span className="combat-intent-mode" title={modeLabel}>{modeLabel}</span>}
      </div>

      <div className="combat-intent-economy" role="list" aria-label="本回合资源">
        {economy.map(item => (
          <span
            key={item.key}
            className={`combat-intent-chip ${item.tone}`}
            role="listitem"
            aria-label={`${item.label} ${item.value}`}
          >
            <b>{item.label}</b>
            <em>{item.value}</em>
          </span>
        ))}
      </div>

      <div className={`combat-intent-target ${target ? '' : 'empty'}`} aria-label="当前战斗目标">
        <span>目标</span>
        {target ? (
          <>
            <b title={target.name}>{target.name}</b>
            <em>{target.detail}</em>
          </>
        ) : (
          <>
            <b>未选择</b>
            <em>{status.targetHint}</em>
          </>
        )}
      </div>

      {ruleChips.length > 0 && (
        <div className="combat-intent-rules" role="list" aria-label="目标规则摘要">
          {ruleChips.map(chip => (
            <span
              key={chip.key}
              className={chip.tone || ''}
              title={chip.title || chip.label}
              role="listitem"
              aria-label={chip.title || chip.label}
            >
              {chip.label}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}

function buildIntentStatus({
  isPlayerTurn,
  isProcessing,
  syncBlocked,
  moveMode,
  helpMode,
  selectedTargetEntity,
  skillBar = [],
}) {
  if (syncBlocked) {
    return {
      label: '同步暂停',
      detail: '等待房间状态恢复',
      targetHint: '同步恢复后再选择',
      tone: 'blocked',
    }
  }
  if (isProcessing) {
    return {
      label: '结算中',
      detail: '等待上一动作写入',
      targetHint: '结算完成后再选择',
      tone: 'processing',
    }
  }
  if (!isPlayerTurn) {
    return {
      label: '观战',
      detail: '等待你的回合',
      targetHint: '可以先观察敌我位置',
      tone: 'waiting',
    }
  }
  if (helpMode) {
    return {
      label: '协助模式',
      detail: selectedTargetEntity ? '确认队友目标' : '选择一名队友',
      targetHint: '选择要协助的队友',
      tone: selectedTargetEntity ? 'ready' : 'warn',
    }
  }
  if (moveMode) {
    return {
      label: '移动模式',
      detail: '在战场选择落点',
      targetHint: '移动不需要目标',
      tone: 'ready',
    }
  }
  if (selectedTargetEntity) {
    return {
      label: '目标锁定',
      detail: selectedTargetEntity.is_enemy ? '评估攻击与法术' : '评估协助或治疗',
      targetHint: '已锁定目标',
      tone: 'ready',
    }
  }
  if (hasTargetRequiredOption(skillBar)) {
    return {
      label: '选择目标',
      detail: '攻击或法术需要目标',
      targetHint: '先点选战场单位',
      tone: 'warn',
    }
  }
  return {
    label: '可行动',
    detail: '选择动作或结束回合',
    targetHint: '可直接执行非目标动作',
    tone: 'ready',
  }
}

function buildEconomy(turnState = {}) {
  const movementMax = readNumber(turnState?.movement_max, 6)
  const movementUsed = readNumber(turnState?.movement_used, 0)
  const movementLeft = Math.max(0, movementMax - movementUsed)
  return [
    buildSpentChip('动作', turnState?.action_used),
    buildSpentChip('附赠', turnState?.bonus_action_used),
    {
      key: 'move',
      label: '移动',
      value: `${movementLeft}/${movementMax}`,
      tone: movementLeft > 0 ? 'ready' : 'spent',
    },
    buildSpentChip('反应', turnState?.reaction_used),
  ]
}

function buildSpentChip(label, used) {
  return {
    key: label,
    label,
    value: used ? '已用' : '可用',
    tone: used ? 'spent' : 'ready',
  }
}

function buildTargetSummary({ selectedTargetEntity, prediction }) {
  if (!selectedTargetEntity) return null
  const side = selectedTargetEntity.is_enemy
    ? '敌方'
    : selectedTargetEntity.is_companion || selectedTargetEntity.is_player || selectedTargetEntity.is_ally
      ? '友方'
      : '单位'
  const parts = [side]
  const hp = selectedTargetEntity.hp_current ?? selectedTargetEntity.hp
  const hpMax = selectedTargetEntity.hp_max ?? selectedTargetEntity.max_hp
  if (hp !== null && hp !== undefined && hpMax !== null && hpMax !== undefined) {
    parts.push(`HP ${hp}/${hpMax}`)
  }
  if (selectedTargetEntity.ac !== null && selectedTargetEntity.ac !== undefined) {
    parts.push(`AC ${selectedTargetEntity.ac}`)
  }
  if (prediction?.hit_rate !== null && prediction?.hit_rate !== undefined) {
    parts.push(`命中 ${formatPercent(prediction.hit_rate)}`)
  }
  return {
    name: selectedTargetEntity.name || '目标',
    detail: parts.join(' / '),
  }
}

function buildModeLabel({ isRanged, selectedWeaponName }) {
  const mode = isRanged ? '远程' : '近战'
  const weapon = String(selectedWeaponName || '').trim()
  if (weapon) return `${mode} / ${weapon}`
  return isRanged ? mode : ''
}

function hasTargetRequiredOption(skillBar = []) {
  return skillBar.some(skill => {
    if (!skill || skill.available === false) return false
    if (skill.requires_target || skill.needs_target || skill.target_required || skill.targeting?.requires_target) return true
    return skill.kind === 'attack'
  })
}

function readNumber(value, fallback) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function formatPercent(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '--'
  return `${Math.round((number <= 1 ? number * 100 : number))}%`
}
