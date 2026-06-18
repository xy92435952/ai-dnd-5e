import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import AdventureBottomHud from '../AdventureBottomHud'

vi.mock('../../Portrait', () => ({
  default: () => <div data-testid="portrait" />,
}))

vi.mock('../../Crests', () => ({
  classKey: () => 'fighter',
}))

const members = [
  {
    id: 'char-1',
    name: 'Alden',
    char_class: 'Fighter',
    hp_current: 12,
    hp_max: 12,
    isPlayer: true,
  },
  {
    id: 'char-2',
    name: 'Mira',
    char_class: 'Wizard',
    hp_current: 5,
    hp_max: 9,
  },
]

const locationGraph = {
  current_location_id: 'camp',
  nodes: [
    { id: 'camp', name: 'Flooded Camp', visited: true },
    { id: 'mine', name: 'Old Mine', visited: false },
  ],
  edges: [{ from: 'camp', to: 'mine', type: 'discovered' }],
}

describe('AdventureBottomHud', () => {
  it('keeps the adventure status hud responsive while preserving tool actions', () => {
    const onOpenCharacter = vi.fn()
    const onOpenJournal = vi.fn()
    const onOpenMap = vi.fn()
    const onOpenLoot = vi.fn()

    render(
      <AdventureBottomHud
        allMembers={members}
        questLine={{
          quest: 'Trace the missing caravan before the storm blocks the pass',
          status: 'active',
          next_step: 'Question the scout captain and compare tracks near the river crossing.',
        }}
        clues={[{ text: 'Wagon ruts turn toward the mine', is_new: true }]}
        npcUpdates={[]}
        keyDecisions={[]}
        recentConsequences={[]}
        companionSignals={[]}
        locationGraph={locationGraph}
        onOpenCharacter={onOpenCharacter}
        onOpenJournal={onOpenJournal}
        onOpenMap={onOpenMap}
        onOpenLoot={onOpenLoot}
      />,
    )

    const hud = screen.getByRole('region', { name: 'Adventure status' })
    expect(hud).toHaveClass('adventure-bottom-hud')
    expect(screen.getByRole('group', { name: 'Quest and location status' })).toHaveClass('adventure-quest-hud')

    const tools = screen.getByLabelText('Adventure tools')
    expect(tools).toHaveClass('adventure-bottom-actions')

    const map = within(tools).getByRole('button', { name: 'Map: Open mapped locations and encounter templates.' })
    expect(map).toHaveClass('adventure-tool-button')
    expect(map).toHaveAttribute('title', 'Open mapped locations and encounter templates.')
    expect(within(map).getByText('2 loc')).toHaveClass('adventure-tool-badge')
    const loot = within(tools).getByRole('button', { name: 'Loot: Open discovered rewards and party distribution.' })
    expect(loot).toHaveAttribute('title', 'Open discovered rewards and party distribution.')
    const journal = within(tools).getByRole('button', { name: 'Journal: Open quests, clues, companions, locations, and decisions.' })
    expect(journal).toHaveAttribute('title', 'Open quests, clues, companions, locations, and decisions.')

    fireEvent.click(map)
    fireEvent.click(loot)
    fireEvent.click(journal)
    fireEvent.click(screen.getByTitle('Alden HP 12/12'))

    expect(onOpenMap).toHaveBeenCalledTimes(1)
    expect(onOpenLoot).toHaveBeenCalledTimes(1)
    expect(onOpenJournal).toHaveBeenCalledTimes(1)
    expect(onOpenCharacter).toHaveBeenCalledWith('char-1')
  })

  it('keeps map access disabled until location graph data exists', () => {
    render(
      <AdventureBottomHud
        allMembers={members}
        questLine={null}
        clues={[]}
        npcUpdates={[]}
        keyDecisions={[]}
        recentConsequences={[]}
        companionSignals={[]}
        locationGraph={null}
        onOpenCharacter={() => {}}
        onOpenJournal={() => {}}
        onOpenMap={() => {}}
        onOpenLoot={() => {}}
      />,
    )

    const map = screen.getByRole('button', {
      name: 'Map unavailable: Map appears after the DM records at least one known location.',
    })
    expect(map).toBeDisabled()
    expect(map).toHaveAttribute('title', 'Map appears after the DM records at least one known location.')
    expect(screen.queryByText(/loc$/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Loot: Open discovered rewards and party distribution.' })).toBeEnabled()
  })
})
