import React from 'react'
import CombatLogEntry from './CombatLogEntry'

export default function CombatHudCombatLog({ logs, logsEndRef }) {
  return (
    <div className="combat-log">
      {logs.slice(-8).map((log, i) => (
        <CombatLogEntry key={log.id || i} log={log} />
      ))}
      <div ref={logsEndRef} />
    </div>
  )
}
