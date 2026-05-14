export function getInventoryItemLabel(item) {
  if (!item) return ''
  if (typeof item === 'string') return item
  return item.zh || item.label || item.name || String(item)
}

export function normalizeInventoryItem(item, category, index = 0) {
  const raw = typeof item === 'string' ? { name: item } : { ...(item || {}) }
  const name = raw.name || raw.zh || `${category}-${index}`
  return {
    ...raw,
    key: `${category}-${name}-${index}`,
    name,
    label: getInventoryItemLabel(raw),
    category,
    index,
    equipped: Boolean(raw.equipped),
    consumable: Boolean(raw.consumable),
  }
}

export function isConsumableInventoryItem(item) {
  return Boolean(item?.consumable)
}

const DIRECT_USE_EFFECTS = new Set(['heal', 'antitoxin', 'fire_resistance', 'stabilize'])
const ITEM_USE_RULES = {
  'Healing Potion': { effect: 'heal' },
  'Greater Healing Potion': { effect: 'heal' },
  Antitoxin: { effect: 'antitoxin' },
  'Potion of Fire Resistance': { effect: 'fire_resistance' },
  "Healer's Kit": { effect: 'stabilize', requiresTarget: true, actionLabel: '用于' },
}

function resolveUseEffect(item) {
  return item?.effect || ITEM_USE_RULES[item?.name]?.effect || ''
}

export function getInventoryUseProfile(item) {
  const effect = resolveUseEffect(item)
  const rule = ITEM_USE_RULES[item?.name] || {}
  const usable = isConsumableInventoryItem(item) && DIRECT_USE_EFFECTS.has(effect)
  const requiresTarget = usable && Boolean(rule.requiresTarget || effect === 'stabilize')
  return {
    usable,
    requiresTarget,
    effect: usable ? effect : '',
    actionLabel: requiresTarget ? '用于' : (rule.actionLabel || '使用'),
  }
}

export function getInventoryUseSuccessText(item, payload = {}) {
  const label = getInventoryItemLabel(item)
  if (payload.effect === 'stabilize') {
    return `已用 ${label} 稳定 ${payload.target_name || '目标'}`
  }
  if (payload.heal_amount) {
    return `${label} 恢复 ${payload.heal_amount} HP`
  }
  return `已使用 ${label}`
}

export function isUsableInventoryItem(item) {
  return getInventoryUseProfile(item).usable
}

export function requiresUseTarget(item) {
  return getInventoryUseProfile(item).requiresTarget
}

export function canSellInventoryItem(item) {
  if (!item) return false
  return !item.equipped
}

export function hasAmmunition(item) {
  return item?.category === 'weapon' && item.ammo != null
}

export function mergeAmmoUpdate(equipment = {}, update = {}) {
  const weaponName = update.weapon || update.weapon_name
  if (!weaponName) return equipment
  return {
    ...equipment,
    weapons: (equipment.weapons || []).map(weapon => (
      weapon?.name === weaponName ? { ...weapon, ammo: update.ammo } : weapon
    )),
  }
}

export function stackInventoryItems(items = []) {
  const byName = new Map()
  for (const item of items) {
    const key = `${item.category}:${item.name}`
    const existing = byName.get(key)
    if (existing) {
      existing.quantity += 1
      existing.indexes.push(item.index)
      continue
    }
    byName.set(key, {
      ...item,
      quantity: 1,
      indexes: [item.index],
    })
  }
  return Array.from(byName.values())
}

function mapShopCategory(items = {}, category) {
  return Object.entries(items)
    .map(([name, data]) => normalizeInventoryItem({ name, ...data, category }, category, 0))
    .sort((a, b) => {
      const costDiff = (a.cost || 0) - (b.cost || 0)
      if (costDiff !== 0) return costDiff
      return a.label.localeCompare(b.label)
    })
}

export function categorizeShopInventory(shop = {}) {
  return {
    weapons: mapShopCategory(shop.weapons, 'weapon'),
    armor: mapShopCategory(shop.armor, 'armor'),
    gear: mapShopCategory(shop.gear, 'gear'),
  }
}
