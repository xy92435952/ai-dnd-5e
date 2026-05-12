import { describe, expect, it } from 'vitest'
import {
  canSellInventoryItem,
  categorizeShopInventory,
  getInventoryItemLabel,
  hasAmmunition,
  isConsumableInventoryItem,
  mergeAmmoUpdate,
  normalizeInventoryItem,
  stackInventoryItems,
} from '../inventory'

describe('inventory utils', () => {
  it('normalizes string and object gear into stable display items', () => {
    expect(normalizeInventoryItem('Rope', 'gear', 2)).toMatchObject({
      key: 'gear-Rope-2',
      name: 'Rope',
      label: 'Rope',
      category: 'gear',
      index: 2,
      equipped: false,
      consumable: false,
    })

    expect(normalizeInventoryItem({
      name: 'Healing Potion',
      zh: '治疗药水',
      cost: 50,
      consumable: true,
      effect: 'heal',
    }, 'gear', 0)).toMatchObject({
      key: 'gear-Healing Potion-0',
      name: 'Healing Potion',
      label: '治疗药水',
      category: 'gear',
      index: 0,
      cost: 50,
      consumable: true,
      effect: 'heal',
    })
  })

  it('marks equipped weapons armor and shields as not sellable', () => {
    expect(canSellInventoryItem(normalizeInventoryItem({ name: 'Longsword', equipped: true }, 'weapon', 0))).toBe(false)
    expect(canSellInventoryItem(normalizeInventoryItem({ name: 'Leather', equipped: true }, 'armor', 0))).toBe(false)
    expect(canSellInventoryItem(normalizeInventoryItem({ name: 'Shield', equipped: true }, 'shield', 0))).toBe(false)
    expect(canSellInventoryItem(normalizeInventoryItem({ name: 'Rope', cost: 1 }, 'gear', 0))).toBe(true)
  })

  it('detects consumables and formats useful labels', () => {
    const potion = normalizeInventoryItem({ name: 'Healing Potion', zh: '治疗药水', consumable: true, description: '恢复2d4+2 HP' }, 'gear', 0)
    expect(isConsumableInventoryItem(potion)).toBe(true)
    expect(getInventoryItemLabel(potion)).toBe('治疗药水')
    expect(getInventoryItemLabel({ name: 'Longsword' })).toBe('Longsword')
  })

  it('categorizes shop inventory maps into sorted item arrays', () => {
    const shop = categorizeShopInventory({
      weapons: {
        Longsword: { zh: '长剑', cost: 15 },
      },
      armor: {
        Shield: { zh: '盾牌', cost: 10 },
      },
      gear: {
        'Healing Potion': { zh: '治疗药水', cost: 50, consumable: true },
      },
    })

    expect(shop.weapons).toEqual([
      expect.objectContaining({ name: 'Longsword', label: '长剑', category: 'weapon', cost: 15 }),
    ])
    expect(shop.armor).toEqual([
      expect.objectContaining({ name: 'Shield', label: '盾牌', category: 'armor', cost: 10 }),
    ])
    expect(shop.gear).toEqual([
      expect.objectContaining({ name: 'Healing Potion', label: '治疗药水', category: 'gear', consumable: true }),
    ])
  })

  it('detects ammunition weapons and merges ammo updates into equipment', () => {
    const bow = normalizeInventoryItem({ name: 'Longbow', zh: '长弓', ammo: 20 }, 'weapon', 0)
    const sword = normalizeInventoryItem({ name: 'Longsword', zh: '长剑' }, 'weapon', 1)
    expect(hasAmmunition(bow)).toBe(true)
    expect(hasAmmunition(sword)).toBe(false)

    const equipment = {
      weapons: [
        { name: 'Longbow', ammo: 20 },
        { name: 'Longsword' },
      ],
    }
    expect(mergeAmmoUpdate(equipment, { weapon: 'Longbow', ammo: 19 })).toEqual({
      weapons: [
        { name: 'Longbow', ammo: 19 },
        { name: 'Longsword' },
      ],
    })
  })

  it('stacks duplicate gear while preserving the first item index for actions', () => {
    const items = [
      normalizeInventoryItem({ name: 'Healing Potion', zh: '治疗药水', consumable: true }, 'gear', 0),
      normalizeInventoryItem({ name: 'Rope', zh: '绳索' }, 'gear', 1),
      normalizeInventoryItem({ name: 'Healing Potion', zh: '治疗药水', consumable: true }, 'gear', 2),
    ]

    expect(stackInventoryItems(items)).toEqual([
      expect.objectContaining({
        name: 'Healing Potion',
        label: '治疗药水',
        index: 0,
        quantity: 2,
        indexes: [0, 2],
      }),
      expect.objectContaining({
        name: 'Rope',
        label: '绳索',
        index: 1,
        quantity: 1,
        indexes: [1],
      }),
    ])
  })
})
