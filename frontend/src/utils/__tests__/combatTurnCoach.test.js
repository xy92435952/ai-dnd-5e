import { describe, expect, it } from 'vitest'
import { buildCombatTurnCoach } from '../combatTurnCoach'

describe('buildCombatTurnCoach', () => {
  it('prioritizes websocket sync blocks over turn ownership', () => {
    expect(buildCombatTurnCoach({
      currentTurnEntry: { character_id: 'hero-1', name: '洛林', is_player: true },
      isPlayerTurn: true,
      syncBlocked: true,
    })).toEqual({
      tone: 'blocked',
      label: '同步暂停',
      detail: '等待战斗同步恢复后再操作，避免使用过期回合状态。',
    })
  })

  it('explains the active player turn', () => {
    const coach = buildCombatTurnCoach({
      currentTurnEntry: { character_id: 'hero-1', name: '洛林', is_player: true },
      currentTurnEntity: { id: 'hero-1', name: '洛林', is_player: true },
      controlledCharacter: { id: 'hero-1', name: '洛林' },
      isPlayerTurn: true,
    })

    expect(coach.tone).toBe('active')
    expect(coach.label).toBe('你的回合')
    expect(coach.detail).toContain('正在控制 洛林')
  })

  it('explains a multiplayer teammate turn with controller context', () => {
    const coach = buildCombatTurnCoach({
      currentTurnEntry: { character_id: 'hero-2', name: '莉亚', is_player: true },
      currentTurnEntity: { id: 'hero-2', name: '莉亚', is_player: true },
      room: { is_multiplayer: true },
      controllerName: 'Ally',
    })

    expect(coach.tone).toBe('watching')
    expect(coach.label).toBe('等待队友')
    expect(coach.detail).toBe('莉亚 由 Ally 控制。你可以观察战场、查看日志，或准备可能出现的反应。')
  })

  it('marks enemy turns as danger', () => {
    const coach = buildCombatTurnCoach({
      currentTurnEntry: { character_id: 'goblin-1', name: '矿洞斥候', is_enemy: true },
      currentTurnEntity: { id: 'goblin-1', name: '矿洞斥候', is_enemy: true },
    })

    expect(coach).toEqual({
      tone: 'danger',
      label: '敌方行动',
      detail: '矿洞斥候 正在行动。留意反应提示、伤害结算和位置变化。',
    })
  })

  it('adds tactical role context to enemy turn guidance', () => {
    const coach = buildCombatTurnCoach({
      currentTurnEntry: { character_id: 'goblin-1', name: '矿洞斥候', is_enemy: true },
      currentTurnEntity: { id: 'goblin-1', name: '矿洞斥候', is_enemy: true, tactical_role: 'skirmisher' },
    })

    expect(coach).toEqual({
      tone: 'danger',
      label: '敌方行动',
      detail: '矿洞斥候（游击）正在行动。倾向攻击边缘或后排，并在安全时撤步拉开距离。 留意反应提示、伤害结算和位置变化。',
    })
  })

  it('treats non-player allies as companion turns', () => {
    const coach = buildCombatTurnCoach({
      currentTurnEntry: { character_id: 'ally-1', name: '铁砧' },
      currentTurnEntity: { id: 'ally-1', name: '铁砧', is_enemy: false },
    })

    expect(coach.tone).toBe('watching')
    expect(coach.label).toBe('队友行动')
    expect(coach.detail).toBe('铁砧 正在行动。你可以观察战场并准备下一步。')
  })
})
