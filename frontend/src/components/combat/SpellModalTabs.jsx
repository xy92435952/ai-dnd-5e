import React from 'react'

export default function SpellModalTabs({
  level,
  setLevel,
  setSelectedSpell,
  cantripCount,
  spellList,
  available,
}) {
  return (
    <div className="spell-modal-tabs" role="tablist" aria-label="施法环级选择">
      <button
        type="button"
        onClick={() => { setLevel(0); setSelectedSpell(null) }}
        className={`spell-modal-tab spell-modal-tab-cantrip ${level === 0 ? 'active' : ''} ${cantripCount > 0 ? '' : 'empty'}`}
        role="tab"
        aria-selected={level === 0}
        aria-label={`戏法，可用 ${cantripCount}`}
      >
        戏法 ({cantripCount})
      </button>
      {[1,2,3,4,5].map(lvl => {
        const cnt = available(lvl)
        const hasSpells = spellList.some(s => s.level <= lvl)
        const disabledReason = cnt <= 0 ? `没有可用的 ${lvl} 环法术位` : !hasSpells ? `没有可用的 ${lvl} 环法术` : ''
        const canOpen = cnt > 0 && hasSpells
        return (
          <button
            key={lvl}
            type="button"
            onClick={() => { setLevel(lvl); setSelectedSpell(null) }}
            disabled={!canOpen}
            title={disabledReason || `${lvl} 环法术`}
            className={`spell-modal-tab ${level === lvl ? 'active' : ''} ${canOpen ? '' : 'disabled'}`}
            role="tab"
            aria-selected={level === lvl}
            aria-label={`${lvl} 环法术，可用 ${cnt}`}
          >
            {lvl}环 ({cnt})
          </button>
        )
      })}
    </div>
  )
}
