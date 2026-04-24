/**
 * PrepareSpellsModal — 长休后准备法术（法师/牧师/德鲁伊）。
 *
 * 上限 = 角色等级 + 施法属性调整值（最少 1）。
 *
 * Props:
 *   player  - 当前玩家 Character
 *   onSave  - (prepared: string[]) => void
 *   onClose - () => void
 */
import { useState } from 'react'
import Overlay from './Overlay'
import { BookIcon } from '../Icons'

export default function PrepareSpellsModal({ player, onSave, onClose }) {
  const derived = player.derived || {}
  const mods = derived.ability_modifiers || {}
  const spellMod = derived.spell_ability ? (mods[derived.spell_ability] || 0) : 0
  const maxPrepared = Math.max(1, player.level + spellMod)

  const [selected, setSelected] = useState(new Set(player.prepared_spells || []))
  const toggle = (s) => setSelected(prev => {
    const n = new Set(prev)
    if (n.has(s)) n.delete(s)
    else if (n.size < maxPrepared) n.add(s)
    return n
  })

  return (
    <Overlay onClose={onClose}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ color: 'var(--amethyst-light)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
            <BookIcon size={18} color="var(--amethyst-light)" /> 准备法术
          </h3>
          <p style={{ color: 'var(--parchment-dark)', fontSize: 12, margin: '4px 0 0' }}>
            上限 {selected.size}/{maxPrepared}
          </p>
        </div>
        <button onClick={onClose} style={{ color: 'var(--parchment-dark)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>x</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
        {(player.known_spells || []).map(spell => {
          const sel = selected.has(spell)
          const can = sel || selected.size < maxPrepared
          return (
            <button
              key={spell}
              onClick={() => toggle(spell)}
              className="btn-fantasy"
              style={{
                textAlign: 'left', opacity: can ? 1 : 0.4,
                borderColor: sel ? 'var(--amethyst)' : undefined,
                background:  sel ? 'rgba(138,79,212,0.15)' : undefined,
                color:       sel ? 'var(--amethyst-light)' : undefined,
              }}
            >
              {sel ? '\u2713 ' : ''}{spell}
            </button>
          )
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-gold" style={{ padding: '8px 16px', fontSize: 13 }} onClick={() => onSave([...selected])}>
          确认（{selected.size}/{maxPrepared}）
        </button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>取消</button>
      </div>
    </Overlay>
  )
}
