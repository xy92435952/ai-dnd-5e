/**
 * LogLine — chat 模式下日志列表里的单条气泡。
 *
 * 按 entry.role 选样式：dm（金色羊皮纸）/ player（蓝）/ companion（绿）/ dice（金色 mono）/ system（灰小字）
 *
 * 从 Adventure.jsx 抽出，extractNarrative 用于兼容历史 JSON 格式 log。
 */
import { extractNarrative } from '../../utils/dialogue'
import { renderLightMarkdown } from '../../utils/markdown'

export default function LogLine({ entry }) {
  const role = entry.role
  const txt = extractNarrative(entry.content)

  if (role === 'dm') {
    return (
      <p style={{
        fontFamily: 'var(--font-script)', fontStyle: 'italic',
        color: 'var(--parchment)', fontSize: 14, lineHeight: 1.7,
        margin: '8px 0', padding: '0 0 0 14px',
        borderLeft: '2px solid rgba(240,208,96,.45)',
      }}>{renderLightMarkdown(txt, 'var(--amber)')}</p>
    )
  }
  if (role === 'player') {
    return (
      <p style={{
        color: '#7fe8f8', fontSize: 13, fontFamily: 'var(--font-body)',
        margin: '6px 0', padding: '0 0 0 14px',
        borderLeft: '2px solid rgba(127,232,248,.5)',
      }}>► {renderLightMarkdown(txt, '#fff8dd')}</p>
    )
  }
  if (role === 'companion') {
    return (
      <p style={{
        color: 'var(--emerald-light)', fontSize: 12,
        margin: '4px 0', padding: '0 0 0 14px', fontStyle: 'italic',
        borderLeft: '2px solid rgba(90,168,120,.5)',
      }}>❖ {renderLightMarkdown(txt, '#a8f0c0')}</p>
    )
  }
  if (role === 'dice') {
    return (
      <p style={{
        color: 'var(--amber)', fontSize: 12, fontFamily: 'var(--font-mono)',
        margin: '3px 0', padding: '2px 10px',
        background: 'rgba(10,6,4,.45)', borderRadius: 3,
        display: 'inline-block',
      }}>🎲 {txt}</p>
    )
  }
  // system / other
  return (
    <p style={{
      color: 'var(--parchment-dark)', fontSize: 11,
      margin: '3px 0', fontStyle: 'italic', opacity: 0.7,
    }}>
      {txt}
    </p>
  )
}
