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
 *   player         未使用（保留以备将来玩家头像扩展）
 *   hasDmContent   chat 模式时控制是否显示
 */
export default function StageLeftFigure({ dialogueMode, currentSeg, companions, player, hasDmContent }) {
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
  const palette = {
    dm:           { light: '#7a4fc4', dark: '#1a0a3a', txtColor: '#d8c8ff', plate: 'default',   glow: 'rgba(168,144,232,.6)' },
    npc:          { light: '#c44848', dark: '#3a0a0a', txtColor: '#ffcaca', plate: 'default',   glow: 'rgba(240,80,80,.55)' },
    companion:    { light: '#3ec8d8', dark: '#14444e', txtColor: '#d8eeff', plate: 'companion', glow: 'rgba(127,200,248,.55)' },
    dm_narration: { light: '#e8c070', dark: '#5a4018', txtColor: '#fff6d8', plate: 'gold',      glow: 'rgba(240,208,96,.5)' },
  }
  // DM 旁白用金色，而不是紫色（紫色更适合 NPC）
  const effectiveRole = (role === 'dm') ? 'dm_narration' : role
  const p = palette[effectiveRole] || palette.dm
  const bg = `radial-gradient(circle at 40% 30%, ${p.light}, ${p.dark} 75%)`

  return (
    <div className="stage-figure left" style={{ '--c-light': p.light }}>
      <div className="silhouette" style={{ background: bg }}>
        {companionChar && window.Portrait ? null : (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'grid', placeItems: 'center',
            fontFamily: 'var(--font-display)', fontSize: 72,
            color: p.txtColor, textShadow: '0 4px 12px #000',
            filter: `drop-shadow(0 0 12px ${p.glow})`,
          }}>
            {companionChar
              ? (companionChar.name || '队').slice(0, 1)
              : role === 'dm' ? 'DM'
              : role === 'npc' ? (speaker || 'NPC').slice(0, 1)
              : (speaker || '?').slice(0, 1)}
          </div>
        )}
      </div>
      <div className="nameplate" style={
        p.plate === 'companion' ? {
          background: 'linear-gradient(180deg, #3ec8d8, #14444e)',
          color: '#04181c',
          boxShadow: '0 0 0 1px rgba(127,232,248,.6), 0 0 12px -2px var(--arcane-light)',
        } : p.plate === 'gold' ? {
          background: 'linear-gradient(180deg, #e8c070, #5a4018)',
          color: '#1a0a04',
          boxShadow: '0 0 0 1px rgba(240,208,96,.6), 0 0 12px -2px var(--amber)',
        } : undefined
      }>
        {role === 'dm' ? '❖ 旁白'
          : role === 'npc'        ? `❖ ${speaker}`
          : role === 'companion'  ? `◈ ${speaker}`
          : speaker}
      </div>
    </div>
  )
}
