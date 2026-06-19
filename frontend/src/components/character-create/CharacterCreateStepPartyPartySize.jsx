import React from 'react'

export default function CharacterCreateStepPartyPartySize({ partySize, setPartySize }) {
  return (
    <section className="companions-party-size" aria-label="Party size">
      <span className="companions-party-size-label">队伍人数</span>
      <div className="companions-party-size-options" role="group" aria-label="Party size options">
        {[2, 3, 4].map(n => (
          <button
            key={n}
            type="button"
            className={`${partySize === n ? 'btn-gold' : 'btn-ghost'} companions-party-size-button`}
            data-selected={partySize === n ? 'true' : 'false'}
            aria-pressed={partySize === n}
            onClick={() => setPartySize(n)}
          >
            {n} 人
          </button>
        ))}
      </div>
    </section>
  )
}
