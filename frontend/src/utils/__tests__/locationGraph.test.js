import { describe, expect, it } from 'vitest'
import { getLocationGraphMap, getLocationGraphSummary } from '../locationGraph'

describe('locationGraph', () => {
  it('summarizes the current location and linked nodes', () => {
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
      totalCount: 3,
      linkedNames: ['Gatehouse', 'Vault'],
      encounterCount: 1,
      nextEncounterName: 'Construct Patrol',
      nextEncounterDifficulty: 'moderate',
      nextEncounterEnemies: ['Clockwork Construct'],
    })
  })

  it('returns null for missing graph data', () => {
    expect(getLocationGraphSummary(null)).toBe(null)
    expect(getLocationGraphSummary({ nodes: [] })).toBe(null)
  })

  it('builds a map model with route state and encounter markers', () => {
    const map = getLocationGraphMap({
      current_location_id: 'vault',
      selected_encounter_template_id: 'enc_vault',
      nodes: [
        { id: 'gate', name: 'Gatehouse', visited: true },
        { id: 'yard', name: 'Training Yard', visited: true },
        { id: 'vault', name: 'Vault', visited: true, encounter_template_ids: ['enc_vault'] },
      ],
      edges: [
        { from: 'gate', to: 'yard', type: 'sequence' },
        { from: 'yard', to: 'vault', type: 'locked', locked: true },
        { from: 'vault', to: 'gate', type: 'hidden', hidden: true, one_way: true },
      ],
      encounter_templates: [
        {
          id: 'enc_vault',
          location_id: 'vault',
          status: 'available',
          name: 'Vault Guard',
          xp_budget: 300,
          terrain: ['balcony'],
          objectives: ['Hold the door'],
          hazards: ['falling stone'],
          enemy_roles: [{ name: 'Vault Guard', role: 'defender' }],
        },
        { id: 'enc_done', location_id: 'yard', status: 'resolved', name: 'Old Patrol' },
      ],
    })

    expect(map.currentNode.name).toBe('Vault')
    expect(map.visitedCount).toBe(3)
    expect(map.encounterCount).toBe(1)
    expect(map.nodes.find(node => node.id === 'vault')).toEqual(expect.objectContaining({
      current: true,
      encounterCount: 1,
      encounterNames: ['Vault Guard'],
    }))
    expect(map.nodes.find(node => node.id === 'vault').encounters[0]).toEqual(expect.objectContaining({
      name: 'Vault Guard',
      xpBudget: 300,
      terrain: ['balcony'],
      objectives: ['Hold the door'],
      hazards: ['falling stone'],
      enemyRoles: [{ name: 'Vault Guard', role: 'defender' }],
      selected: true,
    }))
    expect(map.edges.find(edge => edge.to === 'vault')).toEqual(expect.objectContaining({
      locked: true,
      label: 'locked',
    }))
    expect(map.edges.find(edge => edge.from === 'vault')).toEqual(expect.objectContaining({
      hidden: true,
      oneWay: true,
    }))
  })
})
