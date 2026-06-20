import {
  formatMagicInitiateSpellOption,
  getMagicInitiateClassOptions,
  getMagicInitiateSpellOptionName,
  getMagicInitiateSpellOptions,
} from '../../utils/characterCreate'

export default function MagicInitiateChoiceFields({
  value = {},
  options = {},
  onChange,
  selectClassName = '',
}) {
  const classOptions = getMagicInitiateClassOptions(options)
  const selectedClass = value.spellcasting_class || ''
  const selectedCantrips = Array.isArray(value.cantrips) ? value.cantrips : []
  const selectedSpell = value.spell || ''
  const spellOptions = getMagicInitiateSpellOptions(options, selectedClass)
  const selectClasses = ['magic-initiate-choice-select', selectClassName]
    .filter(Boolean)
    .join(' ')

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
      <p className="magic-initiate-choice-empty" role="status">
        Magic Initiate options unavailable
      </p>
    )
  }

  return (
    <div className="magic-initiate-choice-fields" role="group" aria-label="Magic Initiate choices">
      <label className="magic-initiate-choice-label">
        Magic Initiate class
        <select
          aria-label="Magic Initiate class"
          className={selectClasses}
          value={selectedClass}
          onChange={(event) => emit({
            spellcasting_class: event.target.value,
            cantrips: [],
            spell: '',
          })}
        >
          <option value="">Choose class</option>
          {classOptions.map(className => (
            <option key={className} value={className}>{className}</option>
          ))}
        </select>
      </label>

      {selectedClass && (
        <>
          <div className="magic-initiate-choice-cantrip-group">
            <p className="magic-initiate-choice-title">
              Magic Initiate cantrips {selectedCantrips.length}/2
            </p>
            <div
              className="magic-initiate-choice-grid"
              role="list"
              aria-label="Magic Initiate cantrip choices"
            >
              {spellOptions.cantrips.map((cantrip) => {
                const name = getMagicInitiateSpellOptionName(cantrip)
                if (!name) return null
                const selected = selectedCantrips.includes(name)
                const disabled = !selected && selectedCantrips.length >= 2
                return (
                  <label
                    key={name}
                    className="magic-initiate-choice-card"
                    data-selected={selected ? 'true' : 'false'}
                    data-disabled={disabled ? 'true' : 'false'}
                    role="listitem"
                    aria-label={`Magic Initiate cantrip option ${name}`}
                  >
                    <input
                      className="magic-initiate-choice-checkbox"
                      type="checkbox"
                      aria-label={`Magic Initiate cantrip ${name}`}
                      checked={selected}
                      disabled={disabled}
                      onChange={() => toggleCantrip(name)}
                    />
                    <span className="magic-initiate-choice-name">
                      {formatMagicInitiateSpellOption(cantrip)}
                    </span>
                  </label>
                )
              })}
            </div>
          </div>

          <label className="magic-initiate-choice-label magic-initiate-choice-spell-label">
            Magic Initiate spell
            <select
              aria-label="Magic Initiate spell"
              className={selectClasses}
              value={selectedSpell}
              onChange={(event) => emit({ spell: event.target.value })}
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
