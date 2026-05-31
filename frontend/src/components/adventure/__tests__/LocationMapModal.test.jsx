import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import LocationMapModal from '../LocationMapModal'

const GRAPH = {
  current_location_id: 'yard',
  nodes: [
    { id: 'gate', name: 'Gatehouse', description: 'Stone entry.', visited: true },
    { id: 'yard', name: 'Training Yard', description: 'Low walls.', visited: true, encounter_template_ids: ['enc_yard'] },
    { id: 'vault', name: 'Vault', description: 'Sealed door.', visited: false },
  ],
  edges: [
    { from: 'gate', to: 'yard', type: 'sequence' },
    { from: 'yard', to: 'vault', type: 'locked', locked: true },
  ],
  encounter_templates: [{
    id: 'enc_yard',
    location_id: 'yard',
    status: 'available',
    name: 'Construct Patrol',
    xp_budget: 300,
    difficulty_hint: 'moderate',
    enemy_names: ['Clockwork Construct'],
    enemy_roles: [{ name: 'Clockwork Construct', role: 'defender' }],
    terrain: ['low walls'],
    cover: ['barricades'],
    objectives: ['Hold the yard'],
    hazards: ['sparking conduit'],
    reward_hints: ['Gate Token'],
    tactics: 'Force intruders into the open.',
  }],
}

describe('LocationMapModal', () => {
  it('renders the current map without exposing hidden future locations or encounter details', () => {
    render(<LocationMapModal graph={GRAPH} onClose={() => {}} />)

    expect(screen.getByRole('heading', { name: 'Map' })).toBeInTheDocument()
    expect(screen.getAllByText('Training Yard').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Location map')).toBeInTheDocument()
    expect(screen.getByLabelText('Training Yard current visited')).toBeInTheDocument()
    expect(screen.queryByLabelText('Vault unvisited')).not.toBeInTheDocument()

    const summary = screen.getByLabelText('Map summary')
    expect(within(summary).getAllByText('2').length).toBeGreaterThanOrEqual(2)
    expect(screen.queryByText('encounters')).not.toBeInTheDocument()

    expect(screen.getByRole('heading', { name: 'Exits' })).toBeInTheDocument()
    const routeList = screen.getByRole('list')
    expect(within(routeList).getByText('Gatehouse')).toBeInTheDocument()
    expect(within(routeList).getByText('sequence')).toBeInTheDocument()
    expect(screen.queryByText('locked')).not.toBeInTheDocument()
    expect(screen.queryByText('Construct Patrol')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Selected encounter templates')).not.toBeInTheDocument()
    expect(screen.queryByText('moderate')).not.toBeInTheDocument()
    expect(screen.queryByText('300 XP')).not.toBeInTheDocument()
    expect(screen.queryByText('low walls')).not.toBeInTheDocument()
    expect(screen.queryByText('sparking conduit')).not.toBeInTheDocument()
    expect(screen.queryByText('Gate Token')).not.toBeInTheDocument()
    expect(screen.queryByText('Force intruders into the open.')).not.toBeInTheDocument()
  })

  it('selects a different discovered location without changing the current marker', () => {
    render(<LocationMapModal graph={GRAPH} onClose={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Gatehouse visited' }))

    expect(screen.getByRole('button', { name: 'Gatehouse visited' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Selected')).toBeInTheDocument()
    expect(screen.getByText('Stone entry.')).toBeInTheDocument()
  })

  it('shows selected-location exit gates without revealing hidden routes', () => {
    render(<LocationMapModal graph={{
      current_location_id: 'yard',
      nodes: [
        { id: 'yard', name: 'Training Yard', visited: true },
        { id: 'armory', name: 'Armory', discovered: true },
        { id: 'secret', name: 'Secret Vault', visited: false },
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
        { id: 'yard-secret', from: 'yard', to: 'secret', type: 'hidden', hidden: true },
      ],
    }} onClose={() => {}} />)

    const routeList = screen.getByRole('list')
    expect(within(routeList).getByText('Armory')).toBeInTheDocument()
    expect(within(routeList).getByText('locked')).toBeInTheDocument()
    expect(within(routeList).getByText('key: Bronze Key')).toBeInTheDocument()
    expect(within(routeList).getByText('thieves_tools DC 15')).toBeInTheDocument()
    expect(screen.queryByText('Secret Vault')).not.toBeInTheDocument()
  })

  it('does not surface hidden encounter selection controls', () => {
    const onSelectEncounter = vi.fn()
    render(<LocationMapModal graph={GRAPH} onSelectEncounter={onSelectEncounter} onClose={() => {}} />)

    expect(screen.queryByRole('button', { name: 'Set active' })).not.toBeInTheDocument()
    expect(onSelectEncounter).not.toHaveBeenCalled()
  })

  it('closes through the header button', () => {
    const onClose = vi.fn()
    render(<LocationMapModal graph={GRAPH} onClose={onClose} />)

    fireEvent.click(screen.getByRole('button', { name: 'Close map' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
