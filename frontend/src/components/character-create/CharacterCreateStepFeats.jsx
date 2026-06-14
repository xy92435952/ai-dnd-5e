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
    <div className="step-pane">
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
            style={{
              padding: '12px 16px',
              borderRadius: '8px',
              border: '1px solid var(--wood-light)',
              background: 'rgba(10,8,6,0.3)',
            }}
          >
            <p style={{ fontSize: '0.8rem', color: 'var(--text-bright)', marginBottom: '8px', fontWeight: 600 }}>
              第 {i + 1} 次选择（Lv {asiLevels[i]}）
            </p>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
              <button
                className={isASI ? 'btn-gold' : 'btn-fantasy'}
                style={{ flex: 1, padding: '6px 12px', fontSize: '0.75rem' }}
                onClick={() => {
                  const next = [...chosenFeats]
                  next[i] = { name: '__ASI__', desc: '两项属性各+1' }
                  setChosenFeats(next)
                }}
              >
                +2 属性提升
              </button>
              <button
                className={(feat && !isASI) ? 'btn-gold' : 'btn-fantasy'}
                style={{ flex: 1, padding: '6px 12px', fontSize: '0.75rem' }}
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
              <div>
                <select
                  value={feat.name}
                  className="input-fantasy"
                  style={{ marginBottom: '4px' }}
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
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.65rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                    Ability
                    <select
                      className="input-fantasy"
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
                  <p style={{ fontSize: '0.65rem', color: 'var(--gold-dim)', marginTop: '4px' }}>
                    Prerequisite: {featInfo.prereq}
                  </p>
                )}
                {selectionFailure && (
                  <p style={{ fontSize: '0.65rem', color: 'var(--red-light)', marginTop: '4px' }}>
                    {selectionFailure}
                  </p>
                )}
                <p style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '4px' }}>
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
