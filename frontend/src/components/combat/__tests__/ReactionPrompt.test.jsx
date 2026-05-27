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

  it('prefers reaction id when backend type is generic', async () => {
    const onReact = vi.fn()
    render(
      <ReactionPrompt
        prompt={{
          context: 'Incoming spell',
          target_id: 'enemy-mage',
          reactor_character_id: 'char-2',
          available_reactions: [
            {
              id: 'counterspell',
              type: 'spell',
              name: 'Counterspell',
              effect: 'Cancel the spell',
            },
          ],
        }}
        onReact={onReact}
        onCancel={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Counterspell/ }))

    expect(onReact).toHaveBeenCalledWith('counterspell', 'enemy-mage', 'char-2')
  })

  it('passes the prompt back when cancelling a reaction window', async () => {
    const prompt = {
      trigger: 'spell_cast',
      context: 'Incoming spell',
      target_id: 'enemy-mage',
      reactor_character_id: 'char-2',
      available_reactions: [],
    }
    const onCancel = vi.fn()
    render(
      <ReactionPrompt
        prompt={prompt}
        onReact={vi.fn()}
        onCancel={onCancel}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /放弃|鏀惧純/ }))

    expect(onCancel).toHaveBeenCalledWith(prompt)
  })
})
