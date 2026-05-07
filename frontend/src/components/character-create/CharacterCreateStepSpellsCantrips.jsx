import React from 'react'

export default function CharacterCreateStepSpellsCantrips({ cantripCount, chosenCantrips, availableCantrips, toggleCantrip }) {
  if (cantripCount <= 0) return null

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.875rem', color: 'var(--blue-light)' }}>戏法（0环，无限使用）</span>
        <span style={{ fontSize: '0.75rem', color: chosenCantrips.length === cantripCount ? 'var(--green-light)' : 'var(--gold)' }}>
          {chosenCantrips.length}/{cantripCount}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {availableCantrips.map(name => {
          const sel = chosenCantrips.includes(name)
          const dis = !sel && chosenCantrips.length >= cantripCount
          return (
            <button
              key={name}
              disabled={dis}
              onClick={() => toggleCantrip(name)}
              className="skill-btn"
              style={{
                textAlign: 'left',
                padding: '8px 12px',
                borderColor: sel ? 'var(--blue-light)' : 'var(--wood-light)',
                background: sel ? 'rgba(58,122,170,0.12)' : undefined,
                color: dis ? 'var(--wood-light)' : sel ? 'var(--blue-light)' : 'var(--parchment)',
                cursor: dis ? 'not-allowed' : 'pointer',
                opacity: dis ? 0.4 : 1,
              }}
            >
              {sel && '\u2713 '}{name}
            </button>
          )
        })}
      </div>
    </div>
  )
}
