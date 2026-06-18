/**
 * LogLine — chat 模式下日志列表里的单条气泡。
 *
 * 按 entry.role 选样式：dm（金色羊皮纸）/ player（蓝）/ companion（绿）/ dice（金色 mono）/ system（灰小字）
 *
 * 从 Adventure.jsx 抽出，extractNarrative 用于兼容历史 JSON 格式 log。
 */
import { extractNarrative } from '../../utils/dialogue'
import { renderLightMarkdown } from '../../utils/markdown'

function visibilityLabel(visibility) {
  const scope = visibility?.scope
  if (scope === 'private') return '私密'
  if (scope === 'group') return '分队'
  return ''
}

function VisibilityBadge({ visibility }) {
  const label = visibilityLabel(visibility)
  if (!label) return null
  return (
    <span className={`dialogue-log-visibility ${visibility?.scope || 'party'}`}>
      {label}
    </span>
  )
}

function LogShell({ role, entryRole, children }) {
  return (
    <div className={`dialogue-log-item ${role}`} role="listitem" aria-label={`日志 ${entryRole}`}>
      {children}
    </div>
  )
}

export default function LogLine({ entry }) {
  const role = entry.role
  const txt = extractNarrative(entry.content)

  if (role === 'dm') {
    return (
      <LogShell role="dm" entryRole="DM">
        <p className="dialogue-log-line dialogue-log-line-dm">
          <VisibilityBadge visibility={entry.visibility} />
          {renderLightMarkdown(txt, 'var(--amber)')}
        </p>
      </LogShell>
    )
  }
  if (role === 'player') {
    return (
      <LogShell role="player" entryRole="玩家">
        <p className="dialogue-log-line dialogue-log-line-player">► {renderLightMarkdown(txt, '#fff8dd')}</p>
      </LogShell>
    )
  }
  if (role === 'companion') {
    const speaker = entry.speaker || entry.companion_speaker || '队友'
    return (
      <LogShell role="companion" entryRole={`队友 ${speaker}`}>
        <p className="dialogue-log-line dialogue-log-line-companion">❖ {speaker}：{renderLightMarkdown(txt, '#a8f0c0')}</p>
      </LogShell>
    )
  }
  if (role === 'dice') {
    return (
      <LogShell role="dice" entryRole="骰子">
        <p className="dialogue-log-line dialogue-log-line-dice">🎲 {txt}</p>
      </LogShell>
    )
  }
  // system / other
  return (
    <LogShell role="system" entryRole="系统">
      <p className="dialogue-log-line dialogue-log-line-system">
        {txt}
      </p>
    </LogShell>
  )
}
