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

  return (
    <div style={{
      position: 'relative',
      padding: '14px 18px 14px 22px',
      border: `1px solid ${p.border}`,
      borderLeft: `4px solid ${p.accent}`,
      background: p.bg,
      borderRadius: 6,
      boxShadow: 'inset 0 1px 0 rgba(255,255,255,.05), 0 4px 20px -6px rgba(0,0,0,.8)',
      minHeight: 64,
    }}>
      {!isDm && (
        <div style={{
          position: 'absolute', top: -11, left: 14,
          padding: '2px 10px',
          background: p.accent, color: '#0a0604',
          fontFamily: 'var(--font-display)', fontSize: 11,
          letterSpacing: '.15em', fontWeight: 700,
          borderRadius: 2,
          boxShadow: '0 2px 6px rgba(0,0,0,.6)',
        }}>
          ❖ {seg.speaker || 'NPC'}
        </div>
      )}
      <p style={{
        fontFamily: isDm ? 'var(--font-script)' : 'var(--font-body)',
        fontStyle: isDm ? 'italic' : 'normal',
        color: p.textColor,
        fontSize: isDm ? 15 : 14,
        lineHeight: 1.85,
        margin: 0,
        letterSpacing: '.03em',
        whiteSpace: 'pre-wrap',
      }}>
        {renderLightMarkdown(typingText, p.accent)}
        {!typingDone && (
          <span style={{
            display: 'inline-block',
            width: 6, height: 14,
            background: p.accent,
            marginLeft: 2,
            verticalAlign: 'text-bottom',
            animation: 'breathe 0.8s ease-in-out infinite',
          }} />
        )}
      </p>
    </div>
  )
}
