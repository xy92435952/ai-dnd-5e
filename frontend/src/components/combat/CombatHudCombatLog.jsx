import React from 'react'

function logLabel(log) {
  if (log.log_type === 'combat_mechanics') return '机制'
  if (log.log_type === 'combat') return log.role === 'dm' ? '叙事' : '战斗'
  if (log.log_type === 'system') return '系统'
  return log.dice_result ? '骰点' : '日志'
}

function logClass(log) {
  if (log.dice_result?.is_crit) return 'crit'
  if (log.dice_result?.is_fumble) return 'miss'
  if (log.log_type === 'combat_mechanics') return 'mechanics'
  if (log.log_type === 'combat') return 'dmg'
  return 'normal'
}

export default function CombatHudCombatLog({ logs, logsEndRef }) {
  return (
    <div className="combat-log" style={{ marginTop: 4 }}>
      {logs.slice(-8).map((log, i) => (
        <div key={log.id || i} className={`log-entry ${logClass(log)}`}>
          <span className="roll">
            {log.dice_result ? `d20=${log.dice_result.d20 || log.dice_result.total}` : logLabel(log)}
          </span>
          <span>{(log.content || '').slice(0, 80)}</span>
        </div>
      ))}
      <div ref={logsEndRef} />
    </div>
  )
}
