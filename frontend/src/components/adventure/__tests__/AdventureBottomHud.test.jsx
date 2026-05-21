import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import AdventureBottomHud from '../AdventureBottomHud'

describe('AdventureBottomHud', () => {
  it('opens the journal through a stable accessible control', () => {
    const onOpenJournal = vi.fn()

    render(
      <AdventureBottomHud
        allMembers={[]}
        questLine={[]}
        clues={[]}
        npcUpdates={[]}
        keyDecisions={[]}
        onOpenCharacter={vi.fn()}
        onOpenJournal={onOpenJournal}
      />,
    )

    const openJournalButton = screen.getByRole('button', { name: '打开卷宗' })

    expect(openJournalButton).toHaveAttribute('data-testid', 'open-journal-button')
    expect(openJournalButton).toHaveAttribute('type', 'button')
    expect(openJournalButton).toHaveTextContent('卷宗')

    fireEvent.click(openJournalButton)

    expect(onOpenJournal).toHaveBeenCalledTimes(1)
  })
})
