import { describe, expect, it } from 'vitest'
import { buildGrappleDragMovePreview, buildGrappleDragStatus } from '../grappleDrag'

describe('grappleDrag', () => {
  const entities = {
    hero: { id: 'hero', name: 'Hero' },
    'enemy-1': {
      id: 'enemy-1',
      name: 'Dragged Duelist',
      conditions: ['grappled'],
      condition_durations: { grappled: { source_id: 'hero' } },
    },
    'enemy-2': {
      id: 'enemy-2',
      name: 'Other Grapple',
      conditions: ['grappled'],
      condition_durations: { grappled: { source_id: 'ally' } },
    },
    'enemy-3': {
      id: 'enemy-3',
      name: 'Too Far',
      conditions: ['grappled'],
      condition_durations: { grappled: { source_id: 'hero' } },
    },
  }
  const entityPositions = {
    hero: { x: 5, y: 5 },
    'enemy-1': { x: 6, y: 5 },
    'enemy-2': { x: 5, y: 6 },
    'enemy-3': { x: 9, y: 5 },
  }

  it('detects adjacent targets grappled by the active actor', () => {
    const status = buildGrappleDragStatus({
      actorId: 'hero',
      actorPosition: entityPositions.hero,
      entities,
      entityPositions,
    })

    expect(status).toMatchObject({
      type: 'grapple_drag',
      summary: 'Dragged Duelist',
      title: '拖拽 Dragged Duelist · 移动消耗翻倍',
    })
    expect(status.targets.map(target => target.id)).toEqual(['enemy-1'])
  })

  it('builds doubled movement cost notices and blocks destinations beyond remaining movement', () => {
    const legal = buildGrappleDragMovePreview({
      actorId: 'hero',
      actorPosition: entityPositions.hero,
      destination: { x: 7, y: 5 },
      entities,
      entityPositions,
      turnState: { movement_used: 0, movement_max: 6 },
    })

    expect(legal).toMatchObject({
      steps: 2,
      movementCost: 4,
      remaining: 6,
      effectiveRemaining: 6,
      blockedReason: '',
      notice: '拖拽 Dragged Duelist：移动消耗翻倍，此移动消耗 4 格（剩余 6 格）',
    })

    const blocked = buildGrappleDragMovePreview({
      actorId: 'hero',
      actorPosition: entityPositions.hero,
      destination: { x: 9, y: 5 },
      entities,
      entityPositions,
      turnState: { movement_used: 0, movement_max: 6 },
    })

    expect(blocked).toMatchObject({
      steps: 4,
      movementCost: 8,
      blockedReason: '拖拽 Dragged Duelist 需要 8 格移动力，当前剩余 6 格',
    })
  })

  it('accounts for movement already reserved by standing up from prone', () => {
    const preview = buildGrappleDragMovePreview({
      actorId: 'hero',
      actorPosition: entityPositions.hero,
      destination: { x: 7, y: 5 },
      entities,
      entityPositions,
      turnState: { movement_used: 0, movement_max: 6 },
      reservedMovementCost: 3,
    })

    expect(preview).toMatchObject({
      movementCost: 4,
      effectiveRemaining: 3,
      blockedReason: '拖拽 Dragged Duelist 需要 4 格移动力，起身后剩余 3 格',
    })
  })
})
