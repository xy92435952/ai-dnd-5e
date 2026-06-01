import React from 'react'

export default function CharacterCreateStepEquipmentBackground({ form, options }) {
  const backgroundFeature = options.background_features?.[form.background]
  const backgroundEquipment = options.background_equipment?.[form.background]

  if (!form.background || !backgroundFeature) return null

  return (
    <div className="bg-feat">
      <div className="bf-title">◈ 背景特性 · {backgroundFeature.feature} ◈</div>
      <div className="bf-desc">
        {backgroundFeature.feature_desc}
      </div>
      <div className="bf-tags">
        {(backgroundFeature.skills || []).map(s => (
          <span key={s} className="tag tag-gold">⚔ {s}</span>
        ))}
        {(backgroundFeature.tools || []).map(t => (
          <span key={t} className="tag">◈ {t}</span>
        ))}
        {backgroundFeature.languages > 0 && (
          <span className="tag">◈ 额外语言 × {backgroundFeature.languages}</span>
        )}
      </div>
      {backgroundEquipment && (
        <>
          <div className="bf-desc">背景起始物品</div>
          <div className="bf-tags" aria-label="背景起始物品">
            {backgroundEquipment.gold > 0 && (
              <span className="tag tag-gold">金币 +{backgroundEquipment.gold} gp</span>
            )}
            {(backgroundEquipment.items || []).map((item, index) => (
              <span key={`${item.name}-${index}`} className="tag">
                {item.zh || item.name}{item.quantity > 1 ? ` ×${item.quantity}` : ''}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
