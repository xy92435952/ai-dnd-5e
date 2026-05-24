import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ReactionPrompt from '../ReactionPrompt'

describe('ReactionPrompt', () => {
  it('maps backend available_reactions into clickable reaction actions', async () => {
    const onReact = vi.fn()
    render(
      <ReactionPrompt
        prompt={{
          context: 'Incoming attack',
          attacker_id: 'enemy-1',
          reactor_character_id: 'char-2',
          available_reactions: [
            {
              id: 'hellish_rebuke',
              type: 'hellish_rebuke',
              name: 'Hellish Rebuke',
              effect: 'Deal fire damage',
            },
          ],
        }}
        onReact={onReact}
        onCancel={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Hellish Rebuke/ }))

    expect(onReact).toHaveBeenCalledWith('hellish_rebuke', 'enemy-1', 'char-2')
  })
})
