import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import RestModal from '../RestModal'

describe('RestModal', () => {
  it('uses direct rest actions outside multiplayer', () => {
    const onRest = vi.fn()
    render(<RestModal onRest={onRest} onClose={vi.fn()} />)

    fireEvent.click(screen.getByTestId('rest-long'))
    expect(onRest).toHaveBeenCalledWith('long')

    cleanup()
  })

  it('creates a multiplayer rest vote instead of applying rest directly', () => {
    const onRest = vi.fn()
    const onCreateVote = vi.fn()
    render(
      <RestModal
        onRest={onRest}
        onClose={vi.fn()}
        room={{ is_multiplayer: true, host_user_id: 'host' }}
        myUserId="host"
        onCreateVote={onCreateVote}
      />,
    )

    fireEvent.click(screen.getByTestId('rest-short'))
    expect(onRest).not.toHaveBeenCalled()
    expect(onCreateVote).toHaveBeenCalledWith('short')

    cleanup()
  })

  it('shows active multiplayer vote controls', () => {
    const onVote = vi.fn()
    const onCancelVote = vi.fn()
    render(
      <RestModal
        onRest={vi.fn()}
        onClose={vi.fn()}
        room={{
          is_multiplayer: true,
          host_user_id: 'host',
          rest_vote: {
            rest_type: 'long',
            proposer_user_id: 'host',
            proposer_name: 'Host',
            votes: { host: 'yes' },
            yes_count: 1,
            no_count: 0,
            required_yes: 2,
            remaining_seconds: 80,
          },
        }}
        myUserId="guest"
        onVote={onVote}
        onCancelVote={onCancelVote}
      />,
    )

    fireEvent.click(screen.getByTestId('rest-vote-yes'))
    expect(onVote).toHaveBeenCalledWith('yes')
    expect(screen.queryByTestId('rest-vote-cancel')).not.toBeInTheDocument()

    cleanup()
  })
})
