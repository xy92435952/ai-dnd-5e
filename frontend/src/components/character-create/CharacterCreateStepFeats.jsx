import React from 'react'
import {
  FEAT_ABILITY_OPTIONS,
  buildDefaultMagicInitiateChoice,
  featRequiresAbilityChoice,
  featRequiresMagicInitiateChoices,
  getFeatPrerequisiteFailure,
  getFeatSelectionFailure,
  normalizeFeatAbility,
} from '../../utils/characterCreate'
import MagicInitiateChoiceFields from '../feats/MagicInitiateChoiceFields'

function buildFeatSelection(name, magicInitiateSpellOptions = {}) {
  return {
    name,
    ...(featRequiresAbilityChoice({ name }) ? { ability: FEAT_ABILITY_OPTIONS[0].value } : {}),
    ...(featRequiresMagicInitiateChoices({ name }) ? buildDefaultMagicInitiateChoice(magicInitiateSpellOptions) : {}),
  }
}

export default function CharacterCreateStepFeats({ ctx }) {
  const {
    form,
    needsASI,
    asiCount,
    asiLevels,
    chosenFeats,
    setChosenFeats,
    options,
    finalScores,
    isSpellcaster,
    chosenCantrips,
    chosenSpells,
  } = ctx

  if (!needsASI) return null

  return (
    <div className="step-pane create-feat-step">
      <div className="step-title">✧ 第六章 · 淬炼与专长 ✧</div>
      <div className="step-sub">
        Lv{form.level} — {asiCount} 次属性提升 (ASI) 或专长选择
      </div>
      {Array.from({ length: asiCount }, (_, i) => {
        const feat = chosenFeats[i]
        const isASI = feat?.name === '__ASI__'
        const featInfo = feat && !isASI ? ((options.feats || {})[feat.name] || {}) : {}
        const requiresAbility = featRequiresAbilityChoice(feat)
        const requiresMagicInitiate = featRequiresMagicInitiateChoices(feat)
        const magicInitiateSpellOptions = options?.magic_initiate_spell_options || {}
        const selectionFailure = feat && !isASI
          ? getFeatSelectionFailure({
            ...feat,
            ...featInfo,
            name: feat.name,
          }, {
            abilityScores: finalScores,
            isSpellcaster,
            knownSpells: chosenSpells,
            cantrips: chosenCantrips,
            magicInitiateSpellOptions,
          })
          : ''
        return (
          <div
            key={i}
            className="create-feat-choice-card"
            role="group"
            aria-label={`ASI or feat choice ${i + 1}`}
          >
            <p className="create-feat-choice-title">
              第 {i + 1} 次选择（Lv {asiLevels[i]}）
            </p>
            <div className="create-feat-choice-toggle-row">
              <button
                type="button"
                className={`${isASI ? 'btn-gold' : 'btn-fantasy'} create-feat-choice-toggle`}
                data-selected={isASI ? 'true' : 'false'}
                onClick={() => {
                  const next = [...chosenFeats]
                  next[i] = { name: '__ASI__', desc: '两项属性各+1' }
                  setChosenFeats(next)
                }}
              >
                +2 属性提升
              </button>
              <button
                type="button"
                className={`${(feat && !isASI) ? 'btn-gold' : 'btn-fantasy'} create-feat-choice-toggle`}
                data-selected={(feat && !isASI) ? 'true' : 'false'}
                onClick={() => {
                  const usedNames = chosenFeats.filter(f => f && f.name !== '__ASI__').map(f => f.name)
                  const available = Object.entries(options.feats || {})
                    .filter(([name, info]) => !usedNames.includes(name) && !getFeatPrerequisiteFailure({
                      name,
                      ...(info || {}),
                    }, {
                      abilityScores: finalScores,
                      isSpellcaster,
                      knownSpells: chosenSpells,
                      cantrips: chosenCantrips,
                    }))
                    .map(([name]) => name)
                  if (available.length > 0) {
                    const next = [...chosenFeats]
                    next[i] = buildFeatSelection(available[0], magicInitiateSpellOptions)
                    setChosenFeats(next)
                  }
                }}
              >
                选择专长
              </button>
            </div>
            {feat && !isASI && (
              <div className="create-feat-choice-fields">
                <select
                  value={feat.name}
                  className="input-fantasy create-feat-select"
                  onChange={e => {
                    const next = [...chosenFeats]
                    next[i] = buildFeatSelection(e.target.value, magicInitiateSpellOptions)
                    setChosenFeats(next)
                  }}
                >
                  {Object.entries(options.feats || {}).map(([name, info]) => {
                    const usedElsewhere = chosenFeats.some((other, index) => index !== i && other?.name === name)
                    const unavailableReason = getFeatPrerequisiteFailure({
                      name,
                      ...(info || {}),
                    }, {
                      abilityScores: finalScores,
                      isSpellcaster,
                      knownSpells: chosenSpells,
                      cantrips: chosenCantrips,
                    })
                    return (
                      <option
                        key={name}
                        value={name}
                        disabled={usedElsewhere || Boolean(unavailableReason)}
                      >
                        {info.zh || name} -- {info.desc?.slice(0, 30)}
                        {unavailableReason ? ` (${unavailableReason})` : ''}
                      </option>
                    )
                  })}
                </select>
                {requiresAbility && (
                  <label className="create-feat-ability-label">
                    Ability
                    <select
                      className="input-fantasy create-feat-ability-select"
                      value={normalizeFeatAbility(feat.ability)}
                      onChange={e => {
                        const next = [...chosenFeats]
                        next[i] = { ...feat, ability: e.target.value }
                        setChosenFeats(next)
                      }}
                    >
                      {FEAT_ABILITY_OPTIONS.map(option => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                )}
                {requiresMagicInitiate && (
                  <MagicInitiateChoiceFields
                    value={feat}
                    options={magicInitiateSpellOptions}
                    onChange={(choice) => {
                      const next = [...chosenFeats]
                      next[i] = { ...feat, ...choice }
                      setChosenFeats(next)
                    }}
                    selectClassName="input-fantasy"
                  />
                )}
                {featInfo?.prereq && (
                  <p className="create-feat-note create-feat-note-prereq">
                    Prerequisite: {featInfo.prereq}
                  </p>
                )}
                {selectionFailure && (
                  <p className="create-feat-note create-feat-note-error">
                    {selectionFailure}
                  </p>
                )}
                <p className="create-feat-note create-feat-note-desc">
                  {featInfo?.desc}
                </p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
