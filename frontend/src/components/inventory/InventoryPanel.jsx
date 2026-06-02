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
    charactersApi.getShopInventory(character?.id)
      .then(setShopInventory)
      .catch(e => onError?.(e.message))
  }, [character?.id, onError, shopInventory, shopOpen])

  useEffect(() => {
    setShopInventory(null)
  }, [character?.id])

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
    <div className="inventory-section">
      <InventoryHeading icon={icon} label={CATEGORY_LABEL[items[0].category]} />
      <div className="inventory-item-list">
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
    <div className="panel inventory-panel">
      <div className="inventory-panel-header">
        <SectionTitle compact>装备与背包</SectionTitle>
        <button
          type="button"
          className={`${shopOpen ? 'btn-gold' : 'btn-ghost'} inventory-shop-toggle`}
          onClick={() => setShopOpen(v => !v)}
        >
          {shopOpen ? '收起商店' : '打开商店'}
        </button>
      </div>

      <div className="inventory-gold-strip">
        <span style={{ fontSize: 16 }}>&#x1F4B0;</span>
        <span style={{ color: 'var(--gold)', fontSize: 16, fontWeight: 700 }}>{equipment.gold ?? 0}</span>
        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>gp</span>
        {message && <span className="inventory-message">{message}</span>}
      </div>

      {renderEquippable(sections.weapons, <SwordIcon size={11} color="var(--red-light)" />)}
      {renderEquippable(sections.armor, <ShieldIcon size={11} color="var(--blue-light)" />)}
      {renderEquippable(sections.shield, <DefendIcon size={11} color="var(--blue-light)" />)}

      {sections.gear.length > 0 && (
        <div className="inventory-section">
          <InventoryHeading label="杂物与消耗品" />
          <div className="inventory-item-list">
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
        <p className="inventory-empty">
          暂无装备数据
        </p>
      )}

      {shopOpen && (
        <ShopPanel
          shop={shop}
          tab={shopTab}
          onTab={setShopTab}
          pricing={shopInventory?.pricing}
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
    <p className="inventory-heading">
      {icon && <span className="inventory-heading-icon">{icon}</span>}
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
    <div className="inventory-row" style={{
      background: item.equipped ? 'rgba(201,168,76,0.08)' : 'rgba(10,6,2,0.18)',
      border: `1px solid ${item.equipped ? 'var(--gold-dim)' : 'var(--wood)'}`,
    }}>
      <div className="inventory-row-body">
        <div className="inventory-row-title">
          <span className="inventory-item-label">{item.label}</span>
          {item.equipped && <span className="tag tag-gold" style={{ fontSize: 9 }}>已装备</span>}
          {item.consumable && <span className="tag tag-info" style={{ fontSize: 9 }}>消耗品</span>}
          {item.quantity > 1 && <span className="tag" style={{ fontSize: 9 }}>x{item.quantity}</span>}
        </div>
        <div className="inventory-item-meta">
          {item.damage && <span style={{ color: tone }}>{item.damage}</span>}
          {item.ac != null && <span style={{ color: tone }}>AC {item.ac}</span>}
          {item.ammo != null && <span>弹药 {item.ammo}</span>}
          {item.uses != null && <span>剩余 {item.uses} 次</span>}
          {item.cost != null && <span>{item.cost} gp</span>}
          {item.description && <span>{item.description}</span>}
        </div>
      </div>
      <div className="inventory-row-actions">
        {onAmmo && (
          <span className="inventory-ammo-actions">
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
            className="inventory-row-select"
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
            className="inventory-row-select"
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

function ShopPanel({ shop, tab, onTab, pricing, gold, busyKey, onBuy }) {
  const tabItems = [
    ['gear', '消耗品/工具'],
    ['weapons', '武器'],
    ['armor', '护甲'],
  ]
  const items = shop[tab] || []
  const hasDynamicPricing = pricing && pricing.profile && pricing.profile !== 'standard'
  return (
    <div className="inventory-shop-panel">
      {pricing && (
        <div
          aria-label="Shop pricing"
          className={`inventory-shop-pricing ${hasDynamicPricing ? 'dynamic' : ''}`}
        >
          <span>{pricing.label || '标准价格'}</span>
          <span>买入 x{pricing.buy_multiplier ?? 1}</span>
          <span>卖出 {Math.round((pricing.sell_rate ?? 0.5) * 100)}%</span>
        </div>
      )}
      <div className="inventory-shop-tabs">
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
      <div className="inventory-shop-grid">
        {items.map(item => {
          const affordable = (gold || 0) >= (item.cost || 0)
          return (
            <div key={`${item.category}-${item.name}`} className="inventory-shop-card">
              <div className="inventory-shop-card-title">{item.label}</div>
              <div className="inventory-shop-card-desc">
                {item.description || item.damage || (item.ac != null ? `AC ${item.ac}` : CATEGORY_LABEL[item.category])}
              </div>
              <div className="inventory-shop-card-footer">
                <span className="inventory-shop-price">
                  <span style={{ color: affordable ? 'var(--gold)' : 'var(--red-light)', fontSize: 11 }}>{item.cost || 0} gp</span>
                  {item.base_cost != null && item.base_cost !== item.cost && (
                    <span style={{ color: 'var(--text-dim)', fontSize: 9 }}>原价 {item.base_cost} gp</span>
                  )}
                </span>
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
