import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AdventurePartyHud from '../AdventurePartyHud'

vi.mock('../../Portrait', () => ({
  default: () => <div data-testid="portrait" />,
}))

vi.mock('../../Crests', () => ({
  classKey: () => 'fighter',
}))

describe('AdventurePartyHud', () => {
  it('prefers effective top-level hp max over base derived hp max', () => {
    render(
      <AdventurePartyHud
        allMembers={[{
          id: 'char-1',
          name: 'Tired Hero',
          char_class: 'Fighter',
          hp_current: 6,
          hp_max: 6,
          derived: { hp_max: 12 },
          isPlayer: true,
        }]}
        onOpenCharacter={() => {}}
      />,
    )

    expect(screen.getByTitle('Tired Hero HP 6/6')).toBeTruthy()
  })
})
