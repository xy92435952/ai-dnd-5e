import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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

    fireEvent.click(screen.getByRole('button', { name: /结束回合/ }))
    fireEvent.click(screen.getByRole('button', { name: '延迟' }))
    fireEvent.click(screen.getByRole('button', { name: /移动/ }))
    fireEvent.click(screen.getByRole('button', { name: /远程/ }))
    fireEvent.change(screen.getByLabelText('攻击武器'), { target: { value: 'Javelin' } })

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
    expect(screen.getByText('等待你的回合')).toBeInTheDocument()

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
    expect(screen.getByText('等待战斗同步恢复')).toBeInTheDocument()
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
    expect(screen.getByRole('option', { name: '长弓 · 弹药 7' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /轻弩/ })).not.toBeInTheDocument()
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
    expect(screen.getByText('已花费本回合动作，不能延迟')).toBeInTheDocument()

    fireEvent.click(delay)
    fireEvent.click(endTurn)

    expect(props.onDelayTurn).not.toHaveBeenCalled()
    expect(props.onEndTurn).toHaveBeenCalledTimes(1)
  })
})
