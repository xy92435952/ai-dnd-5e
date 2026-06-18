/**
 * PrepareSpellsModal: long-rest spell preparation.
 *
 * The backend remains authoritative for spell-list validity and prepared limits.
 * This modal mirrors those options so prepared casters can choose from their
 * class list plus subclass expanded spells, while spellbook/known casters keep
 * their narrower source lists.
 */
import { useEffect, useMemo, useState } from 'react'
import { charactersApi } from '../../api/client'
import { getClassEnKey } from '../../utils/characterCreate'
import Overlay from './Overlay'
import { BookIcon } from '../Icons'

const HALF_PREPARED_CLASSES = new Set(['Paladin'])

function getSpellName(spell) {
  return typeof spell === 'string' ? spell : spell?.name
}

function isLeveledSpell(spell) {
  if (typeof spell === 'string') return true
  const level = Number(spell?.level)
  return !Number.isFinite(level) || level > 0
}

function uniqueSpellNames(spells = []) {
  const seen = new Set()
  const names = []
  ;(spells || []).forEach((spell) => {
    const name = getSpellName(spell)
    if (!name || seen.has(name)) return
    seen.add(name)
    names.push(name)
  })
  return names
}

function normalizeSubclassKey(subclass) {
  return String(subclass || '')
    .trim()
    .toLowerCase()
    .replace(/^the\s+/, '')
    .replace(/\s+domain$/, '')
}

function findSubclassSpellDetails(options = {}, subclass = '') {
  const detailsBySubclass = options?.subclass_bonus_spell_details || {}
  if (detailsBySubclass[subclass]) return detailsBySubclass[subclass]

  const normalized = normalizeSubclassKey(subclass)
  const matchedKey = Object.keys(detailsBySubclass).find(
    key => normalizeSubclassKey(key) === normalized,
  )
  return matchedKey ? detailsBySubclass[matchedKey] : null
}

function subclassSpellDetailsForLevel(options = {}, subclass = '', level = 1) {
  const details = findSubclassSpellDetails(options, subclass)
  if (!details) return []
  if (Array.isArray(details)) return details

  return Object.entries(details || {})
    .filter(([threshold]) => Number(threshold) <= level)
    .flatMap(([, spells]) => spells || [])
}

function buildAvailableSpellNames(player = {}, options = {}, classKey = '', preparationType = '') {
  const knownSpells = uniqueSpellNames(player.known_spells || [])
  if (preparationType === 'known' || preparationType === 'spellbook') {
    return knownSpells
  }

  if (preparationType !== 'prepared') {
    return knownSpells
  }

  const level = Number(player.level) || 1
  const classSpells = options?.class_spell_details?.[classKey] || options?.class_spells?.[classKey] || []
  const subclassSpells = subclassSpellDetailsForLevel(options, player.subclass, level)
  const spellNames = uniqueSpellNames(
    [...classSpells, ...subclassSpells].filter(isLeveledSpell),
  )

  return spellNames.length ? spellNames : knownSpells
}

function maxPreparedSpells(player = {}, classKey = '', spellMod = 0, preparationType = '') {
  if (preparationType === 'known') {
    return uniqueSpellNames(player.known_spells || []).length
  }

  const level = Number(player.level) || 1
  if (preparationType === 'prepared' && HALF_PREPARED_CLASSES.has(classKey)) {
    return Math.max(1, Math.floor(level / 2) + spellMod)
  }
  return Math.max(1, level + spellMod)
}

function setsEqual(a, b) {
  if (a.size !== b.size) return false
  return [...a].every(item => b.has(item))
}

function preparationTypeLabel(type) {
  if (type === 'known') return '已知施法者'
  if (type === 'spellbook') return '法术书'
  if (type === 'prepared') return '每日准备'
  return '角色法术'
}

export default function PrepareSpellsModal({ player, onSave, onClose }) {
  const derived = player.derived || {}
  const mods = derived.ability_modifiers || {}
  const spellMod = derived.spell_ability ? (mods[derived.spell_ability] || 0) : 0
  const classKey = getClassEnKey(player.char_class)
  const [options, setOptions] = useState(null)
  const preparationType = options?.spell_preparation_type?.[classKey] || player.preparation_type || ''
  const availableSpellNames = useMemo(
    () => buildAvailableSpellNames(player, options || {}, classKey, preparationType),
    [player, options, classKey, preparationType],
  )
  const availableSpellKey = availableSpellNames.join('\u0000')
  const maxPrepared = maxPreparedSpells(player, classKey, spellMod, preparationType)
  const knownCasterLocked = preparationType === 'known'
  const typeLabel = preparationTypeLabel(preparationType)

  const [selected, setSelected] = useState(new Set(player.prepared_spells || []))

  useEffect(() => {
    let active = true
    charactersApi.options()
      .then((data) => {
        if (active) setOptions(data || {})
      })
      .catch(() => {
        if (active) setOptions({})
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (knownCasterLocked) {
      setSelected(new Set(availableSpellNames))
      return
    }
    if (options === null) return

    setSelected((prev) => {
      const available = new Set(availableSpellNames)
      const next = new Set([...prev].filter(spell => available.has(spell)))
      return setsEqual(prev, next) ? prev : next
    })
  }, [knownCasterLocked, options, availableSpellKey])

  const toggle = (spell) => setSelected(prev => {
    if (knownCasterLocked) return prev
    const next = new Set(prev)
    if (next.has(spell)) next.delete(spell)
    else if (next.size < maxPrepared) next.add(spell)
    return next
  })

  return (
    <Overlay onClose={onClose}>
      <div className="prepare-modal-head">
        <div>
          <h3>
            <BookIcon size={18} color="var(--amethyst-light)" /> 准备法术
          </h3>
          <p>
            上限 {selected.size}/{maxPrepared}
          </p>
        </div>
        <button
          aria-label="关闭准备法术"
          onClick={onClose}
          type="button"
        >
          ×
        </button>
      </div>

      <div className="prepare-status" role="status" aria-live="polite">
        <span>{typeLabel}</span>
        <strong>{selected.size}/{maxPrepared}</strong>
        <b>{availableSpellNames.length} 个可选法术</b>
        {knownCasterLocked && <em>已知施法者无需每日准备</em>}
      </div>

      <div className="prepare-spell-list" aria-label="可准备法术列表" aria-live="polite">
        {availableSpellNames.map(spell => {
          const selectedSpell = selected.has(spell)
          const canSelect = selectedSpell || selected.size < maxPrepared
          return (
            <button
              key={spell}
              onClick={() => toggle(spell)}
              disabled={knownCasterLocked || !canSelect}
              aria-pressed={selectedSpell}
              className={`btn-fantasy prepare-spell-option ${selectedSpell ? 'selected' : ''} ${!canSelect ? 'capped' : ''}`}
            >
              {selectedSpell ? '\u2713 ' : ''}{spell}
            </button>
          )
        })}
        {availableSpellNames.length === 0 && (
          <p className="prepare-empty">
            暂无可准备法术
          </p>
        )}
      </div>

      <div className="prepare-modal-actions" role="group" aria-label="准备法术操作">
        <button
          aria-label="保存准备法术"
          className="btn-gold"
          onClick={() => onSave(knownCasterLocked ? availableSpellNames : [...selected])}
        >
          确认（{selected.size}/{maxPrepared}）
        </button>
        <button className="btn-fantasy" onClick={onClose} aria-label="取消准备法术">取消</button>
      </div>
    </Overlay>
  )
}
