import LogLine from './LogLine'

export default function DialogueLogList({ logs, logsEndRef }) {
  return (
    <div
      className="dialogue-log-list"
      role="log"
      aria-label="冒险对话日志"
      aria-live="polite"
    >
      <div className="dialogue-log-items" role="list" aria-label="对话记录">
        {logs.map(l => <LogLine key={l.id} entry={l} />)}
      </div>
      <div ref={logsEndRef} className="dialogue-log-end" aria-hidden="true" />
    </div>
  )
}
