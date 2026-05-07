import React from 'react'
import { SpellIcon, HeartIcon } from '../Icons'

export default function SpellModalList({
  level,
  shownSpells,
  cantrips,
  selectedSpell,
  setSelectedSpell,
  onSpellHover,
}) {
  return (
    <div className="space-y-1.5 overflow-y-auto flex-1" style={{ maxHeight:260 }}>
      {shownSpells.length === 0 ? (
        <p className="text-xs text-center py-4" style={{ color: 'var(--text-dim)' }}>
          {level === 0 ? '未习得戏法' : '当前法术位不足或无可用法术'}
        </p>
      ) : shownSpells.map(spell => {
        const isSel = selectedSpell?.name === spell.name
        const isCantrip = spell.level === 0 || cantrips?.includes(spell.name)
        return (
          <div key={spell.name}
            onClick={() => setSelectedSpell(isSel ? null : spell)}
            onMouseEnter={() => onSpellHover?.(spell)}
            onMouseLeave={() => onSpellHover?.(null)}
            style={{
              padding:'8px 10px', borderRadius:6, cursor:'pointer',
              background: isSel ? (isCantrip ? 'rgba(58,122,170,0.18)' : 'rgba(138,90,246,0.18)') : 'var(--bg)',
              border: `1px solid ${isSel ? (isCantrip ? 'var(--blue-light)' : '#8a5af6') : 'var(--wood)'}`,
              transition:'all 0.1s',
            }}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold" style={{ color:'var(--parchment)' }}>
                {isCantrip
                  ? <SpellIcon size={12} color="var(--blue-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
                  : spell.type==='heal'
                    ? <HeartIcon size={12} color="var(--green-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
                    : <SpellIcon size={12} color="var(--red-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />}
                {spell.name}
                {isCantrip && <span className="ml-1 text-xs" style={{ color:'var(--blue-light)', opacity:0.7 }}>戏法</span>}
              </span>
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                {spell.type==='damage' ? spell.damage : spell.heal}
              </span>
            </div>
            {spell.desc && <p className="text-xs mt-0.5 line-clamp-1" style={{ color: 'var(--text-dim)' }}>{spell.desc}</p>}
          </div>
        )
      })}
    </div>
  )
}
