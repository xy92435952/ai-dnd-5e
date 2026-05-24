import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import ReactionPrompt from '../ReactionPrompt'

describe('ReactionPrompt', () => {
  it('renders backend available_reactions and sends attacker as target', () => {
    const onReact = vi.fn()
    render(
      <ReactionPrompt
        prompt={{
          attacker_id: 'enemy-1',
          attacker_name: 'Goblin',
          context: 'A weapon attack hits you',
          available_reactions: [
            {
              id: 'shield',
              name: 'Shield',
              cost: '1st-level spell slot',
              effect: '+5 AC',
            },
          ],
        }}
        onReact={onReact}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByTestId('combat-reaction-prompt')).toBeInTheDocument()
    expect(screen.getByText('Shield')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('combat-reaction-shield'))

    expect(onReact).toHaveBeenCalledWith('shield', 'enemy-1')
  })

  it('keeps supporting the legacy options shape', () => {
    const onReact = vi.fn()
    render(
      <ReactionPrompt
        prompt={{
          options: [
            { type: 'hellish_rebuke', label: 'Hellish Rebuke', target_id: 'enemy-2' },
          ],
        }}
        onReact={onReact}
        onCancel={vi.fn()}
      />
    )

    fireEvent.click(screen.getByTestId('combat-reaction-hellish_rebuke'))

    expect(onReact).toHaveBeenCalledWith('hellish_rebuke', 'enemy-2')
  })
})
