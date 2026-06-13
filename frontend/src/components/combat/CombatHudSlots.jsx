import React from 'react'

const READY_SPELL_CONCENTRATION_PREFIXES = ['准备法术: ', '准备法术：', 'Ready Spell: ']

export function formatConcentrationLabel(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  const prefix = READY_SPELL_CONCENTRATION_PREFIXES.find(item => text.startsWith(item))
  if (!prefix) return text
  const spellName = text.slice(prefix.length).trim()
  return spellName ? `准备法术 ${spellName}` : '准备法术'
}

export default function CombatHudSlots({
  session,
  playerSpellSlots,
  character = null,
  disabled = false,
  onEndConcentration,
}) {
  const caster = character || session?.player
  const slotMax = caster?.derived?.spell_slots_max || session?.player?.derived?.spell_slots_max || {}
  const canEndConcentration = Boolean(caster?.concentration && onEndConcentration && !disabled)
  const concentrationLabel = formatConcentrationLabel(caster?.concentration)
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
          const max = slotMax[lvl] || cur
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
      {caster?.concentration && (
        <div
          style={{
            marginTop: 8,
            paddingTop: 6,
            borderTop: '1px solid rgba(138,90,24,.3)',
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            color: 'var(--parchment-dark)',
            letterSpacing: '.1em',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
          }}
        >
          <span>
            专注 <span style={{ color: 'var(--flame)' }}>{concentrationLabel}</span>
          </span>
          {onEndConcentration && (
            <button
              type="button"
              onClick={onEndConcentration}
              disabled={!canEndConcentration}
              aria-label={`结束专注 ${concentrationLabel}`}
              title={disabled ? '同步或结算完成后可结束专注' : `结束对 ${concentrationLabel} 的专注`}
              style={{
                border: '1px solid rgba(240,120,80,.55)',
                background: canEndConcentration ? 'rgba(80,20,12,.65)' : 'rgba(80,64,48,.35)',
                color: canEndConcentration ? 'var(--flame)' : 'var(--text-dim)',
                fontFamily: 'inherit',
                fontSize: 9,
                padding: '2px 6px',
                cursor: canEndConcentration ? 'pointer' : 'not-allowed',
              }}
            >
              结束
            </button>
          )}
        </div>
      )}
    </div>
  )
}
