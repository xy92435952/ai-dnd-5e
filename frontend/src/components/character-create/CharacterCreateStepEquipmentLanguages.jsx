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
    <section className="equipment-language-section" aria-label="Bonus language choices">
      <p className="equipment-language-title" data-complete={bonusLanguages.length === totalBonus ? 'true' : 'false'}>
        额外语言选择（{bonusLanguages.length}/{totalBonus}）
      </p>
      <p className="equipment-language-fixed">
        种族固定语言：{fixed.join('、')}
      </p>
      <div className="equipment-language-options" role="list" aria-label="Available bonus languages">
        {available.map(lang => {
          const sel = bonusLanguages.includes(lang)
          return (
            <div key={lang} className="equipment-language-option" role="listitem">
              <button
                type="button"
                className={`skill-btn equipment-language-button${sel ? ' selected' : ''}`}
                data-selected={sel ? 'true' : 'false'}
                onClick={() => setBonusLanguages(prev =>
                  prev.includes(lang) ? prev.filter(l => l !== lang)
                    : prev.length >= totalBonus ? prev : [...prev, lang]
                )}
              >
                {sel && '\u2713 '}{lang}
              </button>
            </div>
          )
        })}
      </div>
    </section>
  )
}
