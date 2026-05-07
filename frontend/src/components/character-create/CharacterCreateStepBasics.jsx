import React from 'react'
import CharacterCreateStepBasicsIdentity from './CharacterCreateStepBasicsIdentity'
import CharacterCreateStepBasicsFeatures from './CharacterCreateStepBasicsFeatures'
import CharacterCreateStepBasicsDetails from './CharacterCreateStepBasicsDetails'

export default function CharacterCreateStepBasics({ ctx }) {
  return (
    <div className="step-pane">
      <div className="step-title">✧ 第一章 · 身世与血脉 ✧</div>
      <div className="step-sub">姓名决定传说，血脉决定起点，职业决定道路。</div>
      <CharacterCreateStepBasicsIdentity ctx={ctx} />
      <CharacterCreateStepBasicsFeatures ctx={ctx} />
      <CharacterCreateStepBasicsDetails ctx={ctx} />
    </div>
  )
}
