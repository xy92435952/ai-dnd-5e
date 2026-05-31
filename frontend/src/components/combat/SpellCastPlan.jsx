import React from 'react'

export default function SpellCastPlan({ plan }) {
  if (!plan) return null

  return (
    <section className={`spell-cast-plan ${plan.tone}`} aria-label="施法计划">
      <div className="spell-cast-plan-head">
        <span>施法计划</span>
        <b>{plan.status}</b>
      </div>
      <div className="spell-cast-plan-grid">
        {plan.rows.map(row => (
          <div key={`${row.label}-${row.value}`} className={`spell-cast-plan-row ${row.tone || ''}`}>
            <span>{row.label}</span>
            <b>{row.value}</b>
          </div>
        ))}
      </div>
    </section>
  )
}
