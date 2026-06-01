import { describe, expect, it } from 'vitest'
import { buildEnemyInspectModel, isEnemyDetailVisible } from '../enemyInspect'

describe('enemyInspect', () => {
  it('hides unrevealed enemy details while keeping an inspect model', () => {
    const model = buildEnemyInspectModel({
      is_enemy: true,
      name: 'Bandit Captain',
      cr: '2',
      speed: 30,
      resistances: ['poison'],
      actions: [{ name: 'Scimitar' }],
      tactics: 'Flank isolated targets.',
    })

    expect(model.revealLabel).toBe('部分')
    expect(model.rows.find(row => row.label === 'CR')).toMatchObject({
      value: '未知',
      hidden: true,
    })
    expect(model.actions).toBe('未知')
    expect(model.tacticsHidden).toBe(true)
  })

  it('reveals selected details from perception or investigation state', () => {
    const entity = {
      is_enemy: true,
      cr: '1',
      speed: 40,
      resistances: ['fire'],
      immunities: [],
      actions: [{ name: 'Bite' }, { name: 'Claw' }],
      revealed_stats: ['cr', 'speed', 'resistances', 'actions'],
    }
    const model = buildEnemyInspectModel(entity)

    expect(isEnemyDetailVisible(entity, 'speed')).toBe(true)
    expect(model.rows.find(row => row.label === 'CR')).toMatchObject({ value: '1', hidden: false })
    expect(model.rows.find(row => row.label === '抗性')).toMatchObject({ value: 'fire', hidden: false })
    expect(model.rows.find(row => row.label === '免疫')).toMatchObject({ value: '未知', hidden: true })
    expect(model.actions).toBe('Bite / Claw')
  })

  it('shows all stat blocks once an enemy is identified', () => {
    const model = buildEnemyInspectModel({
      is_enemy: true,
      identified: true,
      cr: '1/2',
      speed: 30,
      vulnerabilities: ['radiant'],
      condition_immunities: ['charmed'],
      special_abilities: [{ name: 'Pack Tactics' }],
      tactics: 'Focus wounded targets.',
    })

    expect(model.revealLabel).toBe('已识别')
    expect(model.rows.find(row => row.label === '易伤').value).toBe('radiant')
    expect(model.rows.find(row => row.label === '状态免疫').value).toBe('charmed')
    expect(model.traits).toBe('Pack Tactics')
    expect(model.tactics).toBe('Focus wounded targets.')
  })

  it('does not reveal stat blocks from an inspect attempt alone', () => {
    const model = buildEnemyInspectModel({
      is_enemy: true,
      knowledge_state: {
        inspected: true,
        last_inspect: { success: false },
      },
      cr: '5',
      actions: [{ name: 'Claw' }],
      tactics: 'Punish isolated targets.',
    })

    expect(model.revealLabel).toBe('部分')
    expect(model.rows.find(row => row.label === 'CR')).toMatchObject({
      value: '未知',
      hidden: true,
    })
    expect(model.actions).toBe('未知')
    expect(model.tactics).toBe('未知')
  })
})
