import React from 'react'
import { JuiceAudio } from '../../juice'
import { SKILL_INFO } from '../../data/combat'
import { computeSkillStats } from '../../utils/combat'

export default function CombatHudSkillBar({ skillBar, session, entities, selectedTarget, onSkillClick, isPlayerTurn, syncBlocked = false }) {
  return (
    <div>
      <div className="skill-bar">
        {skillBar.map(s => {
          const stats = computeSkillStats(s, session?.player, entities[selectedTarget])
          const info = SKILL_INFO[s.k] || {}
          return (
            <div
              key={s.k}
              className={`slot-key ${s.kind} ${!s.available ? 'used' : ''}`}
              onClick={() => !syncBlocked && onSkillClick(s)}
              onMouseEnter={() => { try { JuiceAudio.hover() } catch {} }}
              style={{ cursor: s.available && isPlayerTurn && !syncBlocked ? 'pointer' : 'not-allowed' }}
            >
              <span className="hot">{s.key}</span>
              <span className="glyph">{s.glyph}</span>
              {s.cost && <span className="cost">{String(s.cost).split('·')[0]}</span>}

              {s.label && (
                <div className="skill-tooltip">
                  <div className="t-name">{s.label}</div>
                  <div className="t-meta">
                    {s.kind === 'attack' ? '攻击' : s.kind === 'spell' ? '法术' : s.kind === 'bonus' ? '附赠' : s.kind === 'move' ? '移动' : '—'}
                    {' · '}{s.cost || '—'}
                    {syncBlocked && <span style={{ color: 'var(--parchment-dark)', marginLeft: 6 }}>同步中</span>}
                    {!s.available && <span style={{ color: '#f47070', marginLeft: 6 }}>✕ 不可用</span>}
                  </div>
                  {stats && stats.length > 0 && stats.map((r, ri) => (
                    <div key={ri} className="t-row">
                      <span>{r.label}</span>
                      <b>{r.value}</b>
                    </div>
                  ))}
                  {(s.reason || info.desc) && (
                    <div className="t-desc">{s.reason || info.desc}</div>
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
