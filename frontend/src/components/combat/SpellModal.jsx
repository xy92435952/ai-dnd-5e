/**
 * SpellModal — 战斗中的法术选择弹窗。
 *
 * 原内嵌在 pages/Combat.jsx，抽出来独立组件化。
 * 无 business state，只接受 props 并通过 onCast / onClose 回调外抛。
 *
 * Props:
 *   spells       - Array<{name, level, type, damage, heal, desc, aoe}>
 *   cantrips     - string[] 已知戏法名字
 *   slots        - { "1st": 2, "2nd": 1, ... } 当前法术位余量
 *   onCast       - (spell, level: number) => void
 *   onClose      - () => void
 *   onSpellHover - (spell|null) => void  可选，用于地图上预览 AoE 半径
 */
import { useState } from 'react'
import { SpellIcon, HeartIcon } from '../Icons'

export default function SpellModal({ spells, cantrips, slots, onCast, onClose, onSpellHover }) {
  const [selectedSpell, setSelectedSpell] = useState(null)
  const [level, setLevel] = useState(0)  // 0 = 戏法标签页

  const slotLabel = (lvl) => ['1st','2nd','3rd','4th','5th','6th','7th','8th','9th'][lvl-1] || `${lvl}th`
  const available = (lvl) => slots?.[slotLabel(lvl)] || 0

  const cantripList = spells.filter(s => s.level === 0 || cantrips?.includes(s.name))
  const spellList   = spells.filter(s => s.level > 0 && !cantrips?.includes(s.name))
  const shownSpells = level === 0 ? cantripList : spellList.filter(s => s.level <= level)

  const canCast = selectedSpell
    ? (selectedSpell.level === 0 || cantrips?.includes(selectedSpell.name))
      ? true
      : available(level) > 0
    : false

  return (
    <div onClick={onClose} style={{
      position:'fixed', inset:0, zIndex:500,
      background:'rgba(0,0,0,0.65)',
      display:'flex', alignItems:'center', justifyContent:'center',
    }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{
        padding:20, minWidth:340, maxWidth:420,
        maxHeight:'80vh', display:'flex', flexDirection:'column',
      }}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-sm" style={{ color:'var(--gold)' }}>
            <SpellIcon size={14} color="#8a5af6" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            选择法术
          </h3>
          <button onClick={onClose} style={{ color:'var(--text-dim)', fontSize:18, background:'none', border:'none', cursor:'pointer' }}>x</button>
        </div>

        <div className="flex gap-1.5 mb-3 flex-wrap">
          <button onClick={() => { setLevel(0); setSelectedSpell(null) }}
            className="px-2 py-1 rounded text-xs"
            style={{
              background: level===0 ? 'rgba(58,122,170,0.25)' : 'var(--bg)',
              border: `1px solid ${level===0 ? 'var(--blue-light)' : 'var(--wood-light)'}`,
              color: level===0 ? 'var(--blue-light)' : cantripList.length > 0 ? 'var(--parchment)' : 'var(--wood-light)',
              cursor: 'pointer', fontFamily: 'inherit',
            }}>
            戏法 ({cantripList.length})
          </button>
          {[1,2,3,4,5].map(lvl => {
            const cnt = available(lvl)
            const hasSpells = spellList.some(s => s.level <= lvl)
            return (
              <button key={lvl} onClick={() => { setLevel(lvl); setSelectedSpell(null) }}
                disabled={cnt <= 0 || !hasSpells}
                className="px-2 py-1 rounded text-xs"
                style={{
                  background: level===lvl ? 'rgba(138,90,246,0.25)' : 'var(--bg)',
                  border: `1px solid ${level===lvl ? '#8a5af6' : 'var(--wood-light)'}`,
                  color: (cnt > 0 && hasSpells) ? (level===lvl ? '#c084fc' : 'var(--parchment)') : 'var(--wood-light)',
                  cursor: (cnt > 0 && hasSpells) ? 'pointer' : 'not-allowed',
                  fontFamily: 'inherit',
                }}>
                {lvl}环 ({cnt})
              </button>
            )
          })}
        </div>

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

        <div className="flex gap-2 mt-3">
          <button className="flex-1 btn-fantasy py-2 text-sm"
            style={{ borderColor: canCast ? '#8a5af6' : 'var(--wood)', opacity: canCast ? 1 : 0.4 }}
            disabled={!canCast}
            onClick={() => selectedSpell && onCast(selectedSpell, level || 1)}>
            <SpellIcon size={14} color="#8a5af6" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
            施放{selectedSpell ? `【${selectedSpell.name}】` : ''}
          </button>
          <button className="btn-fantasy px-4 py-2 text-sm" onClick={onClose}>取消</button>
        </div>
      </div>
    </div>
  )
}
