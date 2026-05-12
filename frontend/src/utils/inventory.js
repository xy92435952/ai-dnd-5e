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
