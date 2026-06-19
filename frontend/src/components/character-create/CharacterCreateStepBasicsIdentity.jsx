import React from 'react'
import { RACE_INFO, CLASS_INFO, ABILITY_ZH, CLASS_ZH_TO_EN } from '../../data/dnd5e.js'
import { formatHitDieLabel } from '../../utils/characterCreate'
import Portrait from '../Portrait'
import { classKey } from '../Crests'

export default function CharacterCreateStepBasicsIdentity({ ctx }) {
  const {
    form,
    setForm,
    options,
    classEnKey,
    classInfo,
    raceEnKey,
    saveProfs,
    openModal,
  } = ctx

  return (
    <>
      <div className="create-field">
        <label className="lbl">英雄之名</label>
        <input
          className="input-fantasy"
          placeholder="输入你的名字…"
          value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
        />
      </div>

      <div className="create-field">
        <label className="lbl">血脉 · 种族</label>
        <div className="race-grid">
          {options.races.map(r => {
            const sel = form.race === r
            const enKey = Object.keys(RACE_INFO).find(k => RACE_INFO[k].zh === r) || r
            const info = RACE_INFO[enKey]
            const bonus = options.racial_ability_bonuses?.[r] || options.racial_ability_bonuses?.[enKey] || {}
            return (
              <div
                key={r}
                className={`race-card ${sel ? 'sel' : ''}`}
                onClick={() => setForm(f => ({ ...f, race: r }))}
              >
                <div className="race-name">{r}</div>
                <div className="race-meta">{info?.size || '—'} · 速度 {info?.speed || 30}</div>
                {Object.keys(bonus).length > 0 && (
                  <div className="race-bonus">
                    {Object.entries(bonus).map(([k, v]) => (
                      <span key={k}>{ABILITY_ZH[k] || k} +{v}</span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
        {form.race && RACE_INFO[raceEnKey]?.description && (
          <div className="hint">
            <em>"{RACE_INFO[raceEnKey].description.slice(0, 80)}…"</em>
            {raceEnKey && (
              <button
                type="button"
                className="create-basics-detail-button"
                aria-label={`${form.race} race details`}
                onClick={() => openModal('race', raceEnKey)}
              >
                【详情】
              </button>
            )}
          </div>
        )}
      </div>

      <div className="create-field">
        <label className="lbl">使命 · 职业</label>
        <div className="class-grid">
          {options.classes.map(c => {
            const sel = form.char_class === c
            const enKey = CLASS_ZH_TO_EN[c] || c
            const info = CLASS_INFO[enKey]
            return (
              <div
                key={c}
                className={`class-card ${sel ? 'sel' : ''}`}
                onClick={() => setForm(f => ({ ...f, char_class: c, subclass: '' }))}
              >
                <Portrait cls={classKey(c)} size="sm" className="create-basics-class-portrait" />
                <div className="class-name">{c}</div>
                <div className="class-prim">{formatHitDieLabel(info?.hit_die)}</div>
              </div>
            )
          })}
        </div>
        {classInfo && (
          <div className="class-details">
            <div className="row">
              <span className="tag tag-gold">生命骰 {formatHitDieLabel(classInfo.hit_die)}</span>
              <span className="tag">主属性 {classInfo.primary_ability}</span>
              {saveProfs.length > 0 && (
                <span className="tag">豁免 {saveProfs.map(k => ABILITY_ZH[k] || k).join('/')}</span>
              )}
            </div>
            {classInfo.description && (
              <p className="desc"><em>"{classInfo.description.slice(0, 120)}"</em></p>
            )}
            <div className="row-muted">
              {classInfo.armor_proficiency && `护甲：${classInfo.armor_proficiency}`}
              {classEnKey && (
                <button
                  type="button"
                  className="create-basics-detail-button create-basics-class-detail-button"
                  aria-label={`${form.char_class} class details`}
                  onClick={() => openModal('class', classEnKey)}
                >
                  【完整特性】
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
