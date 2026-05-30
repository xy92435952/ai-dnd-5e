import { describe, expect, it } from 'vitest'
import { getLocationGraphMap, getLocationGraphSummary } from '../locationGraph'

describe('locationGraph', () => {
  it('summarizes only discovered locations and public routes', () => {
    expect(getLocationGraphSummary({
      current_location_id: 'yard',
      nodes: [
        { id: 'gate', name: 'Gatehouse', visited: true },
        { id: 'yard', name: 'Training Yard', description: 'Low walls.', visited: true, encounter_template_ids: ['enc_yard'] },
        { id: 'vault', name: 'Vault', visited: false },
      ],
      edges: [
        { from: 'gate', to: 'yard', type: 'sequence' },
        { from: 'yard', to: 'vault', type: 'sequence' },
      ],
      encounter_templates: [{
        id: 'enc_yard',
        location_id: 'yard',
        status: 'available',
        name: 'Construct Patrol',
        difficulty_hint: 'moderate',
        enemy_names: ['Clockwork Construct'],
      }],
    })).toEqual({
      currentName: 'Training Yard',
      currentDescription: 'Low walls.',
      visitedCount: 2,
      totalCount: 2,
      linkedNames: ['Gatehouse'],
      encounterCount: 0,
      nextEncounterName: '',
      nextEncounterDifficulty: '',
      nextEncounterEnemies: [],
    })
  })

  it('returns null for missing graph data', () => {
    expect(getLocationGraphSummary(null)).toBe(null)
    expect(getLocationGraphSummary({ nodes: [] })).toBe(null)
  })

  it('builds a map model without hidden future nodes or hidden encounter markers', () => {
    const map = getLocationGraphMap({
      current_location_id: 'yard',
      selected_encounter_template_id: 'enc_yard',
      nodes: [
        { id: 'gate', name: 'Gatehouse', visited: true },
        { id: 'yard', name: 'Training Yard', visited: true, encounter_template_ids: ['enc_yard'] },
        { id: 'vault', name: 'Vault', visited: false },
      ],
      edges: [
        { from: 'gate', to: 'yard', type: 'sequence' },
        { from: 'yard', to: 'vault', type: 'locked', locked: true },
        { from: 'yard', to: 'secret', type: 'hidden', hidden: true, one_way: true },
      ],
      encounter_templates: [
        {
          id: 'enc_yard',
          location_id: 'yard',
          status: 'available',
          name: 'Yard Patrol',
          xp_budget: 300,
          terrain: ['balcony'],
          objectives: ['Hold the door'],
          hazards: ['falling stone'],
          enemy_roles: [{ name: 'Yard Guard', role: 'defender' }],
        },
      ],
    })

    expect(map.currentNode.name).toBe('Training Yard')
    expect(map.visitedCount).toBe(2)
    expect(map.totalCount).toBe(2)
    expect(map.encounterCount).toBe(0)
    expect(map.nodes.map(node => node.id)).toEqual(['gate', 'yard'])
    expect(map.nodes.find(node => node.id === 'yard')).toEqual(expect.objectContaining({
      current: true,
      encounterCount: 0,
      encounterNames: [],
    }))
    expect(map.edges.map(edge => [edge.from, edge.to])).toEqual([['gate', 'yard']])
    expect(map.edges.find(edge => edge.to === 'vault')).toBeUndefined()
  })
})
