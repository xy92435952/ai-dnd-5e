import React from 'react'
import CharacterCreateStepSkillsSummary from './CharacterCreateStepSkillsSummary'
import CharacterCreateStepSkillsGrid from './CharacterCreateStepSkillsGrid'

export default function CharacterCreateStepSkills({ ctx }) {
  const {
    form,
    skillConfig,
    chosenSkills,
    saveProfs,
    toggleSkill,
    openModal,
  } = ctx

  return (
    <div className="step-pane">
      <div className="step-title">✧ 第三章 · 所学所长 ✧</div>
      <CharacterCreateStepSkillsSummary
        form={form}
        skillConfig={skillConfig}
        chosenSkills={chosenSkills}
        saveProfs={saveProfs}
      />
      <CharacterCreateStepSkillsGrid
        skillConfig={skillConfig}
        chosenSkills={chosenSkills}
        toggleSkill={toggleSkill}
        openModal={openModal}
      />
    </div>
  )
}
