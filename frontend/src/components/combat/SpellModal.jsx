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
import { useEffect, useMemo, useState } from 'react'
import { SpellIcon } from '../Icons'
import SpellModalTabs from './SpellModalTabs'
import SpellModalList from './SpellModalList'
import SpellModalActions from './SpellModalActions'
import SpellCastPlan from './SpellCastPlan'
import { getSpellCastDisabledReason, spellNameMatches } from '../../utils/combat'
import { buildSpellCastPlan } from '../../utils/spellCastPlan'

function isCantripSpell(spell, cantripNames) {
  return spell.level === 0 || (cantripNames || []).some(name => spellNameMatches(spell, name))
}

export default function SpellModal({
  spells = [],
  cantrips = [],
  slots = {},
  quickPick,
  selectedTarget = null,
  playerId = null,
  combat = null,
  aoeHover = null,
  aoeLockedCenter = null,
  onCast,
  onClose,
  onSpellHover,
  onResetAoeCenter,
}) {
  const [selectedSpell, setSelectedSpell] = useState(null)
  const [level, setLevel] = useState(0)  // 0 = 戏法标签页

  const slotLabel = (lvl) => ['1st','2nd','3rd','4th','5th','6th','7th','8th','9th'][lvl-1] || `${lvl}th`
  const available = (lvl) => slots?.[slotLabel(lvl)] || 0

  const cantripList = spells.filter(spell => isCantripSpell(spell, cantrips))
  const spellList   = spells.filter(s => s.level > 0 && !isCantripSpell(s, cantrips))
  const shownSpells = level === 0 ? cantripList : spellList.filter(s => s.level <= level)
  const caster = (playerId ? combat?.entities?.[playerId] : combat?.player) || null

  useEffect(() => {
    if (!quickPick) return
    const picked = spells.find(spell => spellNameMatches(spell, quickPick))
    if (!picked) return
    setSelectedSpell(picked)
    setLevel(isCantripSpell(picked, cantrips) ? 0 : picked.level)
    onSpellHover?.(picked)
  }, [cantrips, onSpellHover, quickPick, spells])

  const castDisabledReason = getSpellCastDisabledReason({
    spell: selectedSpell,
    level,
    cantrips,
    available,
    selectedTarget,
    playerId,
    combat,
    aoeHover,
  })
  const canCast = !castDisabledReason
  const castPlan = useMemo(() => buildSpellCastPlan({
    spell: selectedSpell,
    level,
    cantrips,
    slots,
    selectedTarget,
    playerId,
    combat,
    aoeHover,
    aoeLockedCenter,
    disabledReason: castDisabledReason,
  }), [aoeHover, aoeLockedCenter, cantrips, castDisabledReason, combat, level, playerId, selectedSpell, selectedTarget, slots])

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

        <SpellModalTabs
          level={level}
          setLevel={setLevel}
          setSelectedSpell={setSelectedSpell}
          cantripCount={cantripList.length}
          spellList={spellList}
          available={available}
        />

        <SpellModalList
          level={level}
          shownSpells={shownSpells}
          cantrips={cantrips}
          caster={caster}
          combat={combat}
          playerId={playerId}
          selectedTarget={selectedTarget}
          selectedSpell={selectedSpell}
          setSelectedSpell={setSelectedSpell}
          onSpellHover={onSpellHover}
        />

        <SpellCastPlan plan={castPlan} onResetAoeCenter={onResetAoeCenter} />

        <SpellModalActions
          canCast={canCast}
          disabledReason={castDisabledReason}
          selectedSpell={selectedSpell}
          level={level}
          onCast={onCast}
          onClose={onClose}
        />
      </div>
    </div>
  )
}
