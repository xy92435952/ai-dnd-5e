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
  it('renders the current map, route states, and encounter markers', () => {
    render(<LocationMapModal graph={GRAPH} onClose={() => {}} />)

    expect(screen.getByRole('heading', { name: 'Map' })).toBeInTheDocument()
    expect(screen.getAllByText('Training Yard').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Location map')).toBeInTheDocument()
    expect(screen.getByLabelText('Training Yard current visited')).toBeInTheDocument()
    expect(screen.getByLabelText('Vault unvisited')).toBeInTheDocument()

    const summary = screen.getByLabelText('Map summary')
    expect(within(summary).getByText('2')).toBeInTheDocument()
    expect(within(summary).getByText('3')).toBeInTheDocument()
    expect(within(summary).getByText('1')).toBeInTheDocument()

    expect(screen.getByText(/Training Yard - Vault/)).toBeInTheDocument()
    expect(screen.getByText('locked')).toBeInTheDocument()
    expect(screen.getAllByText('Construct Patrol').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Selected encounter templates')).toBeInTheDocument()
    expect(screen.getByText('moderate')).toBeInTheDocument()
    expect(screen.getByText('300 XP')).toBeInTheDocument()
    expect(screen.getByText('low walls')).toBeInTheDocument()
    expect(screen.getByText('sparking conduit')).toBeInTheDocument()
    expect(screen.getByText('Gate Token')).toBeInTheDocument()
    expect(screen.getByText('Force intruders into the open.')).toBeInTheDocument()
  })

  it('selects a different location without changing the current marker', () => {
    render(<LocationMapModal graph={GRAPH} onClose={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Gatehouse visited' }))

    expect(screen.getByRole('button', { name: 'Gatehouse visited' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Selected')).toBeInTheDocument()
    expect(screen.getByText('Stone entry.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Selected encounter templates')).not.toBeInTheDocument()
  })

  it('can request an active encounter template selection', () => {
    const onSelectEncounter = vi.fn()
    render(<LocationMapModal graph={GRAPH} onSelectEncounter={onSelectEncounter} onClose={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Set active' }))

    expect(onSelectEncounter).toHaveBeenCalledWith('enc_yard')
  })

  it('shows the selected encounter as active', () => {
    render(
      <LocationMapModal
        graph={{ ...GRAPH, selected_encounter_template_id: 'enc_yard' }}
        onSelectEncounter={() => {}}
        onClose={() => {}}
      />,
    )

    expect(screen.getByRole('button', { name: 'Active' })).toBeDisabled()
    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('closes through the header button', () => {
    const onClose = vi.fn()
    render(<LocationMapModal graph={GRAPH} onClose={onClose} />)

    fireEvent.click(screen.getByRole('button', { name: 'Close map' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
