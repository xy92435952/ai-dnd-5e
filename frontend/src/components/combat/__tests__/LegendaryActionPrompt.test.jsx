import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import LegendaryActionPrompt from '../LegendaryActionPrompt'

describe('LegendaryActionPrompt', () => {
  it('renders available legendary actions and resolves the selected option', () => {
    const onUse = vi.fn()
    const onSkip = vi.fn()

    render(
      <LegendaryActionPrompt
        prompt={{
          actor_id: 'dragon-1',
          actor_name: 'Ancient Gatekeeper',
          remaining: 2,
          uses: 3,
          context: 'Ancient Gatekeeper can use a Legendary Action after Smoke Sentinel turn.',
          actions: [
            {
              id: 'detect',
              name: 'Detect',
              cost: 1,
              remaining_after: 1,
              description: 'Perceive a threat.',
            },
          ],
        }}
        onUse={onUse}
        onSkip={onSkip}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '传奇动作窗口' })
    expect(dialog).toHaveAttribute('aria-describedby', 'legendary-action-prompt-context')
    expect(within(dialog).getByRole('group', { name: '可用传奇动作' })).toBeInTheDocument()
    const actionList = within(dialog).getByRole('list', { name: '传奇动作选项' })
    expect(within(actionList).getByRole('listitem')).toHaveClass('legendary-action-prompt-item')
    expect(dialog).toHaveTextContent('传奇动作')
    expect(dialog).toHaveTextContent('Ancient Gatekeeper · 2/3')
    expect(dialog).toHaveTextContent('Detect')
    expect(within(dialog).getByTitle('Detect · 消耗 1 · 剩余 1 · Perceive a threat.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Detect/ }))
    expect(onUse).toHaveBeenCalledWith('dragon-1', 'detect', undefined)

    fireEvent.click(screen.getByRole('button', { name: '跳过传奇动作' }))
    expect(onSkip).toHaveBeenCalled()
  })

  it('shows target, attack bonus, and damage for attack legendary actions', () => {
    render(
      <LegendaryActionPrompt
        prompt={{
          actor_id: 'dragon-1',
          actor_name: 'Ancient Gatekeeper',
          remaining: 2,
          uses: 3,
          actions: [
            {
              id: 'tail',
              name: 'Tail Strike',
              cost: 1,
              remaining_after: 1,
              target_id: 'hero-1',
              target_name: 'Smoke Sentinel',
              attack_bonus: 7,
              damage_dice: '1d8+3',
              damage_type: 'bludgeoning',
            },
          ],
        }}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '传奇动作窗口' })
    expect(dialog).toHaveTextContent('Tail Strike')
    expect(dialog).toHaveTextContent('消耗 1 · 剩余 1 · 目标 Smoke Sentinel · 命中 +7 · 伤害 1d8+3 bludgeoning')
    expect(within(dialog).getByTitle(
      'Tail Strike · 消耗 1 · 剩余 1 · 目标 Smoke Sentinel · 命中 +7 · 伤害 1d8+3 bludgeoning',
    )).toBeInTheDocument()
  })

  it('shows save DC and half-damage hints for save legendary actions', () => {
    render(
      <LegendaryActionPrompt
        prompt={{
          actor_id: 'dragon-1',
          actor_name: 'Ancient Gatekeeper',
          remaining: 2,
          uses: 3,
          actions: [
            {
              id: 'wing',
              name: 'Wing Buffet',
              cost: 2,
              remaining_after: 0,
              target_id: 'hero-1',
              target_name: 'Smoke Sentinel',
              save_ability: 'dex',
              save_dc: 15,
              damage_dice: '2d6',
              damage_type: 'bludgeoning',
              half_on_save: true,
            },
          ],
        }}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '传奇动作窗口' })
    expect(dialog).toHaveTextContent('Wing Buffet')
    expect(dialog).toHaveTextContent('消耗 2 · 剩余 0 · 目标 Smoke Sentinel · 敏捷豁免 · DC 15 · 成功半伤 · 伤害 2d6 bludgeoning')
    expect(within(dialog).getByTitle(
      'Wing Buffet · 消耗 2 · 剩余 0 · 目标 Smoke Sentinel · 敏捷豁免 · DC 15 · 成功半伤 · 伤害 2d6 bludgeoning',
    )).toBeInTheDocument()
  })

  it('passes multi-target legendary action ids and shows affected count', () => {
    const onUse = vi.fn()
    render(
      <LegendaryActionPrompt
        prompt={{
          actor_id: 'dragon-1',
          actor_name: 'Ancient Gatekeeper',
          remaining: 2,
          uses: 3,
          actions: [
            {
              id: 'wing',
              name: 'Wing Buffet',
              cost: 2,
              remaining_after: 0,
              target_ids: ['hero-1', 'ally-1'],
              target_names: ['Smoke Sentinel', 'Mara Quickstep'],
              target_count: 2,
              save_ability: 'dex',
              save_dc: 15,
              damage_dice: '2d6',
              damage_type: 'bludgeoning',
              half_on_save: true,
            },
          ],
        }}
        onUse={onUse}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '传奇动作窗口' })
    expect(dialog).toHaveTextContent('Wing Buffet')
    expect(dialog).toHaveTextContent('影响 2 · 目标 Smoke Sentinel、Mara Quickstep · 敏捷豁免')
    fireEvent.click(screen.getByRole('button', { name: /Wing Buffet/ }))

    expect(onUse).toHaveBeenCalledWith('dragon-1', 'wing', ['hero-1', 'ally-1'])
  })

  it('shows area template metadata while preserving auto target ids', () => {
    const onUse = vi.fn()
    render(
      <LegendaryActionPrompt
        prompt={{
          actor_id: 'dragon-1',
          actor_name: 'Ancient Gatekeeper',
          remaining: 2,
          uses: 3,
          actions: [
            {
              id: 'wing',
              name: 'Wing Buffet',
              cost: 2,
              remaining_after: 0,
              target_ids: ['hero-1', 'ally-1'],
              target_names: ['Smoke Sentinel', 'Mara Quickstep'],
              target_count: 2,
              area_template: 'cone',
              area_range_ft: 15,
              save_ability: 'dex',
              save_dc: 15,
              damage_dice: '2d6',
              damage_type: 'bludgeoning',
              half_on_save: true,
            },
          ],
        }}
        onUse={onUse}
      />,
    )

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('Wing Buffet')
    expect(dialog).toHaveTextContent('范围 15ft cone')

    fireEvent.click(screen.getByRole('button', { name: /Wing Buffet/ }))
    expect(onUse).toHaveBeenCalledWith('dragon-1', 'wing', ['hero-1', 'ally-1'])
  })

  it('renders lair action prompts and submits source ids with area targets', () => {
    const onUse = vi.fn()
    const onSkip = vi.fn()
    render(
      <LegendaryActionPrompt
        variant="lair"
        prompt={{
          source_id: 'goblin-lair',
          source_name: 'Cracked Shrine',
          round_number: 2,
          context: 'Cracked Shrine can use a Lair Action at the start of round 2.',
          actions: [
            {
              id: 'seismic-pulse',
              name: 'Seismic Pulse',
              target_ids: ['hero-1', 'ally-1'],
              target_names: ['Smoke Sentinel', 'Mara Quickstep'],
              target_count: 2,
              area_template: 'radius',
              area_range_ft: 15,
              save_ability: 'dex',
              save_dc: 15,
              damage_dice: '2d6',
              damage_type: 'bludgeoning',
              half_on_save: true,
            },
          ],
        }}
        onUse={onUse}
        onSkip={onSkip}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '巢穴动作窗口' })
    expect(dialog).toHaveAttribute('aria-describedby', 'lair-action-prompt-context')
    expect(within(dialog).getByRole('group', { name: '可用巢穴动作' })).toBeInTheDocument()
    expect(within(dialog).getByRole('list', { name: '巢穴动作选项' })).toBeInTheDocument()
    expect(dialog).toHaveTextContent('巢穴动作')
    expect(dialog).toHaveTextContent('Cracked Shrine · 第 2 轮')
    expect(dialog).toHaveTextContent('范围 15ft radius')

    fireEvent.click(screen.getByRole('button', { name: /Seismic Pulse/ }))
    expect(onUse).toHaveBeenCalledWith('goblin-lair', 'seismic-pulse', ['hero-1', 'ally-1'])

    fireEvent.click(screen.getByRole('button', { name: '跳过巢穴动作' }))
    expect(onSkip).toHaveBeenCalled()
  })

  it('shows failed-save condition riders for non-damaging save legendary actions', () => {
    render(
      <LegendaryActionPrompt
        prompt={{
          actor_id: 'dragon-1',
          actor_name: 'Ancient Gatekeeper',
          remaining: 1,
          uses: 3,
          actions: [
            {
              id: 'mind-lock',
              name: 'Mind Lock',
              cost: 1,
              remaining_after: 0,
              target_id: 'hero-1',
              target_name: 'Smoke Sentinel',
              save_ability: 'wis',
              save_dc: 15,
              condition_on_failed_save: 'stunned',
              conditions_on_failed_save: ['stunned'],
              condition_duration_rounds: 1,
            },
          ],
        }}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '传奇动作窗口' })
    expect(dialog).toHaveTextContent('Mind Lock')
    expect(dialog).toHaveTextContent('目标 Smoke Sentinel · 感知豁免 · DC 15 · 失败附加')
    expect(dialog).not.toHaveTextContent('伤害')
  })

  it('shows failed-save forced movement riders for save legendary actions', () => {
    render(
      <LegendaryActionPrompt
        prompt={{
          actor_id: 'dragon-1',
          actor_name: 'Ancient Gatekeeper',
          remaining: 1,
          uses: 3,
          actions: [
            {
              id: 'wing-gust',
              name: 'Wing Gust',
              cost: 1,
              remaining_after: 0,
              target_id: 'hero-1',
              target_name: 'Smoke Sentinel',
              save_ability: 'str',
              save_dc: 16,
              push_distance_ft: 5,
            },
          ],
        }}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '传奇动作窗口' })
    expect(dialog).toHaveTextContent('Wing Gust')
    expect(dialog).toHaveTextContent('目标 Smoke Sentinel · 力量豁免 · DC 16 · 失败推开 5ft')
  })

  it('reports empty legendary action windows as a status while preserving skip', () => {
    const onSkip = vi.fn()
    render(
      <LegendaryActionPrompt
        prompt={{
          actor_id: 'dragon-1',
          actor_name: 'Ancient Gatekeeper',
          remaining: 0,
          uses: 3,
          actions: [],
        }}
        onSkip={onSkip}
      />,
    )

    const dialog = screen.getByRole('dialog', { name: '传奇动作窗口' })
    expect(dialog.querySelector('.legendary-action-prompt-card')).toBeTruthy()
    const status = within(dialog).getByRole('status')
    expect(status).toHaveClass('legendary-action-prompt-empty')
    expect(status).toHaveTextContent('当前没有可用传奇动作。')

    fireEvent.click(within(dialog).getByRole('button', { name: '跳过传奇动作' }))
    expect(onSkip).toHaveBeenCalledWith(expect.objectContaining({ actor_id: 'dragon-1' }))
  })
})
