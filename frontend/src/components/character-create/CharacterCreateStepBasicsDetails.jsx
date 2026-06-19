import React from 'react'
import { BACKGROUND_INFO } from '../../data/dnd5e.js'
import { CharacterCreateField as Field, CharacterCreateSelect as Select, CharacterCreateInfoBtn as InfoBtn } from './CharacterCreateShared'

export default function CharacterCreateStepBasicsDetails({ ctx }) {
  const {
    form,
    setForm,
    module,
    options,
    narrative,
    setNarrative,
    openModal,
    bonusLanguages,
    setBonusLanguages,
  } = ctx
  const levelInRecommendedRange = form.level >= module.level_min && form.level <= module.level_max

  return (
    <>
      <div className="create-details-top-grid">
        <Field label="等级（1--20）">
          <div className="create-details-level">
            <div className="create-details-level-row">
              <input
                type="range"
                className="create-details-level-slider"
                min={1}
                max={20}
                value={form.level}
                onChange={e => {
                  const nextLevel = +e.target.value
                  setForm(f => ({ ...f, level: nextLevel }))
                }}
              />
              <span className="create-details-level-value">
                {form.level}
              </span>
            </div>
            <p
              className="create-details-level-range"
              data-in-range={levelInRecommendedRange ? 'true' : 'false'}
            >
              {levelInRecommendedRange
                ? `\u2713 推荐范围 ${module.level_min}--${module.level_max}`
                : `推荐 Lv${module.level_min}--${module.level_max}`}
            </p>
          </div>
        </Field>
        <Field label="阵营">
          <Select
            value={form.alignment}
            options={options.alignments}
            placeholder="选择阵营"
            onChange={v => setForm(f => ({ ...f, alignment: v }))}
          />
        </Field>
      </div>

      <Field label="背景（可选）">
        <div className="create-details-background-row">
          <Select
            value={form.background}
            options={options.backgrounds}
            placeholder="选择背景"
            onChange={v => setForm(f => ({ ...f, background: v }))}
          />
          {form.background && BACKGROUND_INFO[form.background] && (
            <InfoBtn onClick={() => openModal('background', form.background)} />
          )}
        </div>
      </Field>

      {form.background && options.background_features?.[form.background] && (
        <div className="bg-feat">
          <div className="bf-title">◈ 背景特性 · {options.background_features[form.background].feature} ◈</div>
          <div className="bf-desc">
            {options.background_features[form.background].feature_desc}
          </div>
          <div className="bf-tags">
            {(options.background_features[form.background].skills || []).map(s => (
              <span key={s} className="tag tag-gold">⚔ {s}</span>
            ))}
            {(options.background_features[form.background].tools || []).map(t => (
              <span key={t} className="tag">◈ {t}</span>
            ))}
            {options.background_features[form.background].languages > 0 && (
              <span className="tag">◈ 额外语言 × {options.background_features[form.background].languages}</span>
            )}
          </div>
        </div>
      )}

      {(() => {
        const raceLang = options.racial_languages?.[form.race] || { fixed: ['Common'], bonus: 0 }
        const bgLangBonus = options.background_features?.[form.background]?.languages || 0
        const totalBonus = raceLang.bonus + bgLangBonus
        if (totalBonus <= 0) return null
        const fixed = raceLang.fixed || []
        const available = (options.all_languages || []).filter(l => !fixed.includes(l) && !bonusLanguages.includes(l))
        return (
          <div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-bright)', marginBottom: '6px' }}>
              额外语言选择（{bonusLanguages.length}/{totalBonus}）
            </p>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginBottom: '8px' }}>
              种族固定语言：{fixed.join('、')}
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {available.map(lang => {
                const sel = bonusLanguages.includes(lang)
                return (
                  <button
                    key={lang}
                    className="skill-btn"
                    style={{
                      borderColor: sel ? 'var(--gold)' : 'var(--wood-light)',
                      background: sel ? 'rgba(201,168,76,0.2)' : undefined,
                      color: sel ? 'var(--gold)' : 'var(--text-dim)',
                    }}
                    onClick={() => setBonusLanguages(prev =>
                      prev.includes(lang) ? prev.filter(l => l !== lang)
                        : prev.length >= totalBonus ? prev : [...prev, lang]
                    )}
                  >
                    {sel && '\u2713 '}{lang}
                  </button>
                )
              })}
            </div>
          </div>
        )
      })()}

      <details
        style={{
          marginTop: 24,
          padding: '12px 16px',
          border: '1px solid var(--wood-light)',
          borderRadius: 6,
          background: 'rgba(46,31,14,0.4)',
        }}
      >
        <summary
          style={{
            cursor: 'pointer',
            color: 'var(--gold)',
            fontFamily: 'var(--font-display)',
            fontSize: '0.95rem',
            letterSpacing: '0.1em',
            userSelect: 'none',
          }}
        >
          ❖ 角色叙事 · 选填
          <span style={{ marginLeft: 12, fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-body)', letterSpacing: 0 }}>
            填了 DM 在你掉线时也能"按你的人设"代演，不会出戏
          </span>
        </summary>

        <div style={{ display: 'grid', gap: 12, marginTop: 14 }}>
          {[
            { key: 'personality', label: '性格', hint: '简短描述（如"沉默寡言，只在必要时开口"）', rows: 2 },
            { key: 'backstory', label: '背景故事', hint: 'DM 偶尔会引用，长短不限', rows: 4 },
            { key: 'speech_style', label: '说话风格', hint: '寡言 / 健谈 / 幽默 / 古板严肃 / ...', rows: 1 },
            { key: 'combat_preference', label: '战斗偏好', hint: '激进 / 远程优先 / 优先保护弱小 / ...', rows: 1 },
            { key: 'catchphrase', label: '口头禅', hint: '一句即可（如"天黑前必须到达。"）', rows: 1 },
          ].map(({ key, label, hint, rows }) => (
            <div key={key}>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.8rem',
                  color: 'var(--text)',
                  marginBottom: 4,
                }}
              >
                {label}
                <span style={{ color: 'var(--text-dim)', marginLeft: 8, opacity: 0.7 }}>— {hint}</span>
              </label>
              {rows > 1 ? (
                <textarea
                  rows={rows}
                  maxLength={key === 'backstory' ? 800 : 200}
                  value={narrative[key]}
                  onChange={e => setNarrative(n => ({ ...n, [key]: e.target.value }))}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontFamily: 'var(--font-body)',
                    fontSize: '0.85rem',
                    background: 'rgba(10,6,4,0.5)',
                    color: 'var(--parchment)',
                    border: '1px solid var(--wood-light)',
                    borderRadius: 4,
                    resize: 'vertical',
                  }}
                />
              ) : (
                <input
                  type="text"
                  maxLength={120}
                  value={narrative[key]}
                  onChange={e => setNarrative(n => ({ ...n, [key]: e.target.value }))}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    fontFamily: 'var(--font-body)',
                    fontSize: '0.85rem',
                    background: 'rgba(10,6,4,0.5)',
                    color: 'var(--parchment)',
                    border: '1px solid var(--wood-light)',
                    borderRadius: 4,
                  }}
                />
              )}
            </div>
          ))}
        </div>
      </details>
    </>
  )
}
