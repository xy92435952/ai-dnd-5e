import React from 'react'
import { SKILL_INFO, ABILITY_ZH } from '../../data/dnd5e.js'

export default function CharacterCreateStepSkillsGrid({ skillConfig, chosenSkills, toggleSkill, openModal }) {
  return (
    <div className="skill-grid create-skills-grid" role="list" aria-label="Skill choices">
      {skillConfig.options.map(skill => {
        const sel = chosenSkills.includes(skill)
        const dis = !sel && chosenSkills.length >= skillConfig.count
        const skillData = SKILL_INFO[skill]
        return (
          <div
            key={skill}
            className={`skill-card ${sel ? 'sel' : ''} ${dis ? 'dis' : ''}`}
            role="listitem"
            aria-label={`${skill} ${ABILITY_ZH[skillData?.ability] || skillData?.ability || ''}`}
            data-selected={sel ? 'true' : 'false'}
            data-disabled={dis ? 'true' : 'false'}
            onClick={() => !dis && toggleSkill(skill)}
          >
            <div className="s-check">{sel ? '✓' : '○'}</div>
            <div className="s-name">
              {skill}
              {skillData && (
                <button
                  type="button"
                  onClick={e => { e.stopPropagation(); openModal('skill', skill) }}
                  className="create-skills-info-button"
                  aria-label={`${skill} details`}
                >
                  ⓘ
                </button>
              )}
            </div>
            <div className="s-ab">{ABILITY_ZH[skillData?.ability] || skillData?.ability || ''}</div>
          </div>
        )
      })}
    </div>
  )
}
