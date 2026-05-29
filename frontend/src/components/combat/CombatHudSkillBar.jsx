import React from 'react'
import { JuiceAudio } from '../../juice'
import { SKILL_INFO } from '../../data/combat'
import { buildCombatPreviewRows, getSkillUnavailableReason } from '../../utils/combat'

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
  entities,
  selectedTarget,
  turnState,
  prediction = null,
  onSkillClick,
  isPlayerTurn,
  isProcessing = false,
  syncBlocked = false,
}) {
  return (
    <div>
      <div className="skill-bar">
        {skillBar.map(s => {
          const selectedTargetEntity = entities[selectedTarget]
          const canUsePrediction = PREDICTED_ATTACK_SKILLS.has(s.k)
          const stats = buildCombatPreviewRows({
            prediction: canUsePrediction ? prediction : null,
            skill: s,
            player: session?.player,
            target: selectedTargetEntity,
          })
          const info = SKILL_INFO[s.k] || {}
          const unavailableReason = getSkillUnavailableReason({
            skill: s,
            turnState,
            isPlayerTurn,
            syncBlocked,
            isProcessing,
            selectedTarget,
          })
          const canUse = !unavailableReason
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
        {skillBar.map(s => <span key={s.k}>{s.label || '—'}</span>)}
      </div>
    </div>
  )
}
