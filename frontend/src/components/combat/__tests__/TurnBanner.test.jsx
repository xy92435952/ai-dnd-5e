import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import TurnBanner from '../TurnBanner'

describe('TurnBanner', () => {
  it('renders the active turn coach under the round banner', () => {
    render(
      <TurnBanner
        roundNumber={3}
        currentTurnName="洛林"
        currentTurnEntry={{ character_id: 'hero-1', name: '洛林', is_player: true }}
        currentTurnEntity={{ id: 'hero-1', name: '洛林', is_player: true }}
        controlledCharacter={{ id: 'hero-1', name: '洛林' }}
        isPlayerTurn={true}
        nextTurnName="矿洞斥候"
        nextTurnTone="enemy"
        showThreat={false}
        onToggleThreat={vi.fn()}
      />
    )

    const banner = screen.getByRole('region', { name: '当前回合状态' })
    expect(within(banner).getByText('R 3')).toBeInTheDocument()
    expect(within(banner).getByText('轮到')).toBeInTheDocument()
    expect(within(banner).getByLabelText('当前行动者 洛林')).toHaveTextContent('洛林')
    expect(within(banner).getByRole('status', { name: '回合状态提示' })).toHaveTextContent('你的回合')
    expect(within(banner).getByRole('status', { name: '回合状态提示' })).toHaveTextContent(/正在控制 洛林/)
    expect(within(banner).getByLabelText('下一位行动 矿洞斥候')).toHaveTextContent('下个')
    expect(within(banner).getByLabelText('下一位行动 矿洞斥候')).toHaveClass('enemy')
  })

  it('shows blocked sync guidance before normal turn guidance', () => {
    render(
      <TurnBanner
        roundNumber={1}
        currentTurnName="洛林"
        currentTurnEntry={{ character_id: 'hero-1', name: '洛林', is_player: true }}
        currentTurnEntity={{ id: 'hero-1', name: '洛林', is_player: true }}
        isPlayerTurn={true}
        syncBlocked={true}
        showThreat={false}
        onToggleThreat={vi.fn()}
      />
    )

    const coach = screen.getByRole('status', { name: '回合状态提示' })
    expect(coach).toHaveTextContent('同步暂停')
    expect(coach).toHaveTextContent(/等待战斗同步恢复/)
    expect(screen.queryByText('你的回合')).not.toBeInTheDocument()
  })

  it('keeps the threat range toggle interactive', () => {
    const onToggleThreat = vi.fn()

    render(
      <TurnBanner
        roundNumber={1}
        currentTurnName="训练假人"
        currentTurnEntry={{ character_id: 'enemy-1', name: '训练假人', is_enemy: true }}
        currentTurnEntity={{ id: 'enemy-1', name: '训练假人', is_enemy: true }}
        showThreat={true}
        onToggleThreat={onToggleThreat}
      />
    )

    const button = screen.getByRole('button', { name: '切换敌人威胁区显示' })
    expect(button).toHaveClass('active')
    expect(button).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('敌方行动')).toBeInTheDocument()

    fireEvent.click(button)
    expect(onToggleThreat).toHaveBeenCalledTimes(1)
  })

  it('renders the player turn action coach when the player can act', () => {
    render(
      <TurnBanner
        roundNumber={2}
        currentTurnName="Hero"
        currentTurnEntry={{ character_id: 'hero-1', name: 'Hero', is_player: true }}
        currentTurnEntity={{ id: 'hero-1', name: 'Hero', is_player: true }}
        controlledCharacter={{ id: 'hero-1', name: 'Hero' }}
        isPlayerTurn={true}
        turnState={{ action_used: false, movement_max: 6, movement_used: 2, reaction_used: false }}
        skillBar={[{ k: 'atk', kind: 'attack', available: true }]}
        selectedTarget={null}
        showThreat={false}
        onToggleThreat={vi.fn()}
      />
    )

    const coach = screen.getByRole('list', { name: '回合行动提示' })
    expect(within(coach).getByRole('listitem', { name: '动作：选目标' })).toBeInTheDocument()
    expect(within(coach).getByRole('listitem', { name: '目标：选目标' })).toBeInTheDocument()
    expect(within(coach).getByRole('listitem', { name: '移动：4 格' })).toBeInTheDocument()
    expect(within(coach).getByRole('listitem', { name: '反应：保留' })).toBeInTheDocument()
  })

  it('surfaces selected target context in the action coach', () => {
    render(
      <TurnBanner
        roundNumber={2}
        currentTurnName="Hero"
        currentTurnEntry={{ character_id: 'hero-1', name: 'Hero', is_player: true }}
        currentTurnEntity={{ id: 'hero-1', name: 'Hero', is_player: true }}
        controlledCharacter={{ id: 'hero-1', name: 'Hero' }}
        isPlayerTurn={true}
        turnState={{ action_used: false, movement_max: 6, movement_used: 0, reaction_used: false }}
        skillBar={[{ k: 'atk', kind: 'attack', available: true }]}
        isRanged={true}
        selectedWeaponName="Longbow"
        selectedTarget="enemy-1"
        selectedTargetEntity={{ id: 'enemy-1', name: 'Goblin Boss', is_enemy: true, hp_current: 7, hp_max: 30, ac: 15 }}
        prediction={{
          hit_rate: 0.55,
          disadvantage: true,
          target_ac: 15,
          effective_target_ac: 20,
          cover_bonus: 5,
          cover_detail: { bonus: 5, raw_bonus: 5 },
          disadvantage_sources: ['attacker poisoned', 'target invisible'],
        }}
        showThreat={false}
        onToggleThreat={vi.fn()}
      />
    )

    const coach = screen.getByRole('list', { name: '回合行动提示' })
    expect(coach).toHaveTextContent('目标')
    expect(coach).toHaveTextContent('敌人 · Goblin Boss · 危急 · AC 15 · 命中 55% · 劣势 · 3/4 掩护 +5 AC · 有效 AC 20')
    expect(screen.getByTitle('敌人 · Goblin Boss · 危急 · AC 15 · 命中 55% · 劣势 · 3/4 掩护 +5 AC · 有效 AC 20')).toBeInTheDocument()
    expect(coach).toHaveTextContent('来源')
    expect(coach).toHaveTextContent('攻击者中毒 / 目标隐形')
    expect(screen.getByTitle('攻击者中毒 / 目标隐形')).toBeInTheDocument()
    expect(coach).toHaveTextContent('远程 · Longbow')
    expect(coach).toHaveTextContent('动作')
    expect(coach).toHaveTextContent('可用')
  })

  it('shows the allied target prompt while Help mode is active', () => {
    render(
      <TurnBanner
        roundNumber={2}
        currentTurnName="Hero"
        currentTurnEntry={{ character_id: 'hero-1', name: 'Hero', is_player: true }}
        currentTurnEntity={{ id: 'hero-1', name: 'Hero', is_player: true }}
        controlledCharacter={{ id: 'hero-1', name: 'Hero' }}
        isPlayerTurn={true}
        turnState={{ action_used: false, movement_max: 6, movement_used: 1, reaction_used: false }}
        skillBar={[{ k: 'help', label: '协助', kind: 'action', available: true }]}
        helpMode={true}
        showThreat={false}
        onToggleThreat={vi.fn()}
      />
    )

    const coach = screen.getByRole('list', { name: '回合行动提示' })
    expect(within(coach).getByRole('listitem', { name: '动作：选队友' })).toBeInTheDocument()
    expect(coach).toHaveTextContent('协助')
  })

  it('warns before ending when a bonus action is still available', () => {
    render(
      <TurnBanner
        roundNumber={2}
        currentTurnName="Hero"
        currentTurnEntry={{ character_id: 'hero-1', name: 'Hero', is_player: true }}
        currentTurnEntity={{ id: 'hero-1', name: 'Hero', is_player: true }}
        controlledCharacter={{ id: 'hero-1', name: 'Hero' }}
        isPlayerTurn={true}
        turnState={{
          action_used: true,
          bonus_action_used: false,
          movement_max: 6,
          movement_used: 6,
          reaction_used: false,
        }}
        skillBar={[{ k: 'offhand', label: '副手攻击', kind: 'bonus', available: true }]}
        showThreat={false}
        onToggleThreat={vi.fn()}
      />
    )

    const coach = screen.getByRole('list', { name: '回合行动提示' })
    expect(within(coach).getByRole('listitem', { name: '附赠：副手攻击' })).toBeInTheDocument()
    expect(within(coach).getByRole('listitem', { name: '结束：还有附赠' })).toBeInTheDocument()
  })
})
