import React from 'react'

export default function CharacterCreateStepSpellsKnown({ spellCount, chosenSpells, availableSpells, toggleSpell }) {
  if (spellCount <= 0) return null

  return (
    <section className="spell-choice-section" aria-label="Known spell choices">
      <div className="spell-section-title">
        <span className="t spell-choice-title-known">已知法术</span>
        <span
          className="count spell-choice-count"
          data-complete={chosenSpells.length === spellCount ? 'true' : 'false'}
        >
          {chosenSpells.length}/{spellCount}
        </span>
      </div>
      <div className="spell-grid" role="list" aria-label="Known spell options">
        {availableSpells.map(name => {
          const sel = chosenSpells.includes(name)
          const dis = !sel && chosenSpells.length >= spellCount
          return (
            <button
              key={name}
              type="button"
              disabled={dis}
              onClick={() => toggleSpell(name)}
              className={`spell-card lv1${sel ? ' sel' : ''}${dis ? ' dis' : ''}`}
              data-selected={sel ? 'true' : 'false'}
              role="listitem"
              aria-label={`Known spell ${name}`}
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
