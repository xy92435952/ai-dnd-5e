import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { DEFAULT_SKILL_BAR } from '../../data/combat'
import { useCombatDerivedState } from '../useCombatDerivedState'

describe('useCombatDerivedState', () => {
  const combat = {
    current_turn_index: 0,
    turn_order: [
      { character_id: 'player', name: 'Hero', is_player: true, initiative: 17 },
      { character_id: 'enemy', name: 'Goblin', is_enemy: true, initiative: 8 },
    ],
    entity_positions: {
      player: { x: 5, y: 5 },
      enemy: { x: 6, y: 5 },
    },
    entities: {
      player: { id: 'player', name: 'Hero', hp_current: 10, hp_max: 12, is_enemy: false },
      enemy: { id: 'enemy', name: 'Goblin', hp_current: 4, hp_max: 8, is_enemy: true },
    },
    grid_data: {
      '1_1': 'wall',
      '2_2': 'hazard',
    },
  }

  it('聚合 Combat 页面需要的派生展示数据', () => {
    const { result } = renderHook(() => useCombatDerivedState({
      combat,
      room: {
        members: [{ character_id: 'player', display_name: 'Alice' }],
      },
      myCharacterId: 'player',
      playerId: 'player',
      selectedTarget: 'enemy',
      showThreat: true,
      aoePreview: { radius: 1 },
      aoeHover: '6_5',
      aoeLockedCenter: null,
      spells: [
        { name: 'Magic Missile', classes: ['Wizard'] },
        { name: 'Cure Wounds', classes: ['Cleric'] },
      ],
      playerKnownSpells: ['Magic Missile'],
      playerCantrips: [],
      playerClass: 'Wizard',
      skillBarV10: null,
      gridWidth: 20,
      gridHeight: 12,
      viewWidth: 12,
      viewHeight: 8,
    }))

    expect(result.current.entities.enemy.name).toBe('Goblin')
    expect(result.current.playerPos).toEqual({ x: 5, y: 5 })
    expect(result.current.controlledCharacter).toBe(combat.entities.player)
    expect(result.current.cam).toEqual({ x0: 0, y0: 1 })
    expect(result.current.walls.has('1_1')).toBe(true)
    expect(result.current.hazards.has('2_2')).toBe(true)
    expect(result.current.selectedTargetEntity.name).toBe('Goblin')
    expect(result.current.initiativeChips).toHaveLength(2)
    expect(result.current.isPlayerTurn).toBe(true)
    expect(result.current.canActThisTurn).toBe(true)
    expect(result.current.isMyTurnMP).toBe(true)
    expect(result.current.currentTurnLabel).toBe('当前回合：Alice（Hero）')
    expect(result.current.playerAvailableSpells.map(s => s.name)).toEqual(['Magic Missile'])
    expect(result.current.skillBar).toBe(DEFAULT_SKILL_BAR)
    expect(result.current.threatCells.has('5_5')).toBe(true)
    expect(result.current.aoeCells.center).toBe('6_5')
  })

  it('AoE locked center takes priority over transient hover cells', () => {
    const { result } = renderHook(() => useCombatDerivedState({
      combat,
      room: null,
      myCharacterId: null,
      playerId: 'player',
      selectedTarget: null,
      showThreat: false,
      aoePreview: { radius: 1 },
      aoeHover: '6_5',
      aoeLockedCenter: '8_8',
      spells: [],
      playerKnownSpells: [],
      playerCantrips: [],
      playerClass: '',
      skillBarV10: [],
      gridWidth: 20,
      gridHeight: 12,
      viewWidth: 12,
      viewHeight: 8,
    }))

    expect(result.current.aoeCells.center).toBe('8_8')
  })

  it('combat 为空时返回安全兜底', () => {
    const { result } = renderHook(() => useCombatDerivedState({
      combat: null,
      room: null,
      myCharacterId: null,
      playerId: null,
      selectedTarget: null,
      showThreat: false,
      aoePreview: null,
      aoeHover: null,
      spells: [],
      playerKnownSpells: [],
      playerCantrips: [],
      playerClass: '',
      skillBarV10: [],
      gridWidth: 20,
      gridHeight: 12,
      viewWidth: 12,
      viewHeight: 8,
    }))

    expect(result.current.entities).toEqual({})
    expect(result.current.entityPositions).toEqual({})
    expect(result.current.currentTurnEntry).toBeUndefined()
    expect(result.current.controlledCharacter).toBeNull()
    expect(result.current.isPlayerTurn).toBe(false)
    expect(result.current.canActThisTurn).toBe(false)
    expect(result.current.isMyTurnMP).toBe(true)
    expect(result.current.currentTurnLabel).toBe('')
  })

  it('多人房间中队友回合仍是玩家回合，但当前用户不可主动行动', () => {
    const { result } = renderHook(() => useCombatDerivedState({
      combat,
      room: {
        members: [{ character_id: 'player', display_name: 'Alice' }],
      },
      myCharacterId: 'other-player',
      playerId: 'other-player',
      selectedTarget: 'enemy',
      showThreat: false,
      aoePreview: null,
      aoeHover: null,
      spells: [],
      playerKnownSpells: [],
      playerCantrips: [],
      playerClass: '',
      skillBarV10: [],
      gridWidth: 20,
      gridHeight: 12,
      viewWidth: 12,
      viewHeight: 8,
    }))

    expect(result.current.isPlayerTurn).toBe(true)
    expect(result.current.isMyTurnMP).toBe(false)
    expect(result.current.canActThisTurn).toBe(false)
  })
})
