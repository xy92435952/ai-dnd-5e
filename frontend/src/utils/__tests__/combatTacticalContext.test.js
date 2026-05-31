import { describe, expect, it } from 'vitest'
import { buildCombatTacticalContext } from '../combatTacticalContext'

describe('combat tactical context', () => {
  it('summarizes encounter template, grid terrain, balance, and staged enemies', () => {
    const context = buildCombatTacticalContext({
      combat: {
        grid_data: {
          _encounter_template: {
            name: 'Rune Hall Encounter',
            objectives: [{ name: 'Seal the rift' }],
            terrain: [{ name: 'oil slick', terrain: 'difficult' }],
            cover: [{ name: 'altar', cover_level: 'half' }],
            hazards: [{ name: 'fire jet', damage_dice: '2d6' }],
          },
          '1_1': { terrain: 'total_cover' },
          '2_2': { terrain: 'hazard' },
          '3_3': { objective: true },
          '4_4': { terrain: 'difficult_terrain' },
        },
      },
      session: {
        game_state: {
          encounter_balance: { difficulty: 'hard', adjusted_xp: 75 },
          last_encounter_template_balance: {
            target_difficulty: 'medium',
            environment_adjusted_difficulty: 'deadly',
            environment_pressure: { pressure: 'heavy' },
            roster_tuning: { staged_count: 2 },
          },
        },
      },
    })

    expect(context.hasContext).toBe(true)
    expect(context.title).toBe('Rune Hall Encounter')
    expect(context.objectives).toEqual(['Seal the rift'])
    expect(context.terrain).toEqual(['oil slick'])
    expect(context.cover).toEqual(['altar'])
    expect(context.hazards).toEqual(['fire jet'])
    expect(context.detailGroups).toEqual([
      { key: 'objective', label: 'OBJ', value: 'Seal the rift · 1 cell', title: 'Seal the rift' },
      { key: 'cover', label: 'COV', value: 'altar · 1 cell', title: 'altar' },
      { key: 'terrain', label: 'TER', value: 'oil slick · 1 cell', title: 'oil slick' },
      { key: 'hazard', label: 'HZD', value: 'fire jet · 1 cell', title: 'fire jet' },
    ])
    expect(context.difficulty).toBe('hard')
    expect(context.targetDifficulty).toBe('medium')
    expect(context.environmentPressure).toBe('heavy')
    expect(context.environmentAdjustedDifficulty).toBe('deadly')
    expect(context.stagedCount).toBe(2)
    expect(context.counts).toMatchObject({ cover: 1, difficult: 1, hazard: 1, objective: 1 })
  })
})
