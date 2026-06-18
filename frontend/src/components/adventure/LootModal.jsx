import { useEffect, useMemo, useState } from 'react'
import Overlay from './Overlay'
import { ScrollIcon } from '../Icons'
import { gameApi } from '../../api/client'

function lootItems(pool) {
  return Array.isArray(pool?.items)
    ? pool.items.filter(item => {
        if (!item) return false
        if (item.status === 'claimed') return true
        if (item.status !== 'available') return false
        const source = String(item.source || '')
        if (!source) return true
        if (item.discovered || item.revealed || item.public) return true
        return !['key_rewards', 'magic_items'].includes(source)
      })
    : []
}

function lootMeta(item) {
  const parts = []
  if (item?.category) parts.push(item.category)
  if (item?.rarity) parts.push(item.rarity)
  if (item?.amount != null && item.category === 'gold') parts.push(`${item.amount} gp`)
  if (item?.cost != null) parts.push(`${item.cost} gp value`)
  const winner = Array.isArray(item?.roll_allocations)
    ? item.roll_allocations.find(allocation => allocation?.winner)
    : null
  if (winner) parts.push(`${winner.character_name || 'Winner'} d20 ${winner.d20}`)
  return parts
}

function statusLabel(item) {
  if (item?.status !== 'claimed') return 'Available'
  if (item?.claim_mode === 'split_party') return 'Split with party'
  if (item?.claim_mode === 'party_stash') return 'Shared by party'
  if (item?.claim_mode === 'roll_party') {
    return item?.claimed_by_name ? `Rolled to ${item.claimed_by_name}` : 'Rolled'
  }
  return item?.claimed_by_name ? `Claimed by ${item.claimed_by_name}` : 'Claimed'
}

function claimHint(item) {
  if (item?.status === 'claimed') return 'Distribution locked after resolution.'
  if (item?.category === 'gold') return 'Claim for yourself or split with the party.'
  return 'Claim for yourself, share to the party stash, or roll for a winner.'
}

function LootRow({ item, disabled, disabledReason = '', claiming, onClaim }) {
  const claimed = item.status === 'claimed'
  const meta = lootMeta(item)
  const canSplit = item.category === 'gold' && Number(item.amount || 0) > 0
  const canDistribute = item.category !== 'gold'
  const actionTitle = disabled ? disabledReason : undefined
  const lootName = item.name || 'loot'
  const categoryClass = item.category ? `loot-row--${item.category}` : 'loot-row--uncategorized'

  return (
    <article className={`loot-row ${categoryClass} ${claimed ? 'claimed' : ''}`}>
      <div className="loot-row-main">
        <div className="loot-row-title">
          <strong>{item.name || 'Unknown reward'}</strong>
          <span>{statusLabel(item)}</span>
        </div>
        {item.description && <p>{item.description}</p>}
        {meta.length > 0 && (
          <div className="loot-row-meta">
            {meta.map(part => <span key={part}>{part}</span>)}
          </div>
        )}
        <p className="loot-row-hint">{claimHint(item)}</p>
      </div>
      <div className="loot-row-actions" role="group" aria-label={`Loot actions for ${lootName}`}>
        <button
          className="btn-fantasy loot-claim-button"
          disabled={disabled || claimed || claiming}
          title={actionTitle}
          aria-label={`Claim ${lootName}`}
          onClick={() => onClaim(item, 'claim')}
        >
          {claiming ? 'Claiming...' : claimed ? 'Taken' : 'Claim'}
        </button>
        {canSplit && (
          <button
            className="btn-fantasy loot-claim-button"
            disabled={disabled || claimed || claiming}
            title={actionTitle}
            aria-label={`Split ${lootName}`}
            onClick={() => onClaim(item, 'split_party')}
          >
            {claiming ? 'Splitting...' : claimed ? 'Split' : 'Split'}
          </button>
        )}
        {canDistribute && (
          <>
            <button
              className="btn-fantasy loot-claim-button"
              disabled={disabled || claimed || claiming}
              title={actionTitle}
              aria-label={`Share ${lootName}`}
              onClick={() => onClaim(item, 'party_stash')}
            >
              {claiming ? 'Sharing...' : claimed ? 'Shared' : 'Share'}
            </button>
            <button
              className="btn-fantasy loot-claim-button"
              disabled={disabled || claimed || claiming}
              title={actionTitle}
              aria-label={`Roll ${lootName}`}
              onClick={() => onClaim(item, 'roll_party')}
            >
              {claiming ? 'Rolling...' : claimed ? 'Rolled' : 'Roll'}
            </button>
          </>
        )}
      </div>
    </article>
  )
}

export default function LootModal({
  sessionId,
  player,
  disabled = false,
  disabledReason = '',
  onClaimed,
  onClose,
}) {
  const [lootPool, setLootPool] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [claimingId, setClaimingId] = useState('')

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError('')
    gameApi.getLoot(sessionId)
      .then(data => { if (alive) setLootPool(data || { items: [] }) })
      .catch(e => { if (alive) setError(e.message || 'Failed to load loot') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [sessionId])

  const items = useMemo(() => lootItems(lootPool), [lootPool])
  const availableCount = items.filter(item => item.status !== 'claimed').length
  const claimedCount = items.length - availableCount
  const blockReason = disabledReason || '房间正在重新同步，请恢复连接后再分配战利品。'

  const handleClaim = async (item, claimMode = 'claim') => {
    if (disabled) {
      setError(blockReason)
      return
    }
    if (!player?.id) {
      setError('No player character is available.')
      return
    }
    setClaimingId(item.id)
    setError('')
    try {
      const result = claimMode === 'claim'
        ? await gameApi.claimLoot(sessionId, player.id, item.id)
        : await gameApi.claimLoot(sessionId, player.id, item.id, claimMode)
      setLootPool(result?.loot_pool || { items: [] })
      await onClaimed?.(result)
    } catch (e) {
      setError(e.message || 'Failed to claim loot')
    } finally {
      setClaimingId('')
    }
  }

  return (
    <Overlay onClose={onClose}>
      <div className="loot-modal-head">
        <h3>
          <ScrollIcon size={18} color="var(--amber)" /> Loot
        </h3>
        <button onClick={onClose} aria-label="Close loot">x</button>
      </div>

      <div className="loot-summary" aria-label="Loot summary">
        <span><b>{availableCount}</b> available</span>
        <span><b>{claimedCount}</b> claimed</span>
      </div>

      {error && <p className="checkpoint-error">{error}</p>}

      {disabled && (
        <div role="status" className="multiplayer-sync-guard" style={{ margin: '0 0 10px' }}>
          <strong>同步暂停</strong>
          <span>{blockReason}</span>
        </div>
      )}

      <div className="loot-list" aria-label="Session loot" aria-live="polite">
        {loading ? (
          <p className="checkpoint-empty">Loading loot...</p>
        ) : items.length === 0 ? (
          <p className="checkpoint-empty">No loot discovered yet.</p>
        ) : (
          items.map(item => (
            <LootRow
              key={item.id || item.name}
              item={item}
              disabled={disabled || !player?.id}
              disabledReason={disabled ? blockReason : 'No player character is available.'}
              claiming={claimingId === item.id}
              onClaim={handleClaim}
            />
          ))
        )}
      </div>
    </Overlay>
  )
}
