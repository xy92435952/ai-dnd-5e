import React from 'react'
import CharacterCreateStepEquipmentBackground from './CharacterCreateStepEquipmentBackground'
import CharacterCreateStepEquipmentLanguages from './CharacterCreateStepEquipmentLanguages'

export default function CharacterCreateStepEquipment({ ctx }) {
  const {
    form,
    classEnKey,
    options,
    equipChoice,
    setEquipChoice,
    getItemZh,
    bonusLanguages,
    setBonusLanguages,
  } = ctx

  return (
    <div className="step-pane">
      <div className="step-title">✧ 第四章 · 起始装备 ✧</div>
      <div className="step-sub">这是你踏上旅程时所携之物。</div>

      <div className="equip-list">
        {(options.starting_equipment?.[classEnKey] || []).map((opt, idx) => {
          const sel = equipChoice === idx
          return (
            <div
              key={idx}
              className={`equip-card ${sel ? 'sel' : ''}`}
              onClick={() => setEquipChoice(idx)}
            >
              <div className="equip-head">
                <div className={`radio ${sel ? 'on' : ''}`}>{sel && <div className="dot" />}</div>
                <div className="equip-name">{opt.label}</div>
              </div>
              <div className="equip-items">
                {opt.items.map((item, j) => {
                  const glyph = item.slot === 'weapon' ? '⚔'
                    : item.slot === 'armor' ? '🛡'
                    : item.slot === 'offhand' ? '◈' : '◇'
                  return (
                    <span key={j} className="item-chip">
                      {glyph} {getItemZh(item.name)}
                    </span>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      <CharacterCreateStepEquipmentBackground form={form} options={options} />
      <CharacterCreateStepEquipmentLanguages
        form={form}
        options={options}
        bonusLanguages={bonusLanguages}
        setBonusLanguages={setBonusLanguages}
      />
    </div>
  )
}
