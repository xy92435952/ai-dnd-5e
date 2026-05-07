import React from 'react'

export default function CombatHudCombatLog({ logs, logsEndRef }) {
  return (
    <div className="combat-log" style={{ marginTop: 4 }}>
      {logs.slice(-8).map((log, i) => (
        <div key={log.id || i} className={`log-entry ${
          log.dice_result?.is_crit ? 'crit' :
          log.dice_result?.is_fumble ? 'miss' :
          log.log_type === 'combat' ? 'dmg' : 'normal'
        }`}>
          <span className="roll">
            {log.dice_result ? `d20=${log.dice_result.d20 || log.dice_result.total}` : '日志'}
          </span>
          <span>{(log.content || '').slice(0, 80)}</span>
        </div>
      ))}
      <div ref={logsEndRef} />
    </div>
  )
}
