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

    const dialog = screen.getByRole('dialog', { name: 'Feather Fall' })
    expect(dialog).toHaveClass('exploration-reaction-prompt')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAttribute('aria-labelledby', 'exploration-reaction-prompt-title')
    expect(dialog).toHaveAttribute(
      'aria-describedby',
      'exploration-reaction-prompt-body exploration-reaction-prompt-meta exploration-reaction-prompt-outcomes',
    )
    expect(screen.getByText('Feather Fall')).toHaveAttribute('id', 'exploration-reaction-prompt-title')
    expect(screen.getByText(/can protect/)).toHaveAttribute('id', 'exploration-reaction-prompt-body')
    expect(screen.getByText(/Prevents 9 fall damage/)).toBeInTheDocument()
    expect(screen.getByText('Costs 1st spell slot + reaction')).toBeInTheDocument()
    expect(screen.getByText('Costs 1st spell slot + reaction').parentElement).toHaveAttribute('id', 'exploration-reaction-prompt-meta')
    const outcomes = screen.getByLabelText('Reaction outcome preview')
    expect(outcomes).toHaveAttribute('id', 'exploration-reaction-prompt-outcomes')
    expect(outcomes).toHaveTextContent('Cast prevents 9 fall damage.')
    expect(outcomes).toHaveTextContent('Decline lets Scout take the saved fall damage.')

    fireEvent.click(screen.getByRole('button', { name: /Cast Feather Fall/ }))
    fireEvent.click(screen.getByRole('button', { name: /Decline/ }))

    expect(onResolve).toHaveBeenNthCalledWith(1, 'feather_fall', expect.objectContaining({
      reactor_character_name: 'Lyra',
    }))
    expect(onResolve).toHaveBeenNthCalledWith(2, 'decline', expect.any(Object))
  })

  it('keeps both decisions disabled while the prompt is blocked', () => {
    const onResolve = vi.fn()
    render(<ExplorationReactionPrompt prompt={prompt()} disabled onResolve={onResolve} />)

    const cast = screen.getByRole('button', { name: /Cast Feather Fall/ })
    const decline = screen.getByRole('button', { name: /Decline/ })

    expect(cast).toBeDisabled()
    expect(decline).toBeDisabled()

    fireEvent.click(cast)
    fireEvent.click(decline)

    expect(onResolve).not.toHaveBeenCalled()
  })
})
