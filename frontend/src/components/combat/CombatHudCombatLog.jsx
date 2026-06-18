import React from 'react'
import CombatLogEntry from './CombatLogEntry'
import { buildCombatLogView } from '../../utils/combatLog'

export default function CombatHudCombatLog({ logs, logsEndRef }) {
  const visibleLogs = logs.slice(-8)
  const summary = buildCombatLogSummary(visibleLogs)

  return (
    <section className="combat-log-panel" aria-label="战斗日志">
      {summary && (
        <div className={`combat-log-summary ${summary.tone}`} role="status" aria-live="polite" aria-label="最近战报摘要">
          <span className="combat-log-summary-kicker">最近</span>
          <b>来源 {summary.roleLabel}</b>
          {summary.feedback.map(item => (
            <span key={item.kind} className={`combat-log-summary-feedback ${item.kind}`}>{item.label}</span>
          ))}
          {summary.impacts.length > 0 && (
            <span className="combat-log-summary-impacts" role="list" aria-label="影响摘要">
              {summary.impacts.map(item => (
                <i
                  key={item.key}
                  className={item.tone || ''}
                  title={item.title || item.label}
                  role="listitem"
                  aria-label={`${item.label}${item.title ? `：${item.title}` : ''}`}
                >
                  {item.label}
                </i>
              ))}
            </span>
          )}
          {summary.headline && <em title={summary.headline}>战报 {summary.headline}</em>}
          {summary.sections.length > 0 && (
            <span className="combat-log-summary-sections" role="list" aria-label="战报结构">
              {summary.sections.map(section => (
                <i key={section.kind} role="listitem">{section.label} {section.count}</i>
              ))}
            </span>
          )}
          <span className="combat-log-summary-count">{visibleLogs.length}/{logs.length}</span>
        </div>
      )}

      <div className="combat-log" role="log" aria-label="最近战斗日志" aria-live="polite">
        {visibleLogs.map((log, i) => (
          <CombatLogEntry key={log.id || i} log={log} />
        ))}
        <div ref={logsEndRef} className="combat-log-end" aria-hidden="true" />
      </div>
    </section>
  )
}

function buildCombatLogSummary(visibleLogs = []) {
  const latest = [...visibleLogs].reverse().find(isMeaningfulCombatLog) || visibleLogs[visibleLogs.length - 1]
  if (!latest) return null

  const view = buildCombatLogView(latest)
  const narration = view.sections.find(section => section.kind === 'narration')?.items?.[0] || ''
  const headline = narration || view.sections.find(section => section.items?.length > 0)?.items?.[0] || ''

  return {
    tone: view.tone,
    roleLabel: view.roleLabel,
    feedback: view.feedback.slice(0, 3),
    impacts: view.impact.slice(0, 5),
    headline,
    sections: view.sections.map(section => ({
      kind: section.kind,
      label: section.label,
      count: section.items?.length || 0,
    })),
  }
}

function isMeaningfulCombatLog(log = {}) {
  if (log.log_type === 'combat' || log.log_type === 'dice') return true
  if (log.dice_result) return true
  if (Array.isArray(log.state_changes) && log.state_changes.length > 0) return true
  return false
}
