import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import ExplorationReactionPrompt from '../ExplorationReactionPrompt'


function prompt() {
  return {
    type: 'feather_fall',
    trap_name: 'Hidden Pit',
    reactor_character_name: 'Lyra',
    target_character_name: 'Scout',
    available_reactions: [{
      type: 'feather_fall',
      slot_level: '1st',
      cost: '1st spell slot + reaction',
      damage_prevented: 9,
    }],
  }
}


describe('ExplorationReactionPrompt', () => {
  it('renders Feather Fall cost and submits accept or decline choices', () => {
    const onResolve = vi.fn()
    render(<ExplorationReactionPrompt prompt={prompt()} onResolve={onResolve} />)

    expect(screen.getByText('Feather Fall')).toBeInTheDocument()
    expect(screen.getByText(/Prevents 9 fall damage/)).toBeInTheDocument()
    expect(screen.getByText('1st spell slot + reaction')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Cast Feather Fall/ }))
    fireEvent.click(screen.getByRole('button', { name: /Decline/ }))

    expect(onResolve).toHaveBeenNthCalledWith(1, 'feather_fall', expect.objectContaining({
      reactor_character_name: 'Lyra',
    }))
    expect(onResolve).toHaveBeenNthCalledWith(2, 'decline', expect.any(Object))
  })
})
