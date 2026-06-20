import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { charactersApi } from '../../../api/client'
import InventoryPanel from '../InventoryPanel'

vi.mock('../../../api/client', () => ({
  charactersApi: {
    getShopInventory: vi.fn(),
    equipItem: vi.fn(),
    useItem: vi.fn(),
    sellItem: vi.fn(),
    transferItem: vi.fn(),
    buyItem: vi.fn(),
    updateAmmo: vi.fn(),
  },
}))

describe('InventoryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders responsive inventory and shop layout hooks', async () => {
    charactersApi.getShopInventory.mockResolvedValue({
      pricing: {
        profile: 'market',
        label: 'Market pricing',
        buy_multiplier: 0.9,
        sell_rate: 0.55,
      },
      weapons: {},
      armor: {},
      gear: {
        Torch: { zh: 'Torch', cost: 1, description: 'Portable light for narrow corridors' },
      },
    })

    const { container } = render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: 'Tester',
          hp_current: 8,
          equipment: {
            gold: 10,
            weapons: [{ name: 'Longsword', zh: 'Longsword', damage: '1d8', equipped: false }],
            gear: [{ name: 'Rope', zh: 'Rope', cost: 1 }],
          },
        }}
        partyMembers={[{ id: 'ally-1', name: 'Ally' }]}
      />,
    )

    expect(container.querySelector('.inventory-panel')).toBeInTheDocument()
    expect(container.querySelector('.inventory-panel-header')).toBeInTheDocument()
    expect(container.querySelector('.inventory-shop-toggle')).toBeInTheDocument()
    expect(container.querySelector('.inventory-gold-strip')).toBeInTheDocument()
    expect(container.querySelector('.inventory-gold-icon')).toBeInTheDocument()
    expect(container.querySelector('.inventory-gold-value')).toHaveTextContent('10')
    expect(container.querySelector('.inventory-gold-unit')).toHaveTextContent('gp')
    expect(container.querySelectorAll('.inventory-section').length).toBeGreaterThanOrEqual(2)
    expect(container.querySelectorAll('.inventory-row').length).toBeGreaterThanOrEqual(2)
    expect(container.querySelector('.inventory-row-actions')).toBeInTheDocument()
    expect(container.querySelector('.inventory-row-action-button')).toBeInTheDocument()
    expect(container.querySelector('.inventory-row-select')).toBeInTheDocument()
    expect(container.querySelector('.inventory-item-meta')).toBeInTheDocument()

    fireEvent.click(container.querySelector('.inventory-shop-toggle'))

    await waitFor(() => {
      expect(charactersApi.getShopInventory).toHaveBeenCalledWith('char-1')
    })
    expect(container.querySelector('.inventory-shop-panel')).toBeInTheDocument()
    expect(container.querySelector('.inventory-shop-pricing.dynamic')).toBeInTheDocument()
    expect(container.querySelector('.inventory-shop-tabs')).toBeInTheDocument()
    expect(container.querySelector('.inventory-shop-grid')).toBeInTheDocument()
    expect(container.querySelector('.inventory-shop-card')).toBeInTheDocument()
    expect(container.querySelector('.inventory-shop-card-footer')).toBeInTheDocument()
    expect(container.querySelector('.inventory-shop-buy-button')).toBeInTheDocument()
  })

  it('equips weapons and merges returned equipment and derived stats', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.equipItem.mockResolvedValue({
      equipment: {
        gold: 10,
        weapons: [{ name: 'Longsword', zh: '长剑', damage: '1d8', equipped: true }],
      },
      derived: { ac: 16, attack_bonus: 5 },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          derived: { ac: 15 },
          equipment: {
            gold: 10,
            weapons: [{ name: 'Longsword', zh: '长剑', damage: '1d8', equipped: false }],
          },
        }}
        onCharacterChange={onCharacterChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '装备' }))

    await waitFor(() => {
      expect(charactersApi.equipItem).toHaveBeenCalledWith('char-1', 'Longsword', 'weapon', true)
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        equipment: {
          gold: 10,
          weapons: [{ name: 'Longsword', zh: '长剑', damage: '1d8', equipped: true }],
        },
        derived: { ac: 16, attack_bonus: 5 },
      }))
    })
    expect(await screen.findByText('已装备 长剑')).toBeInTheDocument()
  })

  it('uses a consumable and updates hit points and remaining gear', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.useItem.mockResolvedValue({
      item: 'Healing Potion',
      heal_amount: 7,
      hp_after: 11,
      equipment: {
        gold: 10,
        gear: [{ name: 'Rope', zh: '绳索', cost: 1 }],
      },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 4,
          conditions: [],
          equipment: {
            gold: 10,
            gear: [
              { name: 'Healing Potion', zh: '治疗药水', consumable: true, cost: 50 },
              { name: 'Rope', zh: '绳索', cost: 1 },
            ],
          },
        }}
        onCharacterChange={onCharacterChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '使用' }))

    await waitFor(() => {
      expect(charactersApi.useItem).toHaveBeenCalledWith('char-1', 'Healing Potion')
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        hp_current: 11,
        equipment: {
          gold: 10,
          gear: [{ name: 'Rope', zh: '绳索', cost: 1 }],
        },
      }))
    })
    expect(await screen.findByText('治疗药水 恢复 7 HP')).toBeInTheDocument()
  })

  it('merges an added condition after using a buff consumable', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.useItem.mockResolvedValue({
      item: 'Potion of Fire Resistance',
      added_condition: 'fire_resistance',
      conditions: ['fire_resistance'],
      equipment: {
        gold: 10,
        gear: [],
      },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          conditions: [],
          equipment: {
            gold: 10,
            gear: [
              {
                name: 'Potion of Fire Resistance',
                zh: '火焰抗性药水',
                consumable: true,
                effect: 'fire_resistance',
              },
            ],
          },
        }}
        onCharacterChange={onCharacterChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '使用' }))

    await waitFor(() => {
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        conditions: ['fire_resistance'],
        equipment: {
          gold: 10,
          gear: [],
        },
      }))
    })
    expect(await screen.findByText('已使用 火焰抗性药水')).toBeInTheDocument()
  })

  it('uses a healer kit on a selected party target and updates remaining uses', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.useItem.mockResolvedValue({
      item: "Healer's Kit",
      effect: 'stabilize',
      target_character_id: 'ally-1',
      target_name: '测试队友',
      death_saves: { successes: 0, failures: 0, stable: true },
      uses_remaining: 9,
      equipment: {
        gold: 10,
        gear: [
          {
            name: "Healer's Kit",
            zh: '医疗包',
            consumable: true,
            uses: 9,
          },
        ],
      },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          conditions: [],
          equipment: {
            gold: 10,
            gear: [
              {
                name: "Healer's Kit",
                zh: '医疗包',
                consumable: true,
                uses: 10,
              },
            ],
          },
        }}
        partyMembers={[{ id: 'ally-1', name: '测试队友' }]}
        onCharacterChange={onCharacterChange}
      />,
    )

    expect(screen.getByText('剩余 10 次')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('用于 医疗包'), { target: { value: 'ally-1' } })

    await waitFor(() => {
      expect(charactersApi.useItem).toHaveBeenCalledWith('char-1', "Healer's Kit", {
        target_character_id: 'ally-1',
      })
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        equipment: {
          gold: 10,
          gear: [
            {
              name: "Healer's Kit",
              zh: '医疗包',
              consumable: true,
              uses: 9,
            },
          ],
        },
      }))
    })
    expect(await screen.findByText('已用 医疗包 稳定 测试队友')).toBeInTheDocument()
  })

  it('does not show a use action for consumables without implemented direct effects', () => {
    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          equipment: {
            gold: 10,
            gear: [
              { name: 'Torch', zh: '火把', consumable: true, cost: 0.01 },
              { name: 'Rope', zh: '绳索', cost: 1 },
            ],
          },
        }}
      />,
    )

    expect(screen.getByText('火把')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '使用' })).not.toBeInTheDocument()
  })

  it('sells an unequipped item and updates gold and gear', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.sellItem.mockResolvedValue({
      sold: 'Rope',
      sell_price: 1,
      gold_remaining: 11,
      equipment: {
        gold: 11,
        gear: [],
      },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          equipment: {
            gold: 10,
            gear: [{ name: 'Rope', zh: '绳索', cost: 2 }],
          },
        }}
        onCharacterChange={onCharacterChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '出售' }))

    await waitFor(() => {
      expect(charactersApi.sellItem).toHaveBeenCalledWith('char-1', 'Rope', 'gear', 0)
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        equipment: {
          gold: 11,
          gear: [],
        },
      }))
    })
    expect(await screen.findByText('出售 绳索，获得 1 gp')).toBeInTheDocument()
  })

  it('updates the current character inventory after transferring an item', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.transferItem.mockResolvedValue({
      transferred: 'Healing Potion',
      target_character_id: 'ally-1',
      source_equipment: {
        gold: 10,
        gear: [{ name: 'Rope', zh: '绳索', cost: 1 }],
      },
      target_equipment: {
        gold: 0,
        gear: [{ name: 'Healing Potion', zh: '治疗药水', consumable: true }],
      },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          conditions: [],
          equipment: {
            gold: 10,
            gear: [
              { name: 'Healing Potion', zh: '治疗药水', consumable: true, cost: 50 },
              { name: 'Rope', zh: '绳索', cost: 1 },
            ],
          },
        }}
        partyMembers={[{ id: 'ally-1', name: '测试队友' }]}
        onCharacterChange={onCharacterChange}
      />,
    )

    fireEvent.change(screen.getByLabelText('给予 治疗药水'), { target: { value: 'ally-1' } })

    await waitFor(() => {
      expect(charactersApi.transferItem).toHaveBeenCalledWith(
        'char-1',
        'ally-1',
        'Healing Potion',
        'gear',
        0,
      )
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        equipment: {
          gold: 10,
          gear: [{ name: 'Rope', zh: '绳索', cost: 1 }],
        },
      }))
    })
  })

  it('transfers shields with the shield category instead of armor', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.transferItem.mockResolvedValue({
      transferred: 'Shield',
      target_character_id: 'ally-1',
      source_equipment: {
        gold: 10,
        shield: null,
      },
      target_equipment: {
        gold: 0,
        shield: { name: 'Shield', zh: '盾牌', ac: 2, equipped: false },
      },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          equipment: {
            gold: 10,
            shield: { name: 'Shield', zh: '盾牌', ac: 2, equipped: false },
          },
        }}
        partyMembers={[{ id: 'ally-1', name: '测试队友' }]}
        onCharacterChange={onCharacterChange}
      />,
    )

    fireEvent.change(screen.getByLabelText('给予 盾牌'), { target: { value: 'ally-1' } })

    await waitFor(() => {
      expect(charactersApi.transferItem).toHaveBeenCalledWith(
        'char-1',
        'ally-1',
        'Shield',
        'shield',
        0,
      )
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        equipment: {
          gold: 10,
          shield: null,
        },
      }))
    })
  })

  it('opens the shop, buys an item, and merges the returned inventory', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.getShopInventory.mockResolvedValue({
      weapons: {},
      armor: {},
      gear: {
        Torch: { zh: '火把', cost: 1, description: '照明工具' },
      },
    })
    charactersApi.buyItem.mockResolvedValue({
      bought: 'Torch',
      quantity: 1,
      cost: 1,
      gold_remaining: 9,
      equipment: {
        gold: 9,
        gear: [{ name: 'Torch', zh: '火把', cost: 1, description: '照明工具' }],
      },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          equipment: {
            gold: 10,
            gear: [],
          },
        }}
        onCharacterChange={onCharacterChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '打开商店' }))
    fireEvent.click(await screen.findByRole('button', { name: '购买' }))

    await waitFor(() => {
      expect(charactersApi.getShopInventory).toHaveBeenCalledWith('char-1')
      expect(charactersApi.buyItem).toHaveBeenCalledWith('char-1', 'Torch', 'gear', 1)
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        equipment: {
          gold: 9,
          gear: [{ name: 'Torch', zh: '火把', cost: 1, description: '照明工具' }],
        },
      }))
    })
    expect(await screen.findByText('购买 火把')).toBeInTheDocument()
  })

  it('shows location shop pricing and modified item costs', async () => {
    charactersApi.getShopInventory.mockResolvedValue({
      pricing: {
        profile: 'market',
        label: '市集价格',
        buy_multiplier: 0.9,
        sell_rate: 0.55,
      },
      weapons: {},
      armor: {},
      gear: {
        'Healing Potion': { zh: '治疗药水', cost: 45, base_cost: 50, description: '恢复2d4+2 HP' },
      },
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          equipment: {
            gold: 45,
            gear: [],
          },
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '打开商店' }))

    expect(await screen.findByLabelText('Shop pricing')).toHaveTextContent('市集价格')
    expect(screen.getByLabelText('Shop pricing')).toHaveTextContent('买入 x0.9')
    expect(screen.getByLabelText('Shop pricing')).toHaveTextContent('卖出 55%')
    expect(screen.getByText('45 gp')).toBeInTheDocument()
    expect(screen.getByText('原价 50 gp')).toBeInTheDocument()
  })

  it('adjusts ammunition without replacing the rest of the equipment', async () => {
    const onCharacterChange = vi.fn()
    charactersApi.updateAmmo.mockResolvedValue({
      weapon: 'Longbow',
      ammo: 19,
      change: -1,
    })

    render(
      <InventoryPanel
        character={{
          id: 'char-1',
          name: '测试战士',
          hp_current: 8,
          equipment: {
            gold: 10,
            weapons: [
              { name: 'Longbow', zh: '长弓', damage: '1d8', ammo: 20, equipped: false },
            ],
            gear: [{ name: 'Rope', zh: '绳索', cost: 1 }],
          },
        }}
        onCharacterChange={onCharacterChange}
      />,
    )

    expect(screen.getByRole('button', { name: '-1' })).toHaveClass('inventory-ammo-button')
    expect(screen.getByRole('button', { name: '+1' })).toHaveClass('inventory-ammo-button')
    fireEvent.click(screen.getByRole('button', { name: '-1' }))

    await waitFor(() => {
      expect(charactersApi.updateAmmo).toHaveBeenCalledWith('char-1', 'Longbow', -1)
      expect(onCharacterChange).toHaveBeenCalledWith(expect.objectContaining({
        equipment: {
          gold: 10,
          weapons: [
            { name: 'Longbow', zh: '长弓', damage: '1d8', ammo: 19, equipped: false },
          ],
          gear: [{ name: 'Rope', zh: '绳索', cost: 1 }],
        },
      }))
    })
    expect(await screen.findByText('长弓 弹药 19')).toBeInTheDocument()
  })
})
