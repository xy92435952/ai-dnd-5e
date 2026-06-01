import { describe, expect, it } from 'vitest'
import { buildCombatTacticalContext, formatTacticalRole, getTacticalRoleHint } from '../combatTacticalContext'

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
            enemy_roles: [
              { name: 'Rune Guard', role: 'defender' },
              { name: 'Spark Adept', role: 'controller' },
              { name: 'Spark Adept', role: 'controller' },
            ],
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
    expect(context.roleSummary).toBe('防卫 x1 / 控制 x2')
    expect(context.enemyRoles.map(role => role.label)).toEqual([
      'Rune Guard: 防卫',
      'Spark Adept: 控制',
      'Spark Adept: 控制',
    ])
    expect(context.detailGroups).toEqual([
      { key: 'roles', label: '敌职', value: '防卫 x1 / 控制 x2', title: '防卫 x1 / 控制 x2' },
      { key: 'objective', label: '目标', value: 'Seal the rift · 1 格', title: 'Seal the rift' },
      { key: 'cover', label: '掩护', value: 'altar · 1 格', title: 'altar' },
      { key: 'terrain', label: '地形', value: 'oil slick · 1 格', title: 'oil slick' },
      { key: 'hazard', label: '危险', value: 'fire jet · 1 格', title: 'fire jet' },
    ])
    expect(context.difficulty).toBe('hard')
    expect(context.targetDifficulty).toBe('medium')
    expect(context.environmentPressure).toBe('heavy')
    expect(context.environmentAdjustedDifficulty).toBe('deadly')
    expect(context.stagedCount).toBe(2)
    expect(context.counts).toMatchObject({ cover: 1, difficult: 1, hazard: 1, objective: 1 })
  })

  it('formats tactical role labels and player-facing hints', () => {
    expect(formatTacticalRole('skirmisher')).toBe('游击')
    expect(formatTacticalRole('defender')).toBe('防卫')
    expect(formatTacticalRole('unknown')).toBe('unknown')
    expect(getTacticalRoleHint('skirmisher')).toBe('倾向攻击边缘或后排，并在安全时撤步拉开距离。')
    expect(getTacticalRoleHint('defender')).toBe('会贴近盟友保护目标，可能用反应制造劣势。')
    expect(getTacticalRoleHint('unknown')).toBe('')
  })
})
