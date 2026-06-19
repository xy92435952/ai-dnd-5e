import React from 'react'

export default function CharacterCreateStepSpellsCantrips({ cantripCount, chosenCantrips, availableCantrips, toggleCantrip }) {
  if (cantripCount <= 0) return null

  return (
    <section className="spell-choice-section" aria-label="Cantrip choices">
      <div className="spell-section-title">
        <span className="t spell-choice-title-cantrip">戏法（0环，无限使用）</span>
        <span
          className="count spell-choice-count"
          data-complete={chosenCantrips.length === cantripCount ? 'true' : 'false'}
        >
          {chosenCantrips.length}/{cantripCount}
        </span>
      </div>
      <div className="spell-grid" role="list" aria-label="Cantrip options">
        {availableCantrips.map(name => {
          const sel = chosenCantrips.includes(name)
          const dis = !sel && chosenCantrips.length >= cantripCount
          return (
            <button
              key={name}
              type="button"
              disabled={dis}
              onClick={() => toggleCantrip(name)}
              className={`spell-card cantrip${sel ? ' sel' : ''}${dis ? ' dis' : ''}`}
              data-selected={sel ? 'true' : 'false'}
              role="listitem"
              aria-label={`Cantrip ${name}`}
            >
              <span className="sp-icon">{sel ? '\u2713' : '○'}</span>
              <span className="sp-name">{name}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
