/**
 * StageBubble — 剧场模式正在播放的单条气泡（含打字机光标）。
 *
 * Props:
 *   seg.role       'dm' | 'npc' | 'companion'
 *   seg.speaker    NPC / 队友名字（DM 不显示头标）
 *   typingText     当前已显示的文本片段（来自 useDialogueFlow）
 *   typingDone     是否打完字（控制末尾光标动画）
 */
import { renderLightMarkdown } from '../../utils/markdown'

export default function StageBubble({ seg, typingText, typingDone }) {
  const role = seg.role || 'dm'
  const palette = {
    dm: {
      border: 'rgba(240,208,96,.45)',
      bg: 'linear-gradient(180deg, rgba(46,31,14,.65), rgba(26,18,8,.85))',
      accent: 'var(--amber)',
      textColor: 'var(--parchment)',
    },
    npc: {
      border: 'rgba(168,144,232,.55)',
      bg: 'linear-gradient(180deg, rgba(58,36,90,.45), rgba(26,16,44,.8))',
      accent: 'var(--amethyst-light)',
      textColor: '#d8c8ff',
    },
    companion: {
      border: 'rgba(127,200,248,.55)',
      bg: 'linear-gradient(180deg, rgba(20,40,62,.55), rgba(10,22,36,.85))',
      accent: 'var(--arcane-light)',
      textColor: '#d8eeff',
    },
  }
  const p = palette[role] || palette.dm
  const isDm = role === 'dm'
  const speaker = seg.speaker || (isDm ? 'DM' : 'NPC')

  return (
    <div
      className={`stage-bubble ${role}`}
      role="article"
      aria-label={`剧场对白：${speaker}`}
      style={{
        '--stage-bubble-border': p.border,
        '--stage-bubble-bg': p.bg,
        '--stage-bubble-accent': p.accent,
        '--stage-bubble-text': p.textColor,
      }}
    >
      {!isDm && (
        <div className="stage-bubble-speaker">
          ❖ {speaker}
        </div>
      )}
      <p
        className="stage-bubble-text"
      >
        {renderLightMarkdown(typingText, p.accent)}
        {!typingDone && (
          <span className="stage-bubble-cursor" aria-hidden="true" />
        )}
      </p>
    </div>
  )
}
