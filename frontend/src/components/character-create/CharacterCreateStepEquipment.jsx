import React from 'react'
import CharacterCreateStepEquipmentBackground from './CharacterCreateStepEquipmentBackground'
import CharacterCreateStepEquipmentLanguages from './CharacterCreateStepEquipmentLanguages'

function getSlotGlyph(slot) {
  if (slot === 'weapon' || slot === 'weapon2') return '⚔'
  if (slot === 'armor') return '🛡'
  if (slot === 'offhand') return '◈'
  return '◇'
}

function formatPackItem(item) {
  const qty = item.quantity || 1
  return `${item.zh || item.name}${qty > 1 ? ` ×${qty}` : ''}`
}

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

  const equipmentOptions = options.starting_equipment?.[classEnKey] || []

  return (
    <div className="step-pane">
      <div className="step-title">✧ 第四章 · 起始装备 ✧</div>
      <div className="step-sub">这是你踏上旅程时所携之物。</div>

      <div className="equip-list">
        {equipmentOptions.map((opt, idx) => {
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
                  const packItems = options.starting_gear_packs?.[item.name] || []
                  return (
                    <React.Fragment key={`${item.slot || 'gear'}-${item.name}-${j}`}>
                      <span className="item-chip">
                        {getSlotGlyph(item.slot)} {getItemZh(item.name)}
                      </span>
                      {packItems.length > 0 && (
                        <div className="equip-pack-preview" aria-label={`${getItemZh(item.name)}内容`}>
                          {packItems.map(packItem => (
                            <span key={`${item.name}-${packItem.name}`} className="pack-chip">
                              {formatPackItem(packItem)}
                            </span>
                          ))}
                        </div>
                      )}
                    </React.Fragment>
                  )
                })}
              </div>
            </div>
          )
        })}
        {equipmentOptions.length === 0 && (
          <div className="create-note">
            <span className="lead">提示</span>
            选择职业后会显示可用的起始装备方案。
          </div>
        )}
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
