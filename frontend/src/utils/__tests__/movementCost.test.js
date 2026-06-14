import { describe, expect, it } from 'vitest'
import { buildDifficultTerrainMovePreview, buildMovementPathCells } from '../movementCost'

describe('movementCost', () => {
  it('builds movement path cells from the actor position to the destination', () => {
    expect(buildMovementPathCells({ x: 5, y: 5 }, { x: 7, y: 5 })).toEqual([
      { key: '6_5', cell: '6_5', x: 6, y: 5 },
      { key: '7_5', cell: '7_5', x: 7, y: 5 },
    ])
  })

  it('explains entered difficult terrain extra movement cost', () => {
    const preview = buildDifficultTerrainMovePreview({
      actorPosition: { x: 5, y: 5 },
      destination: { x: 6, y: 5 },
      terrainDetails: {
        '6_5': { terrain: 'difficult', label: 'Mud slick' },
      },
      turnState: { movement_used: 1, movement_max: 6 },
    })

    expect(preview).toMatchObject({
      type: 'difficult_terrain',
      movementCost: 2,
      difficultExtra: 1,
      effectiveRemaining: 5,
      blockedReason: '',
    })
    expect(preview.cells).toEqual([{
      key: '6_5',
      terrain: 'difficult',
      label: 'Mud slick',
      extraCost: 1,
    }])
    expect(preview.notice).toContain('Mud slick')
  })

  it('blocks difficult terrain destinations that exceed remaining movement', () => {
    const preview = buildDifficultTerrainMovePreview({
      actorPosition: { x: 5, y: 5 },
      destination: { x: 6, y: 5 },
      gridData: {
        '6_5': { terrain: 'difficult_terrain', label: 'Thick rubble' },
      },
      turnState: { movement_used: 5, movement_max: 6 },
    })

    expect(preview.movementCost).toBe(2)
    expect(preview.blockedReason).toBeTruthy()
  })

  it('does not add difficult terrain extra cost after Mobile Dash', () => {
    const preview = buildDifficultTerrainMovePreview({
      actorPosition: { x: 5, y: 5 },
      destination: { x: 6, y: 5 },
      terrainDetails: {
        '6_5': { terrain: 'difficult', label: 'Mud slick' },
      },
      turnState: {
        movement_used: 5,
        movement_max: 6,
        mobile_ignores_difficult_terrain: true,
      },
    })

    expect(preview).toMatchObject({
      movementCost: 1,
      difficultExtra: 0,
      ignoresDifficultTerrain: true,
      effectiveRemaining: 1,
      blockedReason: '',
    })
    expect(preview.cells).toEqual([{
      key: '6_5',
      terrain: 'difficult',
      label: 'Mud slick',
      extraCost: 0,
    }])
  })
})
