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

const PUBLIC_GRAPH = {
  ...GRAPH,
  encounter_templates: GRAPH.encounter_templates.map(template => ({
    ...template,
    public: true,
  })),
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
    const exitSummary = screen.getByLabelText('Exit summary')
    expect(within(exitSummary).getByText('1')).toBeInTheDocument()
    expect(within(exitSummary).getByText('exits')).toBeInTheDocument()
    const routeList = screen.getByRole('list')
    expect(within(routeList).getByText('Gatehouse')).toBeInTheDocument()
    expect(within(routeList).getByText('Known route')).toBeInTheDocument()
    expect(within(routeList).getByText('Next: travel to Gatehouse')).toBeInTheDocument()
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
    const travel = screen.getByLabelText('Route from current')
    expect(within(travel).getByText('Reachable')).toBeInTheDocument()
    expect(within(travel).getByText('1 step')).toBeInTheDocument()
    expect(within(travel).getByText('Training Yard -> Gatehouse')).toBeInTheDocument()
    expect(within(travel).getByText('Next: travel to Gatehouse')).toBeInTheDocument()
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
    expect(within(routeList).getByText('Gated: needs Bronze Key or thieves tools DC 15')).toBeInTheDocument()
    expect(within(routeList).getByText('Next: use Bronze Key or try thieves tools DC 15')).toBeInTheDocument()
    expect(within(routeList).getByText('locked')).toBeInTheDocument()
    expect(within(routeList).getByText('key: Bronze Key')).toBeInTheDocument()
    expect(within(routeList).getByText('thieves_tools DC 15')).toBeInTheDocument()
    const exitSummary = screen.getByLabelText('Exit summary')
    expect(within(exitSummary).getByText('gated')).toBeInTheDocument()
    expect(within(exitSummary).getByText('new')).toBeInTheDocument()
    expect(screen.queryByText('Secret Vault')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Armory unvisited' }))
    const travel = screen.getByLabelText('Route from current')
    expect(within(travel).getByText('Gated route')).toBeInTheDocument()
    expect(within(travel).getByText('Gated: needs Bronze Key or thieves tools DC 15')).toBeInTheDocument()
    expect(within(travel).getByText('Training Yard -> Armory')).toBeInTheDocument()
    expect(within(travel).getByText('Next: use Bronze Key or try thieves tools DC 15')).toBeInTheDocument()
  })

  it('does not surface hidden encounter selection controls', () => {
    const onSelectEncounter = vi.fn()
    render(<LocationMapModal graph={GRAPH} onSelectEncounter={onSelectEncounter} onClose={() => {}} />)

    expect(screen.queryByRole('button', { name: 'Set active' })).not.toBeInTheDocument()
    expect(onSelectEncounter).not.toHaveBeenCalled()
  })

  it('selects an available public encounter template', () => {
    const onSelectEncounter = vi.fn()
    render(<LocationMapModal graph={PUBLIC_GRAPH} onSelectEncounter={onSelectEncounter} onClose={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: 'Set active' }))

    expect(onSelectEncounter).toHaveBeenCalledTimes(1)
    expect(onSelectEncounter).toHaveBeenCalledWith('enc_yard')
  })

  it('keeps public encounters readable but blocks selection while sync is reconnecting', () => {
    const onSelectEncounter = vi.fn()
    render(
      <LocationMapModal
        graph={PUBLIC_GRAPH}
        disabled
        disabledReason="房间正在重新同步，请恢复连接后再选择遭遇。"
        onSelectEncounter={onSelectEncounter}
        onClose={() => {}}
      />
    )

    expect(screen.getAllByText('Construct Patrol').length).toBeGreaterThan(0)
    expect(screen.getByText('房间正在重新同步，请恢复连接后再选择遭遇。')).toBeInTheDocument()

    const selectButton = screen.getByRole('button', { name: 'Set active' })
    expect(selectButton).toBeDisabled()
    expect(selectButton).toHaveAttribute('title', '房间正在重新同步，请恢复连接后再选择遭遇。')
    fireEvent.click(selectButton)

    expect(onSelectEncounter).not.toHaveBeenCalled()
  })

  it('shows public encounter environment pressure without private details', () => {
    render(<LocationMapModal graph={{
      current_location_id: 'yard',
      selected_encounter_template_id: 'enc_yard',
      nodes: [
        { id: 'yard', name: 'Training Yard', visited: true, encounter_template_ids: ['enc_yard'] },
      ],
      encounter_templates: [{
        id: 'enc_yard',
        location_id: 'yard',
        status: 'available',
        public: true,
        name: 'Construct Patrol',
        difficulty_hint: 'moderate',
        xp_budget: 300,
        environment_pressure: {
          pressure: 'heavy',
          hazards: 1,
          objectives: 1,
          cover: 1,
          terrain: 1,
          authored_cells: 5,
        },
      }],
    }} onClose={() => {}} />)

    const encounters = screen.getByLabelText('Selected encounter templates')
    const summary = screen.getByLabelText('Map summary')
    expect(within(summary).getByText('Active')).toBeInTheDocument()
    expect(within(summary).getByText('Construct Patrol')).toBeInTheDocument()
    expect(within(encounters).getByText('Construct Patrol')).toBeInTheDocument()
    expect(within(encounters).getByText('Env heavy')).toBeInTheDocument()
    expect(within(encounters).getByText('hazards 1')).toBeInTheDocument()
    expect(within(encounters).getByText('objectives 1')).toBeInTheDocument()
    expect(within(encounters).getByText('terrain 2')).toBeInTheDocument()
    expect(within(encounters).getByText('cells 5')).toBeInTheDocument()
    const readiness = within(encounters).getByLabelText('Encounter readiness')
    expect(within(readiness).getByText('Active')).toBeInTheDocument()
    expect(within(readiness).getByText('Will seed combat')).toBeInTheDocument()
    expect(within(readiness).getByText('Risk')).toBeInTheDocument()
    expect(within(readiness).getByText('moderate')).toBeInTheDocument()
    expect(within(readiness).getByText('Env')).toBeInTheDocument()
    expect(within(readiness).getByText('heavy')).toBeInTheDocument()
    expect(within(readiness).getByText('Roster hidden')).toBeInTheDocument()
    expect(within(encounters).getByText('Armed for the next combat at this location.')).toBeInTheDocument()
    expect(screen.queryByText('sparking conduit')).not.toBeInTheDocument()
    expect(screen.queryByText('Hidden plan')).not.toBeInTheDocument()
  })

  it('previews public encounters on a selected non-current visible location', () => {
    const onSelectEncounter = vi.fn()
    render(<LocationMapModal graph={{
      current_location_id: 'yard',
      nodes: [
        { id: 'yard', name: 'Training Yard', visited: true },
        { id: 'armory', name: 'Armory', discovered: true, encounter_template_ids: ['enc_armory'] },
        { id: 'vault', name: 'Vault', visited: false, encounter_template_ids: ['enc_vault'] },
      ],
      edges: [{ id: 'yard-armory', from: 'yard', to: 'armory', type: 'route' }],
      encounter_templates: [
        {
          id: 'enc_armory',
          location_id: 'armory',
          status: 'available',
          public: true,
          name: 'Armory Ambush',
          enemy_names: ['Animated Armor'],
        },
        {
          id: 'enc_vault',
          location_id: 'vault',
          status: 'available',
          public: true,
          name: 'Vault Guardian',
        },
      ],
    }} onSelectEncounter={onSelectEncounter} onClose={() => {}} />)

    const routeSummary = screen.getByLabelText('Exit summary')
    expect(within(routeSummary).getByText('encounter route')).toBeInTheDocument()
    const routeList = screen.getByRole('list')
    expect(within(routeList).getByText('Armory')).toBeInTheDocument()
    expect(within(routeList).getByText('Armory Ambush')).toBeInTheDocument()
    expect(within(routeList).getByText('encounter 1')).toHaveClass('danger')

    fireEvent.click(screen.getByRole('button', { name: 'Armory unvisited' }))

    const encounters = screen.getByLabelText('Selected encounter templates')
    expect(within(encounters).getByText('Armory Ambush')).toBeInTheDocument()
    expect(within(encounters).getByText('Animated Armor')).toBeInTheDocument()
    expect(within(encounters).getByText('Ready')).toBeInTheDocument()
    expect(within(encounters).getByText('Can be armed')).toBeInTheDocument()
    expect(within(encounters).getByText('1 known foe')).toBeInTheDocument()
    expect(within(encounters).getByText('Travel here before arming.')).toBeInTheDocument()
    const selectButton = within(encounters).getByRole('button', { name: 'Travel first' })
    expect(selectButton).toBeDisabled()
    expect(selectButton).toHaveAttribute('title', 'Travel to this location before setting this encounter active.')
    fireEvent.click(selectButton)
    expect(onSelectEncounter).not.toHaveBeenCalled()
    expect(screen.queryByText('Vault Guardian')).not.toBeInTheDocument()
  })

  it('closes through the header button', () => {
    const onClose = vi.fn()
    render(<LocationMapModal graph={GRAPH} onClose={onClose} />)

    fireEvent.click(screen.getByRole('button', { name: 'Close map' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
