import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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
        showThreat={false}
        onToggleThreat={vi.fn()}
      />
    )

    expect(screen.getByText('R 3')).toBeInTheDocument()
    expect(screen.getByText('轮到')).toBeInTheDocument()
    expect(screen.getByText('洛林')).toBeInTheDocument()
    expect(screen.getByText('你的回合')).toBeInTheDocument()
    expect(screen.getByText(/正在控制 洛林/)).toBeInTheDocument()
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

    expect(screen.getByText('同步暂停')).toBeInTheDocument()
    expect(screen.getByText(/等待战斗同步恢复/)).toBeInTheDocument()
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

    const button = screen.getByRole('button', { name: /威胁区/ })
    expect(button).toHaveClass('active')
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

    const coach = screen.getByLabelText('Turn action coach')
    expect(coach).toHaveTextContent('Action')
    expect(coach).toHaveTextContent('Pick target')
    expect(coach).toHaveTextContent('Target')
    expect(coach).toHaveTextContent('Move')
    expect(coach).toHaveTextContent('4 sq')
    expect(coach).toHaveTextContent('Reaction')
    expect(coach).toHaveTextContent('Held')
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
        selectedTarget="enemy-1"
        selectedTargetEntity={{ id: 'enemy-1', name: 'Goblin Boss', ac: 15 }}
        prediction={{ hit_rate: 0.65 }}
        showThreat={false}
        onToggleThreat={vi.fn()}
      />
    )

    const coach = screen.getByLabelText('Turn action coach')
    expect(coach).toHaveTextContent('Target')
    expect(coach).toHaveTextContent('Goblin Boss · AC 15 · Hit 65%')
    expect(coach).toHaveTextContent('Action')
    expect(coach).toHaveTextContent('Ready')
  })
})
