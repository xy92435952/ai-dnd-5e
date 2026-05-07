import React from 'react'

export default function CombatHudSlots({ session, playerSpellSlots }) {
  return (
    <div style={{
      padding: '8px 10px',
      background: 'linear-gradient(180deg, #1a1208, #0a0604)',
      border: '1px solid rgba(138,90,24,.5)',
      boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
    }}>
      <div style={{ fontFamily: 'var(--font-heading)', fontSize: 10, color: 'var(--amber)', letterSpacing: '.2em', textTransform: 'uppercase', marginBottom: 6 }}>
        ✦ 法术位
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {Object.entries(playerSpellSlots || {}).filter(([lvl, cur]) => cur > 0 || /^(1st|2nd|3rd)$/.test(lvl)).slice(0, 4).map(([lvl, cur]) => {
          const max = session?.player?.derived?.spell_slots_max?.[lvl] || cur
          return (
            <div key={lvl} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--arcane-light)', letterSpacing: '.08em', width: 24 }}>{lvl}</span>
              <div className="spell-slots">
                {Array.from({ length: Math.max(max, cur) }).map((_, i) => (
                  <div key={i} className={`slot-gem ${i >= cur ? 'used' : ''}`} />
                ))}
              </div>
            </div>
          )
        })}
      </div>
      {session?.player?.concentration && (
        <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(138,90,24,.3)', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.1em' }}>
          专注 <span style={{ color: 'var(--flame)' }}>{session.player.concentration}</span>
        </div>
      )}
    </div>
  )
}
