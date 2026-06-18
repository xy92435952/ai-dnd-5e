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
  const slotRows = Object.entries(playerSpellSlots || {})
    .filter(([lvl, cur]) => cur > 0 || /^(1st|2nd|3rd)$/.test(lvl))
    .slice(0, 4)

  return (
    <section className="combat-spell-slot-panel" aria-label="法术位与专注">
      <div className="combat-spell-slot-title">
        ✦ 法术位
      </div>
      <div className="combat-spell-slot-list" role="list" aria-label="当前法术位">
        {slotRows.map(([lvl, cur]) => {
          const max = slotMax[lvl] || cur
          return (
            <div
              key={lvl}
              className="combat-spell-slot-row"
              role="listitem"
              aria-label={`${lvl} 法术位 ${cur}/${max}`}
            >
              <span className="combat-spell-slot-level">{lvl}</span>
              <div className="spell-slots">
                {Array.from({ length: Math.max(max, cur) }).map((_, i) => (
                  <div
                    key={i}
                    className={`slot-gem ${i >= cur ? 'used' : ''}`}
                    aria-hidden="true"
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>
      {caster?.concentration && (
        <div
          className="combat-concentration-row"
          role="status"
          aria-live="polite"
        >
          <span>
            专注 <span className="combat-concentration-label">{concentrationLabel}</span>
          </span>
          {onEndConcentration && (
            <button
              type="button"
              onClick={onEndConcentration}
              disabled={!canEndConcentration}
              aria-label={`结束专注 ${concentrationLabel}`}
              title={disabled ? '同步或结算完成后可结束专注' : `结束对 ${concentrationLabel} 的专注`}
              className="combat-end-concentration-button"
            >
              结束
            </button>
          )}
        </div>
      )}
    </section>
  )
}
