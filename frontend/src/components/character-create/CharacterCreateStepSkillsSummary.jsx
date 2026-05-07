import React from 'react'
import { ABILITY_ZH } from '../../data/dnd5e.js'

export default function CharacterCreateStepSkillsSummary({ form, skillConfig, chosenSkills, saveProfs }) {
  return (
    <>
      <div className="step-sub">
        {form.char_class} 可选择 <b style={{ color: 'var(--amber)' }}>{skillConfig.count}</b> 项技能熟练 · 已选{' '}
        <b style={{ color: chosenSkills.length === skillConfig.count ? 'var(--emerald-light)' : 'var(--amber)' }}>
          {chosenSkills.length}
        </b>
      </div>

      {saveProfs.length > 0 && (
        <div className="create-note">
          <span className="lead">职业豁免熟练</span>
          （由 {form.char_class} 自动获得）：
          {saveProfs.map(k => ABILITY_ZH[k] || k).join(' · ')}
        </div>
      )}
    </>
  )
}
