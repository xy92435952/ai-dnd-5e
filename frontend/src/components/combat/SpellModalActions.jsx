import React from 'react'
import { SpellIcon } from '../Icons'

export default function SpellModalActions({ canCast, disabledReason = '', selectedSpell, level, onCast, onClose }) {
  return (
    <div className="mt-3">
      <div className="flex gap-2">
        <button className="flex-1 btn-fantasy py-2 text-sm"
          style={{ borderColor: canCast ? '#8a5af6' : 'var(--wood)', opacity: canCast ? 1 : 0.4 }}
          disabled={!canCast}
          title={canCast ? '施放所选法术' : disabledReason}
          onClick={() => selectedSpell && onCast(selectedSpell, level || 1)}>
          <SpellIcon size={14} color="#8a5af6" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
          施放{selectedSpell ? `【${selectedSpell.name}】` : ''}
        </button>
        <button className="btn-fantasy px-4 py-2 text-sm" onClick={onClose}>取消</button>
      </div>
      {!canCast && disabledReason && (
        <div style={{ color: 'var(--text-dim)', fontSize: 11, marginTop: 6 }}>
          {disabledReason}
        </div>
      )}
    </div>
  )
}
