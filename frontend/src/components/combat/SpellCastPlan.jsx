import React from 'react'

export default function SpellCastPlan({ plan, onResetAoeCenter = null }) {
  if (!plan) return null

  return (
    <section className={`spell-cast-plan ${plan.tone}`} aria-label="施法计划">
      <div className="spell-cast-plan-head">
        <span>施法计划</span>
        <b>{plan.status}</b>
      </div>
      {plan.preflight?.length > 0 && (
        <div className="spell-preflight-strip" aria-label="施法预检">
          {plan.preflight.map(item => (
            <span key={item.key} className={item.tone || ''} title={item.title || item.value}>
              <b>{item.label}</b>
              <em>{item.value}</em>
            </span>
          ))}
        </div>
      )}
      <div className="spell-cast-plan-grid">
        {plan.rows.map(row => (
          <div key={`${row.label}-${row.value}`} className={`spell-cast-plan-row ${row.tone || ''}`}>
            <span>{row.label}</span>
            <b>{row.value}</b>
          </div>
        ))}
      </div>
      {plan.aoeBreakdown?.chips?.length > 0 && (
        <div className="spell-aoe-breakdown" aria-label="范围目标统计">
          {plan.aoeBreakdown.chips.map(chip => (
            <span key={chip.key} className={chip.tone || ''} title={chip.title}>{chip.label}</span>
          ))}
        </div>
      )}
      {plan.targetImpactChips?.length > 0 && (
        <div className="spell-target-impacts" aria-label="目标状态影响">
          {plan.targetImpactChips.map(chip => (
            <span key={chip.key} className={chip.tone || ''} title={chip.title}>{chip.label}</span>
          ))}
        </div>
      )}
      {plan.warnings?.length > 0 && (
        <div className="spell-tactical-warnings" aria-label="范围战术提醒">
          {plan.warnings.map(warning => (
            <div key={warning.key} className={warning.tone || ''}>
              <b>{warning.label}</b>
              <span>{warning.detail}</span>
            </div>
          ))}
        </div>
      )}
      {plan.aoePlacement?.canReset && onResetAoeCenter && (
        <div className="spell-placement-actions" aria-label="范围落点操作">
          <button type="button" onClick={onResetAoeCenter} title="清除当前范围落点，重新在战场选择">
            重新选择落点
          </button>
        </div>
      )}
    </section>
  )
}
