import React from 'react'

export default function CharacterCreateStepEquipmentLanguages({
  form,
  options,
  bonusLanguages,
  setBonusLanguages,
}) {
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
}
