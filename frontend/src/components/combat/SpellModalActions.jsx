import React from 'react'
import { SpellIcon } from '../Icons'

export default function SpellModalActions({ canCast, disabledReason = '', selectedSpell, level, onCast, onClose }) {
  const castLabel = selectedSpell ? `施放【${selectedSpell.name}】` : '施放'
  const statusText = canCast ? (selectedSpell ? `准备施放 ${selectedSpell.name}` : '请选择法术') : disabledReason

  return (
    <div className="spell-modal-actions" role="group" aria-label="施法操作">
      <div className="spell-modal-action-row">
        <button
          type="button"
          className="spell-modal-cast btn-fantasy"
          data-ready={canCast ? 'true' : 'false'}
          disabled={!canCast}
          title={canCast ? '施放所选法术' : disabledReason}
          onClick={() => selectedSpell && onCast(selectedSpell, level || 1)}
        >
          <SpellIcon size={14} className="spell-modal-cast-icon" />
          {castLabel}
        </button>
        <button
          type="button"
          className="spell-modal-cancel btn-fantasy"
          onClick={onClose}
        >
          取消
        </button>
      </div>
      {statusText && (
        <div className="spell-modal-action-status" role="status">
          {statusText}
        </div>
      )}
    </div>
  )
}
