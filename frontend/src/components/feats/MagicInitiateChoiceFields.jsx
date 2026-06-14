import {
  formatMagicInitiateSpellOption,
  getMagicInitiateClassOptions,
  getMagicInitiateSpellOptionName,
  getMagicInitiateSpellOptions,
} from '../../utils/characterCreate'

const labelStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  color: 'var(--text-dim)',
  fontSize: 11,
}

const gridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
  gap: 6,
  marginTop: 6,
}

const choiceStyle = {
  minHeight: 34,
  borderRadius: 6,
  border: '1px solid var(--wood-light)',
  background: 'rgba(10,8,6,0.24)',
  padding: '6px 8px',
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  color: 'var(--parchment)',
  fontSize: 11,
}

export default function MagicInitiateChoiceFields({
  value = {},
  options = {},
  onChange,
  selectClassName = '',
  selectStyle = {},
}) {
  const classOptions = getMagicInitiateClassOptions(options)
  const selectedClass = value.spellcasting_class || ''
  const selectedCantrips = Array.isArray(value.cantrips) ? value.cantrips : []
  const selectedSpell = value.spell || ''
  const spellOptions = getMagicInitiateSpellOptions(options, selectedClass)

  const emit = (patch) => {
    if (!onChange) return
    onChange({
      spellcasting_class: selectedClass,
      cantrips: selectedCantrips,
      spell: selectedSpell,
      ...patch,
    })
  }

  const toggleCantrip = (cantripName) => {
    if (selectedCantrips.includes(cantripName)) {
      emit({ cantrips: selectedCantrips.filter(item => item !== cantripName) })
      return
    }
    if (selectedCantrips.length >= 2) return
    emit({ cantrips: [...selectedCantrips, cantripName] })
  }

  if (!classOptions.length) {
    return (
      <p style={{ color: 'var(--red-light)', fontSize: 10, margin: '8px 0 0' }}>
        Magic Initiate options unavailable
      </p>
    )
  }

  return (
    <div style={{ marginTop: 8 }}>
      <label style={labelStyle}>
        Magic Initiate class
        <select
          aria-label="Magic Initiate class"
          className={selectClassName}
          value={selectedClass}
          onChange={(event) => emit({
            spellcasting_class: event.target.value,
            cantrips: [],
            spell: '',
          })}
          style={selectStyle}
        >
          <option value="">Choose class</option>
          {classOptions.map(className => (
            <option key={className} value={className}>{className}</option>
          ))}
        </select>
      </label>

      {selectedClass && (
        <>
          <div style={{ marginTop: 8 }}>
            <p style={{ color: 'var(--gold-dim)', fontSize: 10, fontWeight: 700, margin: '0 0 4px', textTransform: 'uppercase' }}>
              Magic Initiate cantrips {selectedCantrips.length}/2
            </p>
            <div style={gridStyle}>
              {spellOptions.cantrips.map((cantrip) => {
                const name = getMagicInitiateSpellOptionName(cantrip)
                if (!name) return null
                const selected = selectedCantrips.includes(name)
                return (
                  <label key={name} style={choiceStyle}>
                    <input
                      type="checkbox"
                      aria-label={`Magic Initiate cantrip ${name}`}
                      checked={selected}
                      disabled={!selected && selectedCantrips.length >= 2}
                      onChange={() => toggleCantrip(name)}
                    />
                    <span>{formatMagicInitiateSpellOption(cantrip)}</span>
                  </label>
                )
              })}
            </div>
          </div>

          <label style={{ ...labelStyle, marginTop: 8 }}>
            Magic Initiate spell
            <select
              aria-label="Magic Initiate spell"
              className={selectClassName}
              value={selectedSpell}
              onChange={(event) => emit({ spell: event.target.value })}
              style={selectStyle}
            >
              <option value="">Choose spell</option>
              {spellOptions.spells.map((spell) => {
                const name = getMagicInitiateSpellOptionName(spell)
                if (!name) return null
                return (
                  <option key={name} value={name}>
                    {formatMagicInitiateSpellOption(spell)}
                  </option>
                )
              })}
            </select>
          </label>
        </>
      )}
    </div>
  )
}
