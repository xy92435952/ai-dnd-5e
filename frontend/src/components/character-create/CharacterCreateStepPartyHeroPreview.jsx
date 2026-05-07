import React from 'react'
import Portrait from '../Portrait'
import { classKey } from '../Crests'
import { ABILITY_ZH } from '../../data/dnd5e.js'
import { ABILITY_KEYS, modifier, modStr } from '../../utils/characterCreate'

export default function CharacterCreateStepPartyHeroPreview({ form, finalScores, playerCharacter }) {
  const hero = playerCharacter
  const derived = hero?.derived || {}
  const mods = derived.ability_modifiers || {}
  const scores = hero?.ability_scores || finalScores
  const prof = derived.proficiency_bonus || (2 + Math.floor((form.level - 1) / 4))
  const hpMax = derived.hp_max || 1
  const ac = derived.ac || 10
  const dexMod = mods.dex != null ? mods.dex : modifier(scores.dex || 10)

  return (
    <div className="final-hero-card">
      <div className="fh-left">
        <Portrait cls={classKey(form.char_class)} size="xl" />
      </div>
      <div className="fh-right">
        <div className="fh-name">{form.name || '未命名英雄'}</div>
        <div className="fh-sub">
          {form.race || '—'} · {form.char_class || '—'}
          {form.subclass ? ` · ${form.subclass}` : ''} · Lv {form.level}
        </div>
        <div className="fh-align">
          {form.alignment || ''}
          {form.background ? ` · 背景：${form.background}` : ''}
        </div>

        <div className="fh-stats">
          {ABILITY_KEYS.map(k => {
            const score = scores[k] || finalScores[k] || 10
            const m = mods[k] != null ? mods[k] : modifier(score)
            return (
              <div key={k} className="fh-stat">
                <div className="n">{ABILITY_ZH[k]}</div>
                <div className="v">{score}</div>
                <div className="m">{modStr(m)}</div>
              </div>
            )
          })}
        </div>

        <div className="fh-derived">
          <span>HP {hpMax}</span>
          <span>AC {ac}</span>
          <span>熟练 +{prof}</span>
          <span>先攻 {modStr(dexMod)}</span>
        </div>
      </div>
    </div>
  )
}
