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

const STAGE_BUBBLE_ROLES = new Set(['dm', 'npc', 'companion'])
const ROLE_ACCENTS = {
  dm: 'var(--amber)',
  npc: 'var(--amethyst-light)',
  companion: 'var(--arcane-light)',
}

export default function StageBubble({ seg, typingText, typingDone }) {
  const role = STAGE_BUBBLE_ROLES.has(seg.role) ? seg.role : 'dm'
  const isDm = role === 'dm'
  const speaker = seg.speaker || (isDm ? 'DM' : 'NPC')
  const typingState = typingDone ? 'complete' : 'typing'

  return (
    <div
      className={`stage-bubble ${role} is-${typingState}`}
      role="article"
      aria-label={`剧场对白：${speaker}`}
      aria-busy={!typingDone}
      data-typing-state={typingState}
    >
      {!isDm && (
        <div className="stage-bubble-speaker">
          ❖ {speaker}
        </div>
      )}
      <p
        className="stage-bubble-text"
      >
        {renderLightMarkdown(typingText, ROLE_ACCENTS[role])}
        {!typingDone && (
          <span className="stage-bubble-cursor" aria-hidden="true" />
        )}
      </p>
    </div>
  )
}
