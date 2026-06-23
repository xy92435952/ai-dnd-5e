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
import {
  getMagicInitiateSpellCastInfo,
  getSpellCastDisabledReason,
  spellNameMatches,
} from '../../utils/combat'
import { buildSpellCastPlan } from '../../utils/spellCastPlan'
import { getBardicInspiration } from '../../utils/bardicInspiration'

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
  useBardicSpellSave = false,
  onToggleBardicSpellSave,
}) {
  const [selectedSpell, setSelectedSpell] = useState(null)
  const [level, setLevel] = useState(0)  // 0 = 戏法标签页

  const slotLabel = (lvl) => ['1st','2nd','3rd','4th','5th','6th','7th','8th','9th'][lvl-1] || `${lvl}th`
  const caster = (playerId ? combat?.entities?.[playerId] : combat?.player) || null
  const slotAvailable = (lvl) => slots?.[slotLabel(lvl)] || 0
  const magicInitiateAvailable = (lvl) => spells.some(spell =>
    getMagicInitiateSpellCastInfo({ spell, character: caster, castLevel: lvl }).canUse)
  const tabAvailable = (lvl) => slotAvailable(lvl) + (magicInitiateAvailable(lvl) ? 1 : 0)
  const selectedAvailable = (lvl) => slotAvailable(lvl) + (
    getMagicInitiateSpellCastInfo({ spell: selectedSpell, character: caster, castLevel: lvl }).canUse ? 1 : 0
  )

  const cantripList = spells.filter(spell => isCantripSpell(spell, cantrips))
  const spellList   = spells.filter(s => s.level > 0 && !isCantripSpell(s, cantrips))
  const shownSpells = level === 0 ? cantripList : spellList.filter(s => s.level <= level)

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
    available: selectedAvailable,
    selectedTarget,
    playerId,
    combat,
    aoeHover,
  })
  const canCast = !castDisabledReason
  const selectedTargetEntity = selectedTarget ? combat?.entities?.[selectedTarget] : null
  const selectedTargetBardic = getBardicInspiration(selectedTargetEntity)
  const showBardicSpellSave = Boolean(selectedSpell?.save && selectedTargetBardic)
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
  const castPlanId = 'spell-modal-cast-plan'

  return (
    <div className="spell-modal-backdrop" onClick={onClose}>
      <section
        onClick={e => e.stopPropagation()}
        className="panel spell-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="spell-modal-title"
        aria-describedby={castPlanId}
      >
        <div className="spell-modal-head">
          <h2 id="spell-modal-title" className="spell-modal-title">
            <SpellIcon size={14} color="#8a5af6" className="spell-modal-title-icon" />
            选择法术
          </h2>
          <button
            type="button"
            className="spell-modal-close"
            aria-label="关闭施法面板"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <SpellModalTabs
          level={level}
          setLevel={setLevel}
          setSelectedSpell={setSelectedSpell}
          cantripCount={cantripList.length}
          spellList={spellList}
          available={tabAvailable}
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

        <SpellCastPlan id={castPlanId} plan={castPlan} onResetAoeCenter={onResetAoeCenter} />

        {showBardicSpellSave && (
          <div className="spell-modal-bardic-row" aria-label="Bardic spell save">
            <button
              type="button"
              className="spell-modal-bardic-toggle"
              aria-pressed={useBardicSpellSave}
              onClick={onToggleBardicSpellSave}
              data-active={useBardicSpellSave ? 'true' : 'false'}
            >
              Bardic {useBardicSpellSave ? 'ON' : 'OFF'} · {selectedTargetBardic.die}
            </button>
          </div>
        )}

        <SpellModalActions
          canCast={canCast}
          disabledReason={castDisabledReason}
          selectedSpell={selectedSpell}
          level={level}
          onCast={onCast}
          onClose={onClose}
        />
      </section>
    </div>
  )
}
