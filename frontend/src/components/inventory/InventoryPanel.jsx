import { useEffect, useMemo, useState } from 'react'
import { charactersApi } from '../../api/client'
import {
  canSellInventoryItem,
  categorizeShopInventory,
  getInventoryUseProfile,
  getInventoryUseSuccessText,
  hasAmmunition,
  mergeAmmoUpdate,
  normalizeInventoryItem,
  stackInventoryItems,
} from '../../utils/inventory'
import {
  DefendIcon,
  ShieldIcon,
  SwordIcon,
} from '../Icons'

const CATEGORY_LABEL = {
  weapon: '武器',
  armor: '护甲',
  shield: '盾牌',
  gear: '杂物',
}

function toEquipCategory(category) {
  if (category === 'weapon') return 'weapon'
  if (category === 'armor') return 'armor'
  return category
}

function toSellCategory(category) {
  if (category === 'shield') return 'armor'
  return category
}

function toTransferCategory(category) {
  return category
}

function mergeConditions(current = [], payload = {}) {
  if (Array.isArray(payload.conditions)) return payload.conditions
  if (payload.removed_condition) return current.filter(c => c !== payload.removed_condition)
  if (payload.added_condition && !current.includes(payload.added_condition)) {
    return [...current, payload.added_condition]
  }
  return current
}

function mergeCharacterInventory(char, payload) {
  const equipment = payload.equipment
    || payload.source_equipment
    || (payload.weapon && payload.ammo != null
      ? mergeAmmoUpdate(char.equipment || {}, payload)
      : char.equipment)
  return {
    ...char,
    equipment,
    derived: payload.derived || char.derived,
    hp_current: payload.hp_after ?? char.hp_current,
    conditions: mergeConditions(char.conditions || [], payload),
    death_saves: payload.target_character_id === char.id && payload.death_saves
      ? payload.death_saves
      : char.death_saves,
  }
}

export default function InventoryPanel({ character, partyMembers = [], onCharacterChange, onError }) {
  const [busyKey, setBusyKey] = useState('')
  const [message, setMessage] = useState('')
  const [shopOpen, setShopOpen] = useState(false)
  const [shopInventory, setShopInventory] = useState(null)
  const [shopTab, setShopTab] = useState('gear')

  const equipment = character?.equipment || {}
  const sections = useMemo(() => ({
    weapons: (equipment.weapons || []).map((item, index) => normalizeInventoryItem(item, 'weapon', index)),
    armor: (equipment.armor || []).map((item, index) => normalizeInventoryItem(item, 'armor', index)),
    shield: equipment.shield ? [normalizeInventoryItem(equipment.shield, 'shield', 0)] : [],
    gear: stackInventoryItems((equipment.gear || []).map((item, index) => normalizeInventoryItem(item, 'gear', index))),
  }), [equipment])

  const shop = useMemo(() => categorizeShopInventory(shopInventory || {}), [shopInventory])
  const useTargets = useMemo(() => {
    if (!character?.id) return []
    const seen = new Set([character.id])
    return [
      { id: character.id, name: character.name || '自己' },
      ...partyMembers.filter(member => {
        if (!member?.id || seen.has(member.id)) return false
        seen.add(member.id)
        return true
      }),
    ]
  }, [character?.id, character?.name, partyMembers])

  useEffect(() => {
    if (!shopOpen || shopInventory) return
    charactersApi.getShopInventory()
      .then(setShopInventory)
      .catch(e => onError?.(e.message))
  }, [onError, shopInventory, shopOpen])

  const applyResult = (payload) => {
    onCharacterChange?.(mergeCharacterInventory(character, payload))
  }

  const runAction = async (key, action, successText) => {
    if (!character || busyKey) return
    setBusyKey(key)
    setMessage('')
    try {
      const payload = await action()
      applyResult(payload)
      setMessage(successText(payload))
    } catch (e) {
      onError?.(e.message)
    } finally {
      setBusyKey('')
    }
  }

  const toggleEquip = (item) => runAction(
    `${item.key}-equip`,
    () => charactersApi.equipItem(character.id, item.name, toEquipCategory(item.category), !item.equipped),
    () => `${item.equipped ? '已卸下' : '已装备'} ${item.label}`,
  )

  const useItem = (item, targetCharacterId = null) => runAction(
    `${item.key}-use${targetCharacterId ? `-${targetCharacterId}` : ''}`,
    () => targetCharacterId
      ? charactersApi.useItem(character.id, item.name, { target_character_id: targetCharacterId })
      : charactersApi.useItem(character.id, item.name),
    (payload) => getInventoryUseSuccessText(item, payload),
  )

  const sellItem = (item) => runAction(
    `${item.key}-sell`,
    () => charactersApi.sellItem(character.id, item.name, toSellCategory(item.category), item.indexes?.[0] ?? item.index),
    (payload) => `出售 ${item.label}，获得 ${payload.sell_price || 0} gp`,
  )

  const transferItem = (item, targetCharacterId) => runAction(
    `${item.key}-transfer-${targetCharacterId}`,
    () => charactersApi.transferItem(
      character.id,
      targetCharacterId,
      item.name,
      toTransferCategory(item.category),
      item.indexes?.[0] ?? item.index,
    ),
    (payload) => `已将 ${item.label} 交给 ${partyMembers.find(m => m.id === payload.target_character_id)?.name || '队友'}`,
  )

  const buyItem = (item) => runAction(
    `shop-${item.category}-${item.name}`,
    () => charactersApi.buyItem(character.id, item.name, item.category, 1),
    () => `购买 ${item.label}`,
  )

  const adjustAmmo = (item, change) => runAction(
    `${item.key}-ammo-${change}`,
    () => charactersApi.updateAmmo(character.id, item.name, change),
    (payload) => `${item.label} 弹药 ${payload.ammo}`,
  )

  const renderEquippable = (items, icon) => items.length > 0 && (
    <div style={{ marginBottom: 12 }}>
      <InventoryHeading icon={icon} label={CATEGORY_LABEL[items[0].category]} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map(item => (
          <InventoryRow
            key={item.key}
            item={item}
            busy={busyKey === `${item.key}-equip` || busyKey === `${item.key}-sell`}
            onPrimary={() => toggleEquip(item)}
            primaryLabel={item.equipped ? '卸下' : '装备'}
            onSell={canSellInventoryItem(item) ? () => sellItem(item) : null}
            onAmmo={hasAmmunition(item) ? (change) => adjustAmmo(item, change) : null}
            transferTargets={partyMembers}
            onTransfer={canSellInventoryItem(item) ? (targetId) => transferItem(item, targetId) : null}
          />
        ))}
      </div>
    </div>
  )

  return (
    <div className="panel" style={{ padding: 16, marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <SectionTitle compact>装备与背包</SectionTitle>
        <button
          type="button"
          className={shopOpen ? 'btn-gold' : 'btn-ghost'}
          onClick={() => setShopOpen(v => !v)}
          style={{ fontSize: 11, padding: '6px 12px', flexShrink: 0 }}
        >
          {shopOpen ? '收起商店' : '打开商店'}
        </button>
      </div>

      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
        padding: '8px 12px', background: 'rgba(201,168,76,0.08)',
        borderRadius: 6, border: '1px solid var(--gold-dim)',
      }}>
        <span style={{ fontSize: 16 }}>&#x1F4B0;</span>
        <span style={{ color: 'var(--gold)', fontSize: 16, fontWeight: 700 }}>{equipment.gold ?? 0}</span>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>gp</span>
        {message && <span style={{ marginLeft: 'auto', color: 'var(--green-light)', fontSize: 11 }}>{message}</span>}
      </div>

      {renderEquippable(sections.weapons, <SwordIcon size={11} color="var(--red-light)" />)}
      {renderEquippable(sections.armor, <ShieldIcon size={11} color="var(--blue-light)" />)}
      {renderEquippable(sections.shield, <DefendIcon size={11} color="var(--blue-light)" />)}

      {sections.gear.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <InventoryHeading label="杂物与消耗品" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sections.gear.map(item => (
              <InventoryGearRow
                key={item.key}
                item={item}
                busyKey={busyKey}
                useTargets={useTargets}
                transferTargets={partyMembers}
                onUse={useItem}
                onSell={sellItem}
                onTransfer={transferItem}
              />
            ))}
          </div>
        </div>
      )}

      {!(sections.weapons.length || sections.armor.length || sections.shield.length || sections.gear.length) && (
        <p style={{ color: 'var(--text-dim)', fontSize: 12, textAlign: 'center', padding: 16 }}>
          暂无装备数据
        </p>
      )}

      {shopOpen && (
        <ShopPanel
          shop={shop}
          tab={shopTab}
          onTab={setShopTab}
          gold={equipment.gold ?? 0}
          busyKey={busyKey}
          onBuy={buyItem}
        />
      )}
    </div>
  )
}

function InventoryHeading({ icon, label }) {
  return (
    <p style={{ color: 'var(--parchment-dark)', fontSize: 11, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {icon && <span style={{ display: 'inline-flex', verticalAlign: 'middle', marginRight: 4 }}>{icon}</span>}
      {label}
    </p>
  )
}

function InventoryGearRow({
  item,
  busyKey,
  useTargets,
  transferTargets,
  onUse,
  onSell,
  onTransfer,
}) {
  const useProfile = getInventoryUseProfile(item)
  return (
    <InventoryRow
      item={item}
      busy={busyKey.startsWith(`${item.key}-use`) || busyKey === `${item.key}-sell`}
      onPrimary={useProfile.usable && !useProfile.requiresTarget ? () => onUse(item) : null}
      primaryLabel={useProfile.actionLabel}
      useTargets={useProfile.usable && useProfile.requiresTarget ? useTargets : []}
      onUseTarget={useProfile.usable && useProfile.requiresTarget ? (targetId) => onUse(item, targetId) : null}
      onSell={canSellInventoryItem(item) ? () => onSell(item) : null}
      transferTargets={transferTargets}
      onTransfer={canSellInventoryItem(item) ? (targetId) => onTransfer(item, targetId) : null}
    />
  )
}

function InventoryRow({
  item,
  busy,
  onPrimary,
  primaryLabel,
  onSell,
  onAmmo,
  useTargets = [],
  onUseTarget,
  transferTargets = [],
  onTransfer,
}) {
  const tone = item.category === 'weapon' ? 'var(--red-light)' : item.category === 'gear' ? 'var(--parchment-dark)' : 'var(--blue-light)'
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 8,
      padding: '8px 10px', borderRadius: 6,
      background: item.equipped ? 'rgba(201,168,76,0.08)' : 'rgba(10,6,2,0.18)',
      border: `1px solid ${item.equipped ? 'var(--gold-dim)' : 'var(--wood)'}`,
    }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ color: 'var(--parchment)', fontSize: 12, fontWeight: 700 }}>{item.label}</span>
          {item.equipped && <span className="tag tag-gold" style={{ fontSize: 9 }}>已装备</span>}
          {item.consumable && <span className="tag tag-info" style={{ fontSize: 9 }}>消耗品</span>}
          {item.quantity > 1 && <span className="tag" style={{ fontSize: 9 }}>x{item.quantity}</span>}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 3, color: 'var(--text-dim)', fontSize: 10 }}>
          {item.damage && <span style={{ color: tone }}>{item.damage}</span>}
          {item.ac != null && <span style={{ color: tone }}>AC {item.ac}</span>}
          {item.ammo != null && <span>弹药 {item.ammo}</span>}
          {item.uses != null && <span>剩余 {item.uses} 次</span>}
          {item.cost != null && <span>{item.cost} gp</span>}
          {item.description && <span>{item.description}</span>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {onAmmo && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            <button type="button" className="btn-ghost" disabled={busy || (item.ammo || 0) <= 0} onClick={() => onAmmo(-1)} style={{ fontSize: 10, padding: '4px 7px' }}>
              -1
            </button>
            <button type="button" className="btn-ghost" disabled={busy} onClick={() => onAmmo(1)} style={{ fontSize: 10, padding: '4px 7px' }}>
              +1
            </button>
          </span>
        )}
        {onPrimary && (
          <button type="button" className="btn-ghost" disabled={busy} onClick={onPrimary} style={{ fontSize: 10, padding: '4px 8px' }}>
            {primaryLabel}
          </button>
        )}
        {onUseTarget && useTargets.length > 0 && (
          <select
            aria-label={`用于 ${item.label}`}
            disabled={busy}
            defaultValue=""
            onChange={(event) => {
              const targetId = event.target.value
              event.target.value = ''
              if (targetId) onUseTarget(targetId)
            }}
            style={{
              background: 'rgba(10,6,2,0.65)',
              border: '1px solid var(--wood-light)',
              color: 'var(--parchment)',
              borderRadius: 4,
              fontSize: 10,
              padding: '4px 6px',
              maxWidth: 92,
            }}
          >
            <option value="">用于</option>
            {useTargets.map(target => (
              <option key={target.id} value={target.id}>{target.name}</option>
            ))}
          </select>
        )}
        {onSell && (
          <button type="button" className="btn-ghost" disabled={busy} onClick={onSell} style={{ fontSize: 10, padding: '4px 8px' }}>
            出售
          </button>
        )}
        {onTransfer && transferTargets.length > 0 && (
          <select
            aria-label={`给予 ${item.label}`}
            disabled={busy}
            defaultValue=""
            onChange={(event) => {
              const targetId = event.target.value
              event.target.value = ''
              if (targetId) onTransfer(targetId)
            }}
            style={{
              background: 'rgba(10,6,2,0.65)',
              border: '1px solid var(--wood-light)',
              color: 'var(--parchment)',
              borderRadius: 4,
              fontSize: 10,
              padding: '4px 6px',
              maxWidth: 92,
            }}
          >
            <option value="">给予</option>
            {transferTargets.map(target => (
              <option key={target.id} value={target.id}>{target.name}</option>
            ))}
          </select>
        )}
      </div>
    </div>
  )
}

function ShopPanel({ shop, tab, onTab, gold, busyKey, onBuy }) {
  const tabItems = [
    ['gear', '消耗品/工具'],
    ['weapons', '武器'],
    ['armor', '护甲'],
  ]
  const items = shop[tab] || []
  return (
    <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--wood)' }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
        {tabItems.map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? 'btn-gold' : 'btn-ghost'}
            onClick={() => onTab(key)}
            style={{ fontSize: 10, padding: '5px 10px' }}
          >
            {label}
          </button>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: 8 }}>
        {items.map(item => {
          const affordable = (gold || 0) >= (item.cost || 0)
          return (
            <div key={`${item.category}-${item.name}`} style={{
              padding: 10, borderRadius: 6,
              border: '1px solid var(--wood)',
              background: 'rgba(10,6,2,0.22)',
            }}>
              <div style={{ color: 'var(--parchment)', fontSize: 12, fontWeight: 700 }}>{item.label}</div>
              <div style={{ color: 'var(--text-dim)', fontSize: 10, marginTop: 4, minHeight: 28 }}>
                {item.description || item.damage || (item.ac != null ? `AC ${item.ac}` : CATEGORY_LABEL[item.category])}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
                <span style={{ color: affordable ? 'var(--gold)' : 'var(--red-light)', fontSize: 11 }}>{item.cost || 0} gp</span>
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={!affordable || busyKey === `shop-${item.category}-${item.name}`}
                  onClick={() => onBuy(item)}
                  style={{ fontSize: 10, padding: '4px 8px' }}
                >
                  购买
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SectionTitle({ children, compact = false }) {
  return (
    <p style={{
      color: 'var(--gold)', fontSize: 12, fontWeight: 700,
      textTransform: 'uppercase', letterSpacing: '0.1em',
      margin: compact ? 0 : '0 0 10px', paddingBottom: compact ? 0 : 6,
      borderBottom: compact ? 'none' : '1px solid var(--wood)',
    }}>
      {children}
    </p>
  )
}
