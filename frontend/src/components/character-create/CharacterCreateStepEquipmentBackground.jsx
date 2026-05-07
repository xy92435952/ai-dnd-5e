import React from 'react'

export default function CharacterCreateStepEquipmentBackground({ form, options }) {
  if (!form.background || !options.background_features?.[form.background]) return null

  return (
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
  )
}
