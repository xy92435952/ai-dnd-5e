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

      <div className="create-multiclass">
        <div
          className="create-multiclass-toggle"
          data-enabled={form.multiclassEnabled ? 'true' : 'false'}
          onClick={() => setForm(f => ({ ...f, multiclassEnabled: !f.multiclassEnabled }))}
        >
          <div className="create-multiclass-checkbox">
            {form.multiclassEnabled && '\u2713'}
          </div>
          <span className="create-multiclass-label">
            启用双职业
          </span>
          <span className="create-multiclass-optional">（可选）</span>
        </div>

        {form.multiclassEnabled && (
          <div className="create-multiclass-panel">
            <div className="create-multiclass-fields">
              <Field label="第二职业">
                <div className="create-multiclass-class-row">
                  <select
                    className="input-fantasy create-multiclass-select"
                    data-selected={form.multiclass_class ? 'true' : 'false'}
                    value={form.multiclass_class}
                    onChange={e => setForm(f => ({ ...f, multiclass_class: e.target.value }))}
                  >
                    <option value="">选择职业</option>
                    {options.classes.filter(c => c !== form.char_class).map(c => (
                      <option key={c} value={c}>
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
                  className="input-fantasy create-multiclass-level-input"
                />
              </Field>
            </div>
            {form.multiclass_class && Object.keys(multiReqs).length > 0 && (
              <div
                className="create-multiclass-requirements"
                data-met={multiReqMet ? 'true' : 'false'}
              >
                <span className="create-multiclass-requirements-title">
                  {multiReqMet ? '\u2713 已满足' : '\u2717 未满足'} 入门要求：
                </span>
                {Object.entries(multiReqs).map(([ab, min]) => {
                  const met = (finalScores[ab] || 0) >= min
                  return (
                    <span
                      key={ab}
                      className="create-multiclass-requirement"
                      data-met={met ? 'true' : 'false'}
                    >
                      {ABILITY_ZH[ab] || ab}&gt;={min}（当前{finalScores[ab] || 8}）
                    </span>
                  )
                })}
              </div>
            )}
            {!form.multiclass_class && (
              <p className="create-multiclass-empty">
                选择第二职业后将显示入门属性要求
              </p>
            )}
          </div>
        )}
      </div>
    </>
  )
}
