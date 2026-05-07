import React from 'react'
import { ABILITY_ZH, CLASS_INFO } from '../../data/dnd5e.js'
import { CharacterCreateField as Field, CharacterCreateInfoBtn as InfoBtn } from './CharacterCreateShared'

export default function CharacterCreateStepBasicsFeatures({ ctx }) {
  const {
    form,
    setForm,
    classEnKey,
    classInfo,
    showSubclass,
    subclassOptions,
    hasFightingStyle,
    multiReqs,
    multiReqMet,
    finalScores,
    multiclassEnKey,
    options,
    openModal,
    fightingStyle,
    setFightingStyle,
  } = ctx

  return (
    <>
      {showSubclass && subclassOptions.length > 0 && (
        <div className="create-field">
          <label className="lbl">
            {classInfo.subclass_label}（Lv{classInfo.subclass_unlock} 解锁）
          </label>
          <div className="sub-grid">
            {subclassOptions.map(sc => {
              const sel = form.subclass === sc.name
              return (
                <div
                  key={sc.name}
                  className={`sub-chip ${sel ? 'sel' : ''}`}
                  onClick={() => setForm(f => ({ ...f, subclass: sel ? '' : sc.name }))}
                >
                  {sc.zh}
                </div>
              )
            })}
          </div>
          {!form.subclass && <div className="hint">可跳过，稍后决定</div>}
        </div>
      )}

      {hasFightingStyle && (
        <div className="create-field">
          <label className="lbl">战斗风格</label>
          <div className="fstyle-grid">
            {(options.fighting_style_classes?.[classEnKey]?.styles || []).map(style => {
              const sel = fightingStyle === style
              const info = options.fighting_styles?.[style] || {}
              return (
                <div
                  key={style}
                  className={`fstyle-card ${sel ? 'sel' : ''}`}
                  onClick={() => setFightingStyle(sel ? '' : style)}
                >
                  <div className="n">{info.zh || style}</div>
                  <div className="d">{info.desc}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', userSelect: 'none' }}
          onClick={() => setForm(f => ({ ...f, multiclassEnabled: !f.multiclassEnabled }))}
        >
          <div
            style={{
              width: '16px',
              height: '16px',
              borderRadius: '3px',
              border: `1px solid ${form.multiclassEnabled ? 'var(--gold)' : 'var(--wood-light)'}`,
              background: form.multiclassEnabled ? 'rgba(201,168,76,0.2)' : 'transparent',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.75rem',
              color: 'var(--gold)',
            }}
          >
            {form.multiclassEnabled && '\u2713'}
          </div>
          <span style={{ fontSize: '0.875rem', color: form.multiclassEnabled ? 'var(--gold)' : 'var(--text-dim)' }}>
            启用双职业
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', opacity: 0.5 }}>（可选）</span>
        </div>

        {form.multiclassEnabled && (
          <div
            style={{
              marginTop: '12px',
              padding: '12px',
              borderRadius: '6px',
              border: '1px solid var(--wood-light)',
              background: 'rgba(201,168,76,0.04)',
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <Field label="第二职业">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <select
                    className="input-fantasy"
                    style={{ color: form.multiclass_class ? 'var(--parchment)' : 'var(--text-dim)', background: 'var(--bg2)' }}
                    value={form.multiclass_class}
                    onChange={e => setForm(f => ({ ...f, multiclass_class: e.target.value }))}
                  >
                    <option value="">选择职业</option>
                    {options.classes.filter(c => c !== form.char_class).map(c => (
                      <option key={c} value={c} style={{ background: 'var(--bg2)' }}>
                        {c}
                      </option>
                    ))}
                  </select>
                  {multiclassEnKey && CLASS_INFO[multiclassEnKey] && (
                    <InfoBtn onClick={() => openModal('class', multiclassEnKey)} />
                  )}
                </div>
              </Field>
              <Field label="副职等级">
                <input
                  type="number"
                  min={1}
                  max={Math.max(1, 20 - form.level)}
                  value={form.multiclass_level}
                  onChange={e => setForm(f => ({ ...f, multiclass_level: +e.target.value || 1 }))}
                  className="input-fantasy"
                  style={{ textAlign: 'center' }}
                />
              </Field>
            </div>
            {form.multiclass_class && Object.keys(multiReqs).length > 0 && (
              <div
                style={{
                  fontSize: '0.75rem',
                  padding: '8px',
                  borderRadius: '6px',
                  background: multiReqMet ? 'rgba(42,90,42,0.12)' : 'rgba(139,32,32,0.12)',
                  border: `1px solid ${multiReqMet ? 'var(--green)' : 'var(--red)'}`,
                }}
              >
                <span style={{ color: multiReqMet ? 'var(--green-light)' : 'var(--red-light)' }}>
                  {multiReqMet ? '\u2713 已满足' : '\u2717 未满足'} 入门要求：
                </span>
                {Object.entries(multiReqs).map(([ab, min]) => {
                  const met = (finalScores[ab] || 0) >= min
                  return (
                    <span key={ab} style={{ marginLeft: '8px', color: met ? 'var(--green-light)' : 'var(--red-light)' }}>
                      {ABILITY_ZH[ab] || ab}&gt;={min}（当前{finalScores[ab] || 8}）
                    </span>
                  )
                })}
              </div>
            )}
            {!form.multiclass_class && (
              <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', opacity: 0.5 }}>
                选择第二职业后将显示入门属性要求
              </p>
            )}
          </div>
        )}
      </div>
    </>
  )
}
