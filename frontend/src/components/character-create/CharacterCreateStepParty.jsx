import React from 'react'
import CharacterCreateStepPartyHeroPreview from './CharacterCreateStepPartyHeroPreview'
import CharacterCreateStepPartyPartySize from './CharacterCreateStepPartyPartySize'
import CharacterCreateStepPartyCompanions from './CharacterCreateStepPartyCompanions'

export default function CharacterCreateStepParty({ ctx }) {
  const {
    form,
    finalScores,
    partySize,
    setPartySize,
    companions,
    generatingParty,
    error,
    handleGenerateParty,
    playerCharacter,
  } = ctx

  return (
    <div className="step-pane">
      <div className="step-title">✧ 终章 · 同伴相逢 ✧</div>
      <div className="step-sub">你的冒险不会独自前行。AI 已为你组建了最合拍的队伍。</div>
      <CharacterCreateStepPartyHeroPreview
        form={form}
        finalScores={finalScores}
        playerCharacter={playerCharacter}
      />

      <CharacterCreateStepPartyPartySize
        partySize={partySize}
        setPartySize={setPartySize}
      />

      <div className="companions-title">
        <span className="orn">❦</span>
        <span className="t">你的队友</span>
        <span className="orn">❦</span>
      </div>

      <CharacterCreateStepPartyCompanions
        companions={companions}
        generatingParty={generatingParty}
        handleGenerateParty={handleGenerateParty}
        error={error}
      />
    </div>
  )
}
