import React from 'react'

export default function SpellModalTabs({
  level,
  setLevel,
  setSelectedSpell,
  cantripCount,
  spellList,
  available,
}) {
  return (
    <div className="flex gap-1.5 mb-3 flex-wrap">
      <button onClick={() => { setLevel(0); setSelectedSpell(null) }}
        className="px-2 py-1 rounded text-xs"
        style={{
          background: level===0 ? 'rgba(58,122,170,0.25)' : 'var(--bg)',
          border: `1px solid ${level===0 ? 'var(--blue-light)' : 'var(--wood-light)'}`,
          color: level===0 ? 'var(--blue-light)' : cantripCount > 0 ? 'var(--parchment)' : 'var(--wood-light)',
          cursor: 'pointer', fontFamily: 'inherit',
        }}>
        戏法 ({cantripCount})
      </button>
      {[1,2,3,4,5].map(lvl => {
        const cnt = available(lvl)
        const hasSpells = spellList.some(s => s.level <= lvl)
        return (
          <button key={lvl} onClick={() => { setLevel(lvl); setSelectedSpell(null) }}
            disabled={cnt <= 0 || !hasSpells}
            className="px-2 py-1 rounded text-xs"
            style={{
              background: level===lvl ? 'rgba(138,90,246,0.25)' : 'var(--bg)',
              border: `1px solid ${level===lvl ? '#8a5af6' : 'var(--wood-light)'}`,
              color: (cnt > 0 && hasSpells) ? (level===lvl ? '#c084fc' : 'var(--parchment)') : 'var(--wood-light)',
              cursor: (cnt > 0 && hasSpells) ? 'pointer' : 'not-allowed',
              fontFamily: 'inherit',
            }}>
            {lvl}环 ({cnt})
          </button>
        )
      })}
    </div>
  )
}
