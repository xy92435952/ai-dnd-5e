import React from 'react'

function readNumber(value, fallback) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

export default function CombatHudPips({ turnState }) {
  const movementMax = readNumber(turnState?.movement_max, 6)
  const movementUsed = readNumber(turnState?.movement_used, 0)
  const movementRemaining = Math.max(0, movementMax - movementUsed)
  const pips = [
    {
      key: 'action',
      className: 'action',
      icon: 'A',
      label: '动作',
      used: Boolean(turnState?.action_used),
    },
    {
      key: 'bonus',
      className: 'bonus',
      icon: 'B',
      label: '附赠',
      used: Boolean(turnState?.bonus_action_used),
    },
    {
      key: 'reaction',
      className: 'react',
      icon: 'R',
      label: '反应',
      used: Boolean(turnState?.reaction_used),
    },
  ]

  return (
    <section
      className="action-pips"
      role="region"
      aria-label="行动经济"
      aria-live="polite"
    >
      <div
        className="action-pip-list"
        role="list"
        aria-label={`行动经济：动作${pips[0].used ? '已用' : '可用'}，附赠${pips[1].used ? '已用' : '可用'}，反应${pips[2].used ? '已用' : '可用'}，移动${movementRemaining}/${movementMax}`}
      >
        {pips.map((pip) => (
          <div
            key={pip.key}
            className={`action-pip ${pip.className} ${pip.used ? 'used' : ''}`}
            role="listitem"
            title={`${pip.label}${pip.used ? '已用' : '可用'}`}
            aria-label={`${pip.label}${pip.used ? '已用' : '可用'}`}
          >
            <span className={`pip ${pip.className} ${pip.used ? 'used' : ''}`} aria-hidden="true">
              <span>{pip.icon}</span>
            </span>
            <span className="pip-label">{pip.label}</span>
            <span className="pip-state">{pip.used ? '已用' : '可用'}</span>
          </div>
        ))}
        <div
          className={`action-pip movement ${movementRemaining <= 0 ? 'used' : ''}`}
          role="listitem"
          title={`移动剩余 ${movementRemaining}/${movementMax}`}
          aria-label={`移动剩余 ${movementRemaining}/${movementMax}`}
        >
          <span className={`pip move ${movementRemaining <= 0 ? 'used' : ''}`} aria-hidden="true">
            <span>M</span>
          </span>
          <span className="pip-label">移动</span>
          <span className="pip-state">{movementRemaining}/{movementMax}</span>
        </div>
      </div>
    </section>
  )
}
