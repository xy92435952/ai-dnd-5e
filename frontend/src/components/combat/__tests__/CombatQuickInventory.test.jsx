import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { charactersApi } from '../../../api/client'
import CombatQuickInventory from '../CombatQuickInventory'

vi.mock('../../../api/client', () => ({
  charactersApi: {
    useItem: vi.fn(),
  },
}))

describe('CombatQuickInventory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('stays hidden when the player has no consumables', () => {
    const { container } = render(
      <CombatQuickInventory
        session={{
          player: {
            id: 'char-1',
            equipment: {
              gear: [{ name: 'Rope', zh: '绳索', cost: 1 }],
            },
          },
        }}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('stays hidden when the player only has consumables without direct effects', () => {
    const { container } = render(
      <CombatQuickInventory
        session={{
          player: {
            id: 'char-1',
            equipment: {
              gear: [{ name: 'Torch', zh: '火把', consumable: true }],
            },
          },
        }}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('stacks duplicate consumables and applies the use result to the session', async () => {
    const onSessionChange = vi.fn()
    const onTurnStateChange = vi.fn()
    charactersApi.useItem.mockResolvedValue({
      item: 'Healing Potion',
      heal_amount: 6,
      hp_after: 10,
      equipment: {
        gear: [{ name: 'Healing Potion', zh: '治疗药水', consumable: true }],
      },
      turn_state: {
        action_used: true,
        bonus_action_used: false,
        reaction_used: false,
        movement_used: 0,
        movement_max: 6,
      },
    })

    render(
      <CombatQuickInventory
        session={{
          session_id: 'sess-1',
          player: {
            id: 'char-1',
            hp_current: 4,
            equipment: {
              gear: [
                { name: 'Healing Potion', zh: '治疗药水', consumable: true },
                { name: 'Healing Potion', zh: '治疗药水', consumable: true },
              ],
            },
          },
        }}
        onSessionChange={onSessionChange}
        onTurnStateChange={onTurnStateChange}
      />,
    )

    const panel = screen.getByRole('region', { name: '战斗快捷物品' })
    expect(panel).toHaveClass('combat-quick-inventory')
    expect(within(panel).getByText('快捷物品')).toHaveClass('combat-quick-inventory-title')
    const list = within(panel).getByRole('list', { name: '可用快捷物品' })
    expect(within(list).getByRole('listitem', { name: '快捷物品 治疗药水 x2' })).toBeInTheDocument()
    const button = within(list).getByRole('button', { name: '使用 治疗药水' })
    expect(button).toHaveClass('combat-quick-inventory-action')
    expect(button).toHaveTextContent('治疗药水 x2')

    fireEvent.click(button)

    await waitFor(() => {
      expect(charactersApi.useItem).toHaveBeenCalledWith('char-1', 'Healing Potion', {
        session_id: 'sess-1',
        use_in_combat: true,
      })
      expect(onSessionChange).toHaveBeenCalledWith(expect.objectContaining({
        player: expect.objectContaining({
          hp_current: 10,
          equipment: {
            gear: [{ name: 'Healing Potion', zh: '治疗药水', consumable: true }],
          },
        }),
      }))
      expect(onTurnStateChange).toHaveBeenCalledWith(expect.objectContaining({
        action_used: true,
      }))
    })
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('治疗药水 恢复 6 HP')
    })
  })

  it('merges added conditions from combat consumable results', async () => {
    const onSessionChange = vi.fn()
    charactersApi.useItem.mockResolvedValue({
      item: 'Potion of Fire Resistance',
      added_condition: 'fire_resistance',
      conditions: ['fire_resistance'],
      equipment: { gear: [] },
      turn_state: { action_used: true },
    })

    render(
      <CombatQuickInventory
        session={{
          session_id: 'sess-1',
          player: {
            id: 'char-1',
            conditions: [],
            equipment: {
              gear: [
                {
                  name: 'Potion of Fire Resistance',
                  zh: '火焰抗性药水',
                  consumable: true,
                  effect: 'fire_resistance',
                },
              ],
            },
          },
        }}
        onSessionChange={onSessionChange}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '使用 火焰抗性药水' }))

    await waitFor(() => {
      expect(onSessionChange).toHaveBeenCalledWith(expect.objectContaining({
        player: expect.objectContaining({
          conditions: ['fire_resistance'],
          equipment: { gear: [] },
        }),
      }))
    })
    expect(await screen.findByText('已使用 火焰抗性药水')).toBeInTheDocument()
  })

  it('uses a healer kit on a selected combat ally target', async () => {
    const onSessionChange = vi.fn()
    const onTurnStateChange = vi.fn()
    charactersApi.useItem.mockResolvedValue({
      item: "Healer's Kit",
      effect: 'stabilize',
      target_character_id: 'ally-1',
      target_name: '濒死队友',
      death_saves: { successes: 0, failures: 0, stable: true },
      equipment: {
        gear: [
          { name: "Healer's Kit", zh: '医疗包', consumable: true, uses: 9 },
        ],
      },
      turn_state: { action_used: true },
    })

    render(
      <CombatQuickInventory
        session={{
          session_id: 'sess-1',
          player: {
            id: 'char-1',
            name: '测试战士',
            hp_current: 8,
            equipment: {
              gear: [
                { name: "Healer's Kit", zh: '医疗包', consumable: true, uses: 10 },
              ],
            },
          },
          companions: [
            { id: 'ally-1', name: '濒死队友', hp_current: 0 },
          ],
        }}
        onSessionChange={onSessionChange}
        onTurnStateChange={onTurnStateChange}
      />,
    )

    const panel = screen.getByRole('region', { name: '战斗快捷物品' })
    const list = within(panel).getByRole('list', { name: '可用快捷物品' })
    expect(within(list).getByRole('listitem', { name: '快捷物品 医疗包 (10)' })).toBeInTheDocument()
    const targetSelect = within(list).getByRole('combobox', { name: '用于 医疗包' })
    expect(targetSelect).toHaveClass('combat-quick-inventory-select')
    fireEvent.change(targetSelect, { target: { value: 'ally-1' } })

    await waitFor(() => {
      expect(charactersApi.useItem).toHaveBeenCalledWith('char-1', "Healer's Kit", {
        session_id: 'sess-1',
        use_in_combat: true,
        target_character_id: 'ally-1',
      })
      expect(onSessionChange).toHaveBeenCalledWith(expect.objectContaining({
        player: expect.objectContaining({
          equipment: {
            gear: [
              { name: "Healer's Kit", zh: '医疗包', consumable: true, uses: 9 },
            ],
          },
        }),
        companions: [
          expect.objectContaining({
            id: 'ally-1',
            death_saves: { successes: 0, failures: 0, stable: true },
          }),
        ],
      }))
      expect(onTurnStateChange).toHaveBeenCalledWith(expect.objectContaining({
        action_used: true,
      }))
    })
    expect(await screen.findByText('已用 医疗包 稳定 濒死队友')).toBeInTheDocument()
  })

  it('disables consumables after the action has been used this turn', () => {
    render(
      <CombatQuickInventory
        session={{
          session_id: 'sess-1',
          player: {
            id: 'char-1',
            equipment: {
              gear: [
                { name: 'Healing Potion', zh: '治疗药水', consumable: true },
              ],
            },
          },
        }}
        turnState={{ action_used: true }}
      />,
    )

    expect(screen.getByRole('button', { name: '使用 治疗药水' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('本回合动作已使用')
  })

  it('disables consumables outside the player turn', () => {
    render(
      <CombatQuickInventory
        session={{
          session_id: 'sess-1',
          player: {
            id: 'char-1',
            equipment: {
              gear: [
                { name: 'Healing Potion', zh: '治疗药水', consumable: true },
              ],
            },
          },
        }}
        isPlayerTurn={false}
      />,
    )

    expect(screen.getByRole('button', { name: '使用 治疗药水' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('等待你的回合')
  })

  it('explains disabled consumables while combat is processing or syncing', () => {
    render(
      <CombatQuickInventory
        session={{
          session_id: 'sess-1',
          player: {
            id: 'char-1',
            equipment: {
              gear: [
                { name: 'Healing Potion', zh: '治疗药水', consumable: true },
              ],
            },
          },
        }}
        disabled
      />,
    )

    const button = screen.getByRole('button', { name: '使用 治疗药水' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', '正在结算或同步战斗')
    expect(screen.getByRole('status')).toHaveTextContent('正在结算或同步战斗')
  })
})
