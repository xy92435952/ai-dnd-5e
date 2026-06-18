import React from 'react'
import { JuiceAudio } from '../../juice'
import { SKILL_INFO } from '../../data/combat'
import { buildCombatPreviewRows, getSkillUnavailableReason } from '../../utils/combat'
import { buildCombatRuleTags } from '../../utils/combatRuleTags'
import { buildConditionImpactTags } from '../../utils/conditionRules'

const SKILL_KIND_LABELS = {
  attack: '攻击',
  spell: '法术',
  action: '动作',
  bonus: '附赠',
  move: '移动',
  item: '物品',
}

const PREDICTED_ATTACK_SKILLS = new Set(['atk', 'sneak', 'smite', 'firebolt', 'sacred_flame'])

export default function CombatHudSkillBar({
  skillBar,
  session,
  entities = {},
  selectedTarget,
  turnState,
  prediction = null,
  onSkillClick,
  isPlayerTurn,
  isProcessing = false,
  syncBlocked = false,
}) {
  const selectedTargetEntity = entities[selectedTarget]
  const selectedTargetRuleTags = selectedTargetEntity && prediction
    ? buildCombatRuleTags(prediction, selectedTargetEntity)
    : []
  const attackPreviewSummary = buildAttackPreviewSummary({
    prediction,
    target: selectedTargetEntity,
    ruleTags: selectedTargetRuleTags,
  })
  const skillViews = skillBar.map(s => {
    const canUsePrediction = PREDICTED_ATTACK_SKILLS.has(s.k)
    const stats = buildCombatPreviewRows({
      prediction: canUsePrediction ? prediction : null,
      skill: s,
      player: session?.player,
      target: selectedTargetEntity,
    })
    const ruleTags = canUsePrediction
      ? buildCombatRuleTags(prediction, selectedTargetEntity)
      : []
    const info = SKILL_INFO[s.k] || {}
    const unavailableReason = getSkillUnavailableReason({
      skill: s,
      turnState,
      isPlayerTurn,
      syncBlocked,
      isProcessing,
      selectedTarget,
    })
    return {
      skill: s,
      stats,
      ruleTags,
      info,
      unavailableReason,
      canUse: !unavailableReason,
    }
  })
  const blockerSummary = buildSkillBlockerSummary(skillViews)

  return (
    <section className="combat-skill-panel" aria-label="战斗技能栏">
      <div className="skill-bar" role="list" aria-label="可用战斗技能">
        {skillViews.map(({ skill: s, stats, ruleTags, info, unavailableReason, canUse }) => {
          return (
            <div
              key={s.k}
              className={`slot-key ${s.kind} ${!canUse ? 'used' : ''}`}
              role="button"
              tabIndex={canUse ? 0 : -1}
              onClick={() => { if (canUse) onSkillClick(s) }}
              onKeyDown={(event) => {
                if (!canUse) return
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSkillClick(s)
                }
              }}
              onMouseEnter={() => { try { JuiceAudio.hover() } catch {} }}
              title={unavailableReason || s.label || ''}
              aria-disabled={!canUse}
              aria-label={skillButtonLabel(s, unavailableReason)}
            >
              <span className="hot">{s.key}</span>
              <span className="glyph">{s.glyph}</span>
              {s.cost && <span className="cost">{String(s.cost).split('·')[0]}</span>}

              {s.label && (
                <div className="skill-tooltip">
                  <div className="t-name">{s.label}</div>
                  <div className="t-meta">
                    {SKILL_KIND_LABELS[s.kind] || '—'}
                    {' · '}{s.cost || '—'}
                    {unavailableReason && <span className="skill-unavailable-reason">{unavailableReason}</span>}
                  </div>
                  {ruleTags.length > 0 && (
                    <div className="skill-rule-tags" role="list" aria-label={`${s.label} 攻击规则标签`}>
                      {ruleTags.map(tag => (
                        <span key={tag.key} className={tag.tone || ''} title={tag.title} role="listitem">{tag.label}</span>
                      ))}
                    </div>
                  )}
                  {stats && stats.length > 0 && stats.map((r, ri) => (
                    <div key={ri} className={`t-row ${r.tone || ''}`}>
                      <span>{r.label}</span>
                      <b>{r.value}</b>
                    </div>
                  ))}
                  {(unavailableReason || s.reason || info.desc) && (
                    <div className="t-desc">{unavailableReason || s.reason || info.desc}</div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <div className="slot-label-bar" role="list" aria-label="技能可用状态">
        {skillViews.map(({ skill: s, unavailableReason, canUse }) => (
          <span
            key={s.k}
            className={canUse ? 'ready' : 'blocked'}
            title={skillStatusTitle(s, unavailableReason)}
            role="listitem"
            aria-label={`${s.label || '—'}：${unavailableReason || '可用'}`}
          >
            {s.label || '—'}
          </span>
        ))}
      </div>
      {attackPreviewSummary && (
        <div className="skill-rule-summary" aria-label="当前攻击预览">
          <b title={attackPreviewSummary.targetName}>{attackPreviewSummary.targetName}</b>
          <div role="list" aria-label="攻击预览标签">
            {attackPreviewSummary.chips.map(chip => (
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
        </div>
      )}
      {blockerSummary && (
        <div className={`skill-blocker-summary ${blockerSummary.tone}`} role="status" aria-live="polite" aria-label="技能限制提示">
          <b>限制</b>
          <span>{blockerSummary.text}</span>
        </div>
      )}
    </section>
  )
}

function buildAttackPreviewSummary({ prediction = null, target = null, ruleTags = [] } = {}) {
  if (!prediction || !target) return null

  const chips = []
  if (prediction.hit_rate !== null && prediction.hit_rate !== undefined) {
    chips.push({
      key: 'hit-rate',
      label: `命中 ${formatPercent(prediction.hit_rate)}`,
      tone: prediction.advantage ? 'good' : prediction.disadvantage ? 'bad' : '',
      title: `对 ${target.name || '目标'} 的预计命中率。`,
    })
  }

  for (const tag of ruleTags.slice(0, 4)) {
    chips.push(tag)
  }

  const conditionTags = buildConditionImpactTags(target.conditions || [], target.condition_durations || {})
    .map(tag => ({
      ...tag,
      key: `condition-${tag.key}`,
    }))
  const remainingSlots = Math.max(0, 6 - chips.length)
  for (const tag of conditionTags.slice(0, remainingSlots)) {
    chips.push(tag)
  }

  if (!chips.length) return null
  return {
    targetName: target.name || '目标',
    chips,
  }
}

function buildSkillBlockerSummary(skillViews = []) {
  const blocked = skillViews.filter(view => view.unavailableReason)
  if (!blocked.length) return null

  const byReason = new Map()
  blocked.forEach(view => {
    const list = byReason.get(view.unavailableReason) || []
    list.push(view.skill?.label || view.skill?.k || '技能')
    byReason.set(view.unavailableReason, list)
  })

  const reason = [...byReason.keys()].sort((a, b) => reasonPriority(a) - reasonPriority(b))[0]
  const labels = byReason.get(reason) || []
  const shown = labels.slice(0, 3).join('、')
  const more = labels.length > 3 ? ` 等 ${labels.length} 项` : ''
  return {
    tone: reason.includes('选择目标') ? 'warn' : 'blocked',
    text: `${reason}：${shown}${more}`,
  }
}

function reasonPriority(reason = '') {
  const priorities = [
    '等待战斗同步恢复',
    '等待你的回合',
    '正在结算上一项动作',
    '本回合动作已使用',
    '本回合附赠动作已使用',
    '本回合移动力已用尽',
    '需要先完成主手攻击',
    '需要先选择目标',
    '本回合反应已使用',
  ]
  const index = priorities.findIndex(item => reason.includes(item))
  return index >= 0 ? index : priorities.length
}

function skillStatusTitle(skill = {}, unavailableReason = '') {
  const kindLabel = SKILL_KIND_LABELS[skill.kind] || '—'
  return [
    skill.label || '—',
    kindLabel,
    skill.cost && skill.cost !== kindLabel ? skill.cost : '',
    unavailableReason || '可用',
  ].filter(Boolean).join(' · ')
}

function skillButtonLabel(skill = {}, unavailableReason = '') {
  const status = unavailableReason || '可用'
  const cost = skill.cost ? `，消耗 ${skill.cost}` : ''
  const key = skill.key ? `，快捷键 ${skill.key}` : ''
  return `${skill.label || '技能'}：${status}${cost}${key}`
}

function formatPercent(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '--'
  return `${Math.round((number <= 1 ? number * 100 : number))}%`
}
