import React from 'react'
import CharacterCreateStepSpellsHeader from './CharacterCreateStepSpellsHeader'
import CharacterCreateStepSpellsCantrips from './CharacterCreateStepSpellsCantrips'
import CharacterCreateStepSpellsKnown from './CharacterCreateStepSpellsKnown'

export default function CharacterCreateStepSpells({ ctx }) {
  const {
    classEnKey,
    classInfo,
    options,
    isSpellcaster,
    cantripCount,
    spellCount,
    availableCantrips,
    availableSpells,
    chosenCantrips,
    chosenSpells,
    toggleCantrip,
    toggleSpell,
  } = ctx

  if (!isSpellcaster) return null

  return (
    <div className="step-pane">
      <div className="step-title">✧ 第五章 · 秘术与祷言 ✧</div>
      <CharacterCreateStepSpellsHeader
        classEnKey={classEnKey}
        classInfo={classInfo}
        options={options}
      />
      <CharacterCreateStepSpellsCantrips
        cantripCount={cantripCount}
        chosenCantrips={chosenCantrips}
        availableCantrips={availableCantrips}
        toggleCantrip={toggleCantrip}
      />
      <CharacterCreateStepSpellsKnown
        spellCount={spellCount}
        chosenSpells={chosenSpells}
        availableSpells={availableSpells}
        toggleSpell={toggleSpell}
      />
    </div>
  )
}
