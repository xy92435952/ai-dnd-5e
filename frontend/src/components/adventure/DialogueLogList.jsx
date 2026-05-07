import LogLine from './LogLine'

export default function DialogueLogList({ logs, logsEndRef }) {
  return (
    <div style={{
      padding: '10px 28px 0',
      maxWidth: 900,
      margin: '0 auto',
      minHeight: 0,
    }}>
      {logs.map(l => <LogLine key={l.id} entry={l} />)}
      <div ref={logsEndRef} />
    </div>
  )
}
