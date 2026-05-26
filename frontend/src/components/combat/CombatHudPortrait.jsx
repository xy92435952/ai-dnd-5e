import React from 'react'

export default function CombatHudPortrait({ session, character = null, playerClass, playerSubclass, playerLevel, turnState }) {
  const player = character || session?.player
  const hpMax = player?.hp_max ?? player?.derived?.hp_max ?? 1
  return (
    <div className="hud-portrait">
      <div className="big" style={{ position: 'relative' }}>
        {(player?.name || 'P').slice(0, 1)}
        {(() => {
          const hp = player?.hp_current ?? 0
          return hp > 0 && hp / hpMax <= 0.25 ? <span className="avatar-crack" /> : null
        })()}
      </div>
      <div className="stats">
        <div className="name">{player?.name || '玩家'}</div>
        <div className="sub">{playerClass || '?'} {playerSubclass ? `· ${playerSubclass} ` : ''}· Lv {playerLevel}</div>
        <div className={`hp-segmented ${(() => {
          const hp = player?.hp_current ?? 0
          return hp / hpMax < .34 ? 'low' : hp / hpMax < .67 ? 'mid' : ''
        })()}`}>
          {(() => {
            const hp = player?.hp_current ?? 0
            const segs = 12
            const filled = Math.round((hp / hpMax) * segs)
            return Array.from({ length: segs }).map((_, i) => (
              <div key={i} className={`seg ${i >= filled ? 'empty' : ''}`} />
            ))
          })()}
        </div>
        <div className="hp-text">
          <span><span className="cur">{player?.hp_current ?? 0}</span> / {hpMax}</span>
          <span>移动 <b style={{ color: 'var(--arcane-light)' }}>{(turnState?.movement_max ?? 6) - (turnState?.movement_used ?? 0)}/{turnState?.movement_max ?? 6}</b></span>
        </div>
        <div className="stat-line">
          <span>AC <span className="v">{player?.derived?.ac ?? player?.ac ?? 10}</span></span>
          <span>先攻 <span className="v">{(() => { const m = player?.derived?.initiative ?? 0; return (m >= 0 ? '+' : '') + m })()}</span></span>
          {player?.derived?.spell_save_dc && (
            <span>DC <span className="v">{player.derived.spell_save_dc}</span></span>
          )}
        </div>
        {player?.conditions?.length > 0 && (
          <div className="conditions">
            {player.conditions.slice(0, 6).map((c, i) => (
              <span key={i} className="cond-icon" title={c}>⚠</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
