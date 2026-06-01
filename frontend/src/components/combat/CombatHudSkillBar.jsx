import React from 'react'
import { JuiceAudio } from '../../juice'
import { SKILL_INFO } from '../../data/combat'
import { buildCombatPreviewRows, getSkillUnavailableReason } from '../../utils/combat'
import { buildCombatRuleTags } from '../../utils/combatRuleTags'

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
    <div>
      <div className="skill-bar">
        {skillViews.map(({ skill: s, stats, ruleTags, info, unavailableReason, canUse }) => {
          return (
            <div
              key={s.k}
              className={`slot-key ${s.kind} ${!canUse ? 'used' : ''}`}
              onClick={() => { if (canUse) onSkillClick(s) }}
              onMouseEnter={() => { try { JuiceAudio.hover() } catch {} }}
              title={unavailableReason || s.label || ''}
              aria-disabled={!canUse}
              style={{ cursor: canUse ? 'pointer' : 'not-allowed' }}
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
                    {unavailableReason && <span style={{ color: '#f47070', marginLeft: 6 }}>{unavailableReason}</span>}
                  </div>
                  {ruleTags.length > 0 && (
                    <div className="skill-rule-tags" aria-label={`${s.label} attack rule tags`}>
                      {ruleTags.map(tag => (
                        <span key={tag.key} className={tag.tone || ''} title={tag.title}>{tag.label}</span>
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
      <div className="slot-label-bar">
        {skillViews.map(({ skill: s, unavailableReason, canUse }) => (
          <span
            key={s.k}
            className={canUse ? 'ready' : 'blocked'}
            title={skillStatusTitle(s, unavailableReason)}
            aria-label={`${s.label || '—'}：${unavailableReason || '可用'}`}
          >
            {s.label || '—'}
          </span>
        ))}
      </div>
      {blockerSummary && (
        <div className={`skill-blocker-summary ${blockerSummary.tone}`} aria-label="技能限制提示">
          <b>限制</b>
          <span>{blockerSummary.text}</span>
        </div>
      )}
    </div>
  )
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
