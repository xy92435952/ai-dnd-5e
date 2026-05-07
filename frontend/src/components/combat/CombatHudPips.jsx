import React from 'react'

export default function CombatHudPips({ turnState }) {
  return (
    <div className="action-pips">
      <div className={`pip action ${turnState?.action_used ? 'used' : ''}`}><span>⚔</span></div>
      <div className={`pip bonus ${turnState?.bonus_action_used ? 'used' : ''}`}><span>✦</span></div>
      <div className={`pip react ${turnState?.reaction_used ? 'used' : ''}`}><span>⚡</span></div>
    </div>
  )
}
