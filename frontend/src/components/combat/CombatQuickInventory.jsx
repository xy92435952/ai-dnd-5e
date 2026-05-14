import { useMemo, useState } from 'react'
import { charactersApi } from '../../api/client'
import {
  getInventoryItemLabel,
  getInventoryUseProfile,
  getInventoryUseSuccessText,
  isUsableInventoryItem,
  normalizeInventoryItem,
  stackInventoryItems,
} from '../../utils/inventory'

function mergeConditions(current = [], payload = {}) {
  if (Array.isArray(payload.conditions)) return payload.conditions
  if (payload.removed_condition) return current.filter(c => c !== payload.removed_condition)
  if (payload.added_condition && !current.includes(payload.added_condition)) {
    return [...current, payload.added_condition]
  }
  return current
}

function mergeConsumableResult(session, payload) {
  if (!session?.player || !payload) return session
  const player = session.player
  const mergeTargetState = entity => (
    payload.target_character_id === entity?.id && payload.death_saves
      ? {
          ...entity,
          death_saves: payload.death_saves,
          hp_current: payload.target_hp_current ?? entity.hp_current,
        }
      : entity
  )
  return {
    ...session,
    player: mergeTargetState({
      ...player,
      hp_current: payload.hp_after ?? payload.hp_current ?? player.hp_current,
      equipment: payload.equipment || player.equipment,
      conditions: mergeConditions(player.conditions || [], payload),
      death_saves: payload.target_character_id === player.id && payload.death_saves
        ? payload.death_saves
        : player.death_saves,
    }),
    ...(Array.isArray(session.companions)
      ? { companions: session.companions.map(mergeTargetState) }
      : {}),
  }
}

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
  const disabledReason = actionUsed ? '本回合动作已使用' : waitingTurn ? '等待你的回合' : ''
  const formatQuickLabel = (item) => {
    const label = getInventoryItemLabel(item)
    if (item.uses != null) return `${label} (${item.uses})`
    return `${label}${item.quantity > 1 ? ` x${item.quantity}` : ''}`
  }

  const useConsumable = async (item, targetCharacterId = null) => {
    if (disabled || actionUsed || waitingTurn || busyName) return
    setBusyName(item.name)
    setMessage('')
    try {
      const payload = await charactersApi.useItem(player.id, item.name, {
        session_id: session?.session_id,
        use_in_combat: true,
        ...(targetCharacterId ? { target_character_id: targetCharacterId } : {}),
      })
      onSessionChange?.(mergeConsumableResult(session, payload))
      if (payload.turn_state) onTurnStateChange?.(payload.turn_state)
      setMessage(getInventoryUseSuccessText(item, payload))
    } catch (e) {
      onError?.(e.message || '使用物品失败')
    } finally {
      setBusyName('')
    }
  }

  return (
    <div style={{
      padding: '7px 8px',
      border: '1px solid rgba(201,168,76,.28)',
      background: 'rgba(10,6,2,.28)',
      display: 'grid',
      gap: 5,
    }}>
      <div style={{
        color: 'var(--gold-dim)',
        fontSize: 9,
        fontFamily: 'var(--font-mono)',
        letterSpacing: '.14em',
        textTransform: 'uppercase',
      }}>
        快捷物品
      </div>
      {consumables.length > 0 && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {consumables.slice(0, 4).map(item => {
            const label = getInventoryItemLabel(item)
            const quickLabel = formatQuickLabel(item)
            const useProfile = getInventoryUseProfile(item)
            if (useProfile.requiresTarget) {
              return (
                <select
                  key={item.key}
                  aria-label={`用于 ${label}`}
                  disabled={disabled || actionUsed || waitingTurn || Boolean(busyName)}
                  defaultValue=""
                  onChange={(event) => {
                    const targetId = event.target.value
                    event.target.value = ''
                    if (targetId) useConsumable(item, targetId)
                  }}
                  style={{
                    background: 'rgba(10,6,2,0.65)',
                    border: '1px solid var(--wood-light)',
                    color: 'var(--parchment)',
                    borderRadius: 4,
                    fontSize: 10,
                    padding: '4px 6px',
                    maxWidth: 100,
                  }}
                >
                  <option value="">{quickLabel}</option>
                  {useTargets.map(target => (
                    <option key={target.id} value={target.id}>{target.name}</option>
                  ))}
                </select>
              )
            }
            return (
              <button
                key={item.key}
                type="button"
                className="btn-ghost"
                disabled={disabled || actionUsed || waitingTurn || Boolean(busyName)}
                onClick={() => useConsumable(item)}
                aria-label={`使用 ${label}`}
                style={{ fontSize: 10, padding: '4px 7px' }}
              >
                {quickLabel}
              </button>
            )
          })}
        </div>
      )}
      {disabledReason && consumables.length > 0 && (
        <div style={{ color: 'var(--parchment-dark)', fontSize: 10 }}>{disabledReason}</div>
      )}
      {message && <div style={{ color: 'var(--green-light)', fontSize: 10 }}>{message}</div>}
    </div>
  )
}
