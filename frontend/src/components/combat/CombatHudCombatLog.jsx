import React from 'react'

function logLabel(log) {
  if (log.log_type === 'combat_mechanics') return '机制'
  if (log.log_type === 'combat') return log.role === 'dm' ? '叙事' : '战斗'
  if (log.log_type === 'system') return '系统'
  return log.dice_result ? '骰点' : '日志'
}

function logClass(log) {
  const attack = log.dice_result?.attack || log.dice_result
  if (attack?.is_crit) return 'crit'
  if (attack?.is_fumble) return 'miss'
  if (log.log_type === 'combat_mechanics') return 'mechanics'
  if (log.log_type === 'combat') return 'dmg'
  return 'normal'
}

function rollLabel(log) {
  const dice = log.dice_result
  if (!dice) return logLabel(log)

  const attack = dice.attack || dice
  if (attack?.d20 !== undefined) return `d20=${attack.d20}`
  if (dice.total !== undefined) return `骰点=${dice.total}`
  if (dice.damage !== undefined) {
    const damage = typeof dice.damage === 'object' ? dice.damage.total : dice.damage
    return damage !== undefined ? `伤害=${damage}` : '骰点'
  }
  return '骰点'
}

export default function CombatHudCombatLog({ logs, logsEndRef }) {
  return (
    <div className="combat-log" style={{ marginTop: 4 }}>
      {logs.slice(-8).map((log, i) => (
        <div key={log.id || i} className={`log-entry ${logClass(log)}`}>
          <span className="roll">
            {rollLabel(log)}
          </span>
          <span>{(log.content || '').slice(0, 80)}</span>
        </div>
      ))}
      <div ref={logsEndRef} />
    </div>
  )
}
