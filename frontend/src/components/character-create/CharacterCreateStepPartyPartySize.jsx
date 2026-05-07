import React from 'react'

export default function CharacterCreateStepPartyPartySize({ partySize, setPartySize }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 10,
      margin: '18px 0',
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--parchment-dark)',
      letterSpacing: '.15em',
    }}>
      <span>队伍人数</span>
      {[2, 3, 4].map(n => (
        <button
          key={n}
          className={partySize === n ? 'btn-gold' : 'btn-ghost'}
          style={{ padding: '4px 12px', fontSize: 11 }}
          onClick={() => setPartySize(n)}
        >
          {n} 人
        </button>
      ))}
    </div>
  )
}
