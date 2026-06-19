import { useMemo, useState } from 'react'
import { charactersApi } from '../../api/client'
import {
  getInventoryItemLabel,
  getInventoryUseProfile,
  getInventoryUseSuccessText,
  isUsableInventoryItem,
  mergeConsumableUseResult,
  normalizeInventoryItem,
  stackInventoryItems,
} from '../../utils/inventory'

export default function CombatQuickInventory({
  session,
  turnState,
  isPlayerTurn = true,
  disabled = false,
  onSessionChange,
  onTurnStateChange,
  onError,
}) {
  const [busyName, setBusyName] = useState('')
  const [message, setMessage] = useState('')
  const player = session?.player
  const useTargets = useMemo(() => {
    if (!player?.id) return []
    const seen = new Set([player.id])
    return [
      { id: player.id, name: player.name || '自己' },
      ...(session?.companions || []).filter(member => {
        if (!member?.id || seen.has(member.id)) return false
        seen.add(member.id)
        return true
      }).map(member => ({ id: member.id, name: member.name })),
    ]
  }, [player?.id, player?.name, session?.companions])
  const consumables = useMemo(() => {
    const gear = player?.equipment?.gear || []
    return stackInventoryItems(
      gear
        .map((item, index) => normalizeInventoryItem(item, 'gear', index))
        .filter(isUsableInventoryItem),
    )
  }, [player?.equipment])

  if (!player?.id) return null
  if (consumables.length === 0 && !message) return null

  const actionUsed = Boolean(turnState?.action_used)
  const waitingTurn = !isPlayerTurn
  const busy = Boolean(busyName)
  const disabledReason = disabled
    ? '正在结算或同步战斗'
    : actionUsed
      ? '本回合动作已使用'
      : waitingTurn
        ? '等待你的回合'
        : ''
  const statusReason = busy ? '正在使用物品' : disabledReason
  const controlsDisabled = disabled || actionUsed || waitingTurn || busy
  const formatQuickLabel = (item) => {
    const label = getInventoryItemLabel(item)
    if (item.uses != null) return `${label} (${item.uses})`
    return `${label}${item.quantity > 1 ? ` x${item.quantity}` : ''}`
  }

  const handleUseConsumable = async (item, targetCharacterId = null) => {
    if (controlsDisabled) return
    setBusyName(item.name)
    setMessage('')
    try {
      const payload = await charactersApi.useItem(player.id, item.name, {
        session_id: session?.session_id,
        use_in_combat: true,
        ...(targetCharacterId ? { target_character_id: targetCharacterId } : {}),
      })
      onSessionChange?.(mergeConsumableUseResult(session, payload))
      if (payload.turn_state) onTurnStateChange?.(payload.turn_state)
      setMessage(getInventoryUseSuccessText(item, payload))
    } catch (e) {
      onError?.(e.message || '使用物品失败')
    } finally {
      setBusyName('')
    }
  }

  return (
    <section
      className="combat-quick-inventory"
      aria-label="战斗快捷物品"
      aria-busy={busy ? 'true' : 'false'}
    >
      <div className="combat-quick-inventory-title">
        快捷物品
      </div>
      {consumables.length > 0 && (
        <div className="combat-quick-inventory-list" role="list" aria-label="可用快捷物品">
          {consumables.slice(0, 4).map(item => {
            const label = getInventoryItemLabel(item)
            const quickLabel = formatQuickLabel(item)
            const useProfile = getInventoryUseProfile(item)
            if (useProfile.requiresTarget) {
              return (
                <div
                  key={item.key}
                  className="combat-quick-inventory-item"
                  role="listitem"
                  aria-label={`快捷物品 ${quickLabel}`}
                >
                  <select
                    className="combat-quick-inventory-select"
                    aria-label={`用于 ${label}`}
                    disabled={controlsDisabled}
                    title={statusReason || `用于 ${label}`}
                    defaultValue=""
                    onChange={(event) => {
                      const targetId = event.target.value
                      event.target.value = ''
                      if (targetId) handleUseConsumable(item, targetId)
                    }}
                  >
                    <option value="">{quickLabel}</option>
                    {useTargets.map(target => (
                      <option key={target.id} value={target.id}>{target.name}</option>
                    ))}
                  </select>
                </div>
              )
            }
            return (
              <div
                key={item.key}
                className="combat-quick-inventory-item"
                role="listitem"
                aria-label={`快捷物品 ${quickLabel}`}
              >
                <button
                  type="button"
                  className="btn-ghost combat-quick-inventory-action"
                  disabled={controlsDisabled}
                  onClick={() => handleUseConsumable(item)}
                  aria-label={`使用 ${label}`}
                  title={statusReason || `使用 ${label}`}
                >
                  {quickLabel}
                </button>
              </div>
            )
          })}
        </div>
      )}
      {(statusReason || message) && (
        <div className="combat-quick-inventory-status" role="status" aria-live="polite">
          {statusReason && consumables.length > 0 && (
            <div className="combat-quick-inventory-hint">{statusReason}</div>
          )}
          {message && <div className="combat-quick-inventory-message">{message}</div>}
        </div>
      )}
    </section>
  )
}
