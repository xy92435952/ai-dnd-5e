import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import AdventurePartyHud from '../AdventurePartyHud'

vi.mock('../Portrait', () => ({
  default: () => <div data-testid="portrait" />,
}))

vi.mock('../Crests', () => ({
  classKey: (cls) => cls || 'fighter',
  Crest: { fighter: <div /> },
}))

describe('AdventurePartyHud', () => {
  it('exposes each character portrait as a stable button', () => {
    const onOpenCharacter = vi.fn()

    render(
      <AdventurePartyHud
        allMembers={[
          {
            id: 'char-1',
            name: '雷克',
            char_class: 'fighter',
            hp_current: 8,
            derived: { hp_max: 10 },
            isPlayer: true,
          },
        ]}
        onOpenCharacter={onOpenCharacter}
      />,
    )

    const characterButton = screen.getByRole('button', { name: '打开角色 雷克' })
    expect(characterButton).toHaveAttribute('data-testid', 'party-member-char-1')
    expect(characterButton).toHaveAttribute('type', 'button')

    fireEvent.click(characterButton)

    expect(onOpenCharacter).toHaveBeenCalledWith('char-1')
  })
})
