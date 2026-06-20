/**
 * StageLeftFigure — Adventure 顶部左侧的"说话者剪影 + 名牌"。
 *
 * stage 模式：根据 currentSeg 显示当前正在说话的角色（DM / NPC / companion）
 * chat 模式（hasDmContent=true）：兜底显示 DM 旁白色金色剪影
 * chat 模式（hasDmContent=false）：返回 null（页面没有 DM 内容时藏起来）
 *
 * Props:
 *   dialogueMode   'chat' | 'stage'
 *   currentSeg     stage 模式下当前段 { role, speaker }
 *   companions     队友列表（用于 companion 段匹配头像）
 *   hasDmContent   chat 模式时控制是否显示
 */
export default function StageLeftFigure({ dialogueMode, currentSeg, companions, hasDmContent }) {
  // 决定当前左侧应展示的身份
  let role = 'dm'
  let speaker = '地下城主'
  let companionChar = null

  if (dialogueMode === 'stage' && currentSeg) {
    role = currentSeg.role
    speaker = currentSeg.speaker || '旁白'
    if (role === 'companion') {
      // 匹配队友（按名字模糊比较，处理 LLM 输出与角色名的轻微差异）
      companionChar = (companions || []).find(c =>
        c.name === speaker || c.name?.includes(speaker) || speaker?.includes(c.name)
      )
    }
  } else if (!hasDmContent) {
    return null  // chat 模式且没有 DM 内容时隐藏
  }

  // 配色
  // DM 旁白用金色，而不是紫色（紫色更适合 NPC）
  const effectiveRole = (role === 'dm') ? 'dm_narration' : role
  const plateClass = effectiveRole === 'companion'
    ? 'companion'
    : effectiveRole === 'dm_narration' ? 'gold' : 'default'
  const figureLabel = role === 'dm' ? '旁白' : speaker
  const figureInitial = companionChar
    ? (companionChar.name || '队').slice(0, 1)
    : role === 'dm' ? 'DM'
    : role === 'npc' ? (speaker || 'NPC').slice(0, 1)
    : (speaker || '?').slice(0, 1)
  const plateLabel = role === 'dm' ? '❖ 旁白'
    : role === 'npc' ? `❖ ${speaker}`
    : role === 'companion' ? `◈ ${speaker}`
    : speaker

  return (
    <div
      className={`stage-figure left stage-speaker-figure ${effectiveRole}`}
      role="group"
      aria-label={`当前说话者：${figureLabel}`}
    >
      <div className="silhouette stage-speaker-silhouette">
        {companionChar && window.Portrait ? null : (
          <div className="stage-figure-initial stage-speaker-initial">
            {figureInitial}
          </div>
        )}
      </div>
      <div className={`nameplate stage-speaker-nameplate ${plateClass}`}>
        {plateLabel}
      </div>
    </div>
  )
}
