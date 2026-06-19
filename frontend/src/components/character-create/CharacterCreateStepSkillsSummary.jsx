import React from 'react'
import { ABILITY_ZH } from '../../data/dnd5e.js'

export default function CharacterCreateStepSkillsSummary({ form, skillConfig, chosenSkills, saveProfs }) {
  const complete = chosenSkills.length === skillConfig.count

  return (
    <>
      <div className="step-sub create-skills-summary" data-complete={complete ? 'true' : 'false'}>
        {form.char_class} 可选择{' '}
        <b className="create-skills-summary-count">{skillConfig.count}</b>
        {' '}项技能熟练 · 已选{' '}
        <b className="create-skills-summary-selected">
          {chosenSkills.length}
        </b>
      </div>

      {saveProfs.length > 0 && (
        <div className="create-note create-skills-save-note">
          <span className="lead">职业豁免熟练</span>
          （由 {form.char_class} 自动获得）：
          {saveProfs.map(k => ABILITY_ZH[k] || k).join(' · ')}
        </div>
      )}
    </>
  )
}
