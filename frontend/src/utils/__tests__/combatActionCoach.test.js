import { describe, expect, it } from 'vitest'
import { buildCombatActionCoach } from '../combatActionCoach'

describe('buildCombatActionCoach', () => {
  it('stays hidden outside actionable player turns', () => {
    expect(buildCombatActionCoach({ isPlayerTurn: false })).toEqual({ visible: false, items: [] })
    expect(buildCombatActionCoach({ isPlayerTurn: true, syncBlocked: true })).toEqual({ visible: false, items: [] })
    expect(buildCombatActionCoach({ isPlayerTurn: true, isProcessing: true })).toEqual({ visible: false, items: [] })
  })

  it('prompts for a target before target-based actions', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      turnState: { action_used: false, movement_max: 6, movement_used: 2, reaction_used: false },
      skillBar: [{ k: 'atk', kind: 'attack', available: true }],
      selectedTarget: null,
    })

    expect(coach.visible).toBe(true)
    expect(coach.items).toContainEqual({ key: 'action', label: 'Action', value: 'Pick target', tone: 'warn' })
    expect(coach.items).toContainEqual({ key: 'target', label: 'Target', value: 'Pick target', tone: 'warn' })
    expect(coach.items).toContainEqual({ key: 'move', label: 'Move', value: '4 sq', tone: 'ready' })
    expect(coach.items).toContainEqual({ key: 'reaction', label: 'Reaction', value: 'Held', tone: 'ready' })
  })

  it('summarizes the selected target with AC and hit chance', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      turnState: { action_used: false, movement_max: 6, movement_used: 0, reaction_used: false },
      skillBar: [{ k: 'atk', kind: 'attack', available: true }],
      selectedTarget: 'enemy-1',
      selectedTargetEntity: { id: 'enemy-1', name: 'Goblin Boss', ac: 15 },
      prediction: { hit_rate: 0.65 },
    })

    expect(coach.items).toContainEqual({
      key: 'target',
      label: 'Target',
      value: 'Goblin Boss · AC 15 · Hit 65%',
      tone: 'ready',
    })
    expect(coach.items).toContainEqual({ key: 'action', label: 'Action', value: 'Ready', tone: 'ready' })
  })

  it('summarizes spent action resources and bonus availability', () => {
    const coach = buildCombatActionCoach({
      isPlayerTurn: true,
      turnState: {
        action_used: true,
        bonus_action_used: false,
        reaction_used: true,
        movement_max: 6,
        movement_used: 6,
      },
      skillBar: [{ k: 'off_attack', kind: 'bonus', available: true }],
      selectedTarget: 'enemy-1',
    })

    expect(coach.items).toContainEqual({ key: 'action', label: 'Action', value: 'Spent', tone: 'spent' })
    expect(coach.items).toContainEqual({ key: 'bonus', label: 'Bonus', value: 'Ready', tone: 'ready' })
    expect(coach.items).toContainEqual({ key: 'move', label: 'Move', value: '0 sq', tone: 'spent' })
    expect(coach.items).toContainEqual({ key: 'reaction', label: 'Reaction', value: 'Spent', tone: 'spent' })
  })
})
