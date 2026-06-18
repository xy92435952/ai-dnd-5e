import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import CombatHudControls from '../CombatHudControls'
import { getAttackWeaponOptions } from '../../../utils/combatWeapons'

const TEST_CHARACTER = {
  equipment: {
    weapons: [
      {
        name: 'Longsword',
        zh: '长剑',
        type: 'martial_melee',
        properties: ['versatile(1d10)'],
        equipped: true,
      },
      {
        name: 'Javelin',
        zh: '标枪',
        type: 'simple_melee',
        properties: ['thrown(30/120)'],
        equipped: false,
      },
      {
        name: 'Longbow',
        zh: '长弓',
        type: 'martial_ranged',
        properties: ['ammunition', 'range(150/600)', 'two-handed'],
        ammo: 7,
      },
      {
        name: 'Light Crossbow',
        zh: '轻弩',
        type: 'simple_ranged',
        properties: ['ammunition', 'range(80/320)', 'loading', 'two-handed'],
        ammo: 0,
      },
    ],
  },
}

function renderControls(overrides = {}) {
  const props = {
    isProcessing: false,
    isPlayerTurn: true,
    syncBlocked: false,
    moveMode: false,
    isRanged: false,
    selectedWeaponName: '',
    character: TEST_CHARACTER,
    turnState: {},
    onEndTurn: vi.fn(),
    onDelayTurn: vi.fn(),
    onDelayAfterEntityChange: vi.fn(),
    onToggleMove: vi.fn(),
    onToggleRanged: vi.fn(),
    onSelectedWeaponChange: vi.fn(),
    onToggleLuckyAttack: vi.fn(),
    onOpenCharacter: vi.fn(),
    onReturnAdventure: vi.fn(),
    onForceEndCombat: vi.fn(),
    ...overrides,
  }
  render(<CombatHudControls {...props} />)
  return props
}

describe('CombatHudControls', () => {
  it('keeps turn action buttons enabled on the active turn', () => {
    const props = renderControls()
    const controls = screen.getByRole('region', { name: '战斗回合控制' })
    const actions = within(controls).getByRole('group', { name: '战斗行动命令' })

    expect(controls).toHaveClass('combat-turn-controls')
    expect(actions).toHaveClass('combat-turn-action-grid')
    expect(within(actions).getByRole('button', { name: '延迟' })).toHaveClass('combat-turn-compact-action')
    expect(within(actions).getByLabelText('攻击武器')).toHaveClass('combat-turn-select', 'combat-turn-weapon-select')

    fireEvent.click(within(controls).getByRole('button', { name: /结束回合/ }))
    fireEvent.click(within(actions).getByRole('button', { name: '延迟' }))
    fireEvent.click(within(actions).getByRole('button', { name: /移动/ }))
    fireEvent.click(within(actions).getByRole('button', { name: /远程/ }))
    fireEvent.change(within(actions).getByLabelText('攻击武器'), { target: { value: 'Javelin' } })

    expect(props.onEndTurn).toHaveBeenCalledTimes(1)
    expect(props.onDelayTurn).toHaveBeenCalledWith(null)
    expect(props.onToggleMove).toHaveBeenCalledTimes(1)
    expect(props.onToggleRanged).toHaveBeenCalledTimes(1)
    expect(props.onSelectedWeaponChange).toHaveBeenCalledWith('Javelin')
  })

  it('explains disabled turn controls while waiting for another turn', () => {
    const props = renderControls({ isPlayerTurn: false })

    const endTurn = screen.getByRole('button', { name: /结束回合/ })
    const delay = screen.getByRole('button', { name: '延迟' })
    const move = screen.getByRole('button', { name: /移动/ })
    const ranged = screen.getByRole('button', { name: /远程/ })

    expect(endTurn).toBeDisabled()
    expect(endTurn).toHaveAttribute('title', '等待你的回合')
    expect(delay).toBeDisabled()
    expect(delay).toHaveAttribute('title', '等待你的回合')
    expect(move).toBeDisabled()
    expect(move).toHaveAttribute('title', '等待你的回合')
    expect(ranged).toBeDisabled()
    expect(ranged).toHaveAttribute('title', '等待你的回合')
    expect(screen.getByRole('status')).toHaveTextContent('等待你的回合')
    expect(screen.getByRole('status')).toHaveClass('combat-turn-status')

    fireEvent.click(endTurn)
    fireEvent.click(delay)
    fireEvent.click(move)
    fireEvent.click(ranged)

    expect(props.onEndTurn).not.toHaveBeenCalled()
    expect(props.onDelayTurn).not.toHaveBeenCalled()
    expect(props.onToggleMove).not.toHaveBeenCalled()
    expect(props.onToggleRanged).not.toHaveBeenCalled()
  })

  it('explains sync-blocked turn controls', () => {
    renderControls({ syncBlocked: true })

    const endTurn = screen.getByRole('button', { name: /同步中/ })
    expect(endTurn).toBeDisabled()
    expect(endTurn).toHaveAttribute('title', '等待战斗同步恢复')
    expect(screen.getByRole('status')).toHaveTextContent('等待战斗同步恢复')
  })

  it('filters attack weapons by melee and ranged mode', () => {
    expect(getAttackWeaponOptions(TEST_CHARACTER, false).map(weapon => weapon.name)).toEqual([
      'Longsword',
      'Javelin',
    ])
    expect(getAttackWeaponOptions(TEST_CHARACTER, true).map(weapon => weapon.name)).toEqual([
      'Javelin',
      'Longbow',
    ])
  })

  it('renders ranged weapon resources and preserves the selected weapon value', () => {
    renderControls({
      isRanged: true,
      selectedWeaponName: 'Longbow',
    })

    const selector = screen.getByLabelText('攻击武器')
    expect(selector).toHaveValue('Longbow')
    expect(selector).toHaveClass('combat-turn-select', 'combat-turn-weapon-select')
    expect(screen.getByRole('option', { name: '长弓 · 弹药 7' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /轻弩/ })).not.toBeInTheDocument()
  })

  it('renders a Lucky attack toggle when points remain', () => {
    const props = renderControls({
      classResources: { lucky_points_remaining: 2 },
      useLuckyAttack: true,
    })

    const lucky = screen.getByRole('button', { name: 'Lucky ON · 2' })
    expect(lucky).toHaveAttribute('aria-pressed', 'true')
    expect(lucky).toHaveClass('combat-turn-compact-action')

    fireEvent.click(lucky)
    expect(props.onToggleLuckyAttack).toHaveBeenCalledTimes(1)
  })

  it('renders a Bardic Inspiration attack toggle when an unused die is available', () => {
    const props = renderControls({
      classResources: { bardic_inspiration: { die: 'd8', uses_remaining: 1 } },
      useBardicAttack: true,
      onToggleBardicAttack: vi.fn(),
    })

    const bardic = screen.getByRole('button', { name: 'Bardic ON · d8' })
    expect(bardic).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(bardic)
    expect(props.onToggleBardicAttack).toHaveBeenCalledTimes(1)
  })

  it('renders a Bardic end-save toggle when a repeat save is pending', () => {
    const props = renderControls({
      classResources: { bardic_inspiration: { die: 'd8', uses_remaining: 1 } },
      useBardicEndSave: true,
      onToggleBardicEndSave: vi.fn(),
      character: {
        ...TEST_CHARACTER,
        conditions: ['blinded'],
        condition_durations: {
          blinded: {
            repeat_save: 'end_of_turn',
            save_ability: 'con',
            save_dc: 15,
          },
        },
      },
    })

    const toggle = screen.getByRole('button', { name: 'End Save ON 路 d8' })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(toggle)
    expect(props.onToggleBardicEndSave).toHaveBeenCalledTimes(1)
  })

  it('submits delay placement after a selected later combatant', () => {
    const props = renderControls({
      delayTurnOptions: [
        { value: 'enemy-1', label: 'Goblin Guard' },
        { value: 'ally-1', label: 'Mara Quickstep' },
      ],
      delayAfterEntityId: 'enemy-1',
    })

    expect(screen.getByLabelText('延迟位置')).toHaveValue('enemy-1')
    expect(screen.getByLabelText('延迟位置')).toHaveClass('combat-turn-select')
    fireEvent.change(screen.getByLabelText('延迟位置'), { target: { value: 'ally-1' } })
    fireEvent.click(screen.getByRole('button', { name: '延迟' }))

    expect(props.onDelayAfterEntityChange).toHaveBeenCalledWith('ally-1')
    expect(props.onDelayTurn).toHaveBeenCalledWith('enemy-1')
  })

  it('allows an AI driver to delay an AI-controlled turn without enabling player-only controls', () => {
    const props = renderControls({
      isPlayerTurn: false,
      canDelayTurn: true,
    })

    const delay = screen.getByRole('button', { name: '延迟' })
    const endTurn = screen.getByRole('button', { name: /结束回合/ })
    const move = screen.getByRole('button', { name: /移动/ })

    expect(delay).not.toBeDisabled()
    expect(endTurn).toBeDisabled()
    expect(move).toBeDisabled()

    fireEvent.click(delay)
    fireEvent.click(endTurn)
    fireEvent.click(move)

    expect(props.onDelayTurn).toHaveBeenCalledWith(null)
    expect(props.onEndTurn).not.toHaveBeenCalled()
    expect(props.onToggleMove).not.toHaveBeenCalled()
  })

  it('disables delay after the actor spent turn resources but keeps ending turn available', () => {
    const props = renderControls({
      turnState: {
        action_used: true,
        attacks_made: 1,
      },
    })

    const delay = screen.getByRole('button', { name: '延迟' })
    const endTurn = screen.getByRole('button', { name: /结束回合/ })

    expect(delay).toBeDisabled()
    expect(delay).toHaveAttribute('title', '已花费本回合动作，不能延迟')
    expect(endTurn).not.toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('已花费本回合动作，不能延迟')

    fireEvent.click(delay)
    fireEvent.click(endTurn)

    expect(props.onDelayTurn).not.toHaveBeenCalled()
    expect(props.onEndTurn).toHaveBeenCalledTimes(1)
  })
})
