import React from 'react'

export default function CharacterCreateStepSpellsKnown({ spellCount, chosenSpells, availableSpells, toggleSpell }) {
  if (spellCount <= 0) return null

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.875rem', color: '#c084fc' }}>已知法术</span>
        <span style={{ fontSize: '0.75rem', color: chosenSpells.length === spellCount ? 'var(--green-light)' : 'var(--gold)' }}>
          {chosenSpells.length}/{spellCount}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {availableSpells.map(name => {
          const sel = chosenSpells.includes(name)
          const dis = !sel && chosenSpells.length >= spellCount
          return (
            <button
              key={name}
              disabled={dis}
              onClick={() => toggleSpell(name)}
              className="skill-btn"
              style={{
                textAlign: 'left',
                padding: '8px 12px',
                borderColor: sel ? '#c084fc' : 'var(--wood-light)',
                background: sel ? 'rgba(192,132,252,0.12)' : undefined,
                color: dis ? 'var(--wood-light)' : sel ? '#c084fc' : 'var(--parchment)',
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
