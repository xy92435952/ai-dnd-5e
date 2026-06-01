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

  it('builds selected-location route summaries with gates and checks', () => {
    const map = getLocationGraphMap({
      current_location_id: 'yard',
      nodes: [
        { id: 'yard', name: 'Training Yard', visited: true },
        { id: 'armory', name: 'Armory', discovered: true },
        { id: 'tower', name: 'Watchtower', visited: true },
        { id: 'secret', name: 'Secret Vault', discovered: true },
      ],
      edges: [
        {
          id: 'yard-armory',
          from: 'yard',
          to: 'armory',
          type: 'locked',
          locked: true,
          requires_key: 'Bronze Key',
          check_type: 'thieves_tools',
          dc: 15,
        },
        {
          id: 'tower-yard',
          from: 'tower',
          to: 'yard',
          type: 'stairs',
          one_way: true,
        },
        {
          id: 'yard-secret',
          from: 'yard',
          to: 'secret',
          type: 'hidden',
          hidden: true,
        },
      ],
    })

    expect(map.currentNode.routes).toEqual([expect.objectContaining({
      id: 'yard-armory',
      destinationId: 'armory',
      destinationName: 'Armory',
      destinationVisited: false,
      label: 'locked',
      type: 'locked',
      locked: true,
      oneWay: false,
      requiresKey: 'Bronze Key',
      dc: 15,
      checkType: 'thieves_tools',
      tone: 'locked',
      guidance: 'Gated: needs Bronze Key or thieves tools DC 15',
    })])
    expect(map.nodes.find(node => node.id === 'tower').routes).toEqual([expect.objectContaining({
      destinationId: 'yard',
      oneWay: true,
      tone: 'one-way',
      guidance: 'One-way route',
    })])
  })

  it('surfaces public encounter environment pressure as aggregate tags', () => {
    const map = getLocationGraphMap({
      current_location_id: 'yard',
      nodes: [
        { id: 'yard', name: 'Training Yard', visited: true, encounter_template_ids: ['enc_yard'] },
      ],
      encounter_templates: [{
        id: 'enc_yard',
        location_id: 'yard',
        status: 'available',
        public: true,
        name: 'Yard Patrol',
        environment_pressure: {
          pressure: 'heavy',
          hazards: 1,
          objectives: 1,
          cover: 1,
          terrain: 1,
          authored_cells: 5,
        },
      }],
    })

    expect(map.currentNode.encounters[0]).toMatchObject({
      environmentPressure: 'heavy',
      environmentPressureTags: ['Env heavy', 'hazards 1', 'objectives 1', 'terrain 2', 'cells 5'],
    })
  })
})
