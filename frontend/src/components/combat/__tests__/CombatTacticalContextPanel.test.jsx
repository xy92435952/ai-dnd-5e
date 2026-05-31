import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatTacticalContextPanel from '../CombatTacticalContextPanel'

describe('CombatTacticalContextPanel', () => {
  it('renders compact encounter context', () => {
    render(
      <CombatTacticalContextPanel
        context={{
          hasContext: true,
          title: 'Rune Hall Encounter',
          difficulty: 'hard',
          targetDifficulty: 'medium',
          environmentPressure: 'heavy',
          environmentAdjustedDifficulty: 'deadly',
          stagedCount: 2,
          objectives: ['Seal the rift'],
          terrain: ['oil slick'],
          cover: ['altar'],
          hazards: ['fire jet'],
          detailGroups: [
            { key: 'objective', label: 'OBJ', value: 'Seal the rift · 1 cell', title: 'Seal the rift' },
            { key: 'cover', label: 'COV', value: 'altar · 1 cell', title: 'altar' },
            { key: 'terrain', label: 'TER', value: 'oil slick · 1 cell', title: 'oil slick' },
            { key: 'hazard', label: 'HZD', value: 'fire jet · 1 cell', title: 'fire jet' },
          ],
          counts: { cover: 1, difficult: 1, hazard: 1, objective: 1 },
        }}
      />,
    )

    expect(screen.getByLabelText('Tactical context')).toBeTruthy()
    expect(screen.getByText('Rune Hall Encounter')).toBeTruthy()
    expect(screen.getByText('Seal the rift')).toBeTruthy()
    expect(screen.getByText('altar / oil slick')).toBeTruthy()
    expect(screen.getByText('fire jet')).toBeTruthy()
    expect(screen.getByText('HARD / target medium / env deadly')).toBeTruthy()
    expect(screen.getByLabelText('Tactical feature details')).toBeTruthy()
    expect(screen.getByText('altar · 1 cell')).toBeTruthy()
    expect(screen.getByText('oil slick · 1 cell')).toBeTruthy()
    expect(screen.getByText('fire jet · 1 cell')).toBeTruthy()
    expect(screen.getByText('Difficult 1')).toBeTruthy()
    expect(screen.getByText('Env heavy')).toBeTruthy()
    expect(screen.getByText('Staged 2')).toBeTruthy()
  })

  it('stays hidden when no context exists', () => {
    const { container } = render(<CombatTacticalContextPanel context={{ hasContext: false }} />)

    expect(container.firstChild).toBeNull()
  })
})
