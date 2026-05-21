import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import DialogueStagePlayer from '../DialogueStagePlayer'

vi.mock('../StageBubble', () => ({
  default: ({ seg }) => <div data-testid="stage-bubble">{seg.speaker}</div>,
}))

describe('DialogueStagePlayer', () => {
  it('uses a stable button to advance dialogue', () => {
    const onAdvanceDialogue = vi.fn()

    render(
      <DialogueStagePlayer
        dialogueQueue={[{ role: 'dm', speaker: '旁白', text: '继续前进。' }]}
        dialogueIdx={0}
        typingText="继续前进。"
        typingDone
        onAdvanceDialogue={onAdvanceDialogue}
      />,
    )

    const advanceButton = screen.getByRole('button', { name: '继续对话' })
    expect(advanceButton).toHaveAttribute('type', 'button')
    expect(advanceButton).toHaveTextContent('1 / 1')

    fireEvent.click(advanceButton)

    expect(onAdvanceDialogue).toHaveBeenCalledTimes(1)
  })
})
