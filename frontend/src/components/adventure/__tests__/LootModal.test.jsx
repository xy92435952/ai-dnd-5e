import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import LootModal from '../LootModal'

const { getLootMock, claimLootMock } = vi.hoisted(() => ({
  getLootMock: vi.fn(),
  claimLootMock: vi.fn(),
}))

vi.mock('../../../api/client', () => ({
  gameApi: {
    getLoot: getLootMock,
    claimLoot: claimLootMock,
  },
}))

describe('LootModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads session loot and shows available versus claimed rewards', async () => {
    getLootMock.mockResolvedValue({
      items: [
        { id: 'loot_hidden_seal_0', name: 'Ancient Seal', category: 'gear', status: 'hidden', source: 'key_rewards' },
        { id: 'loot_old_reward_0', name: 'Old Reward', category: 'gear', status: 'available', source: 'key_rewards' },
        { id: 'loot_gold_0', name: '25 gp', category: 'gold', amount: 25, status: 'available' },
        { id: 'loot_gear_gate_token_1', name: 'Gate Token', category: 'gear', rarity: 'common', cost: 100, status: 'claimed', claimed_by_name: 'Mira' },
      ],
    })

    render(
      <LootModal
        sessionId="sess-1"
        player={{ id: 'char-1', name: 'Tester' }}
        onClaimed={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(await screen.findByRole('button', { name: 'Claim 25 gp' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Split 25 gp' })).toBeEnabled()
    expect(screen.getByRole('group', { name: 'Loot actions for 25 gp' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Loot actions for Gate Token' })).toBeInTheDocument()
    expect(screen.getByText('Claim for yourself or split with the party.')).toBeInTheDocument()
    expect(screen.getByText('Claimed by Mira')).toBeInTheDocument()
    expect(screen.queryByText('Ancient Seal')).not.toBeInTheDocument()
    expect(screen.queryByText('Old Reward')).not.toBeInTheDocument()
    expect(screen.getByText('Gate Token')).toBeInTheDocument()
    expect(screen.getByText('100 gp value')).toBeInTheDocument()
    const summary = screen.getByLabelText('Loot summary')
    expect(within(summary).getByText('available')).toBeInTheDocument()
    expect(within(summary).getByText('claimed')).toBeInTheDocument()
    expect(screen.getByLabelText('Session loot')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('button', { name: 'Claim Gate Token' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Share Gate Token' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Roll Gate Token' })).toBeDisabled()
  })

  it('claims loot for the current player and refreshes the visible pool', async () => {
    getLootMock.mockResolvedValue({
      items: [
        { id: 'loot_gold_0', name: '25 gp', category: 'gold', amount: 25, status: 'available' },
      ],
    })
    claimLootMock.mockResolvedValue({
      claimed: { id: 'loot_gold_0', name: '25 gp' },
      character_id: 'char-1',
      equipment: { gold: 30 },
      loot_pool: {
        items: [
          { id: 'loot_gold_0', name: '25 gp', category: 'gold', amount: 25, status: 'claimed', claimed_by_name: 'Tester' },
        ],
      },
    })
    const onClaimed = vi.fn()

    render(
      <LootModal
        sessionId="sess-1"
        player={{ id: 'char-1', name: 'Tester' }}
        onClaimed={onClaimed}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Claim 25 gp' }))

    await waitFor(() => {
      expect(claimLootMock).toHaveBeenCalledWith('sess-1', 'char-1', 'loot_gold_0')
      expect(onClaimed).toHaveBeenCalledWith(expect.objectContaining({
        character_id: 'char-1',
      }))
    })
    expect(screen.getByText('Claimed by Tester')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Claim 25 gp' })).toBeDisabled()
  })

  it('keeps discovered loot visible but blocks distribution while room sync is reconnecting', async () => {
    getLootMock.mockResolvedValue({
      items: [
        { id: 'loot_gold_0', name: '25 gp', category: 'gold', amount: 25, status: 'available' },
        { id: 'loot_gear_gate_token_0', name: 'Gate Token', category: 'gear', rarity: 'common', status: 'available' },
      ],
    })

    render(
      <LootModal
        sessionId="sess-1"
        player={{ id: 'char-1', name: 'Tester' }}
        disabled
        disabledReason="房间正在重新同步，请恢复连接后再分配战利品。"
        onClaimed={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    const claim = await screen.findByRole('button', { name: 'Claim 25 gp' })
    expect(screen.getByText('Gate Token')).toBeInTheDocument()
    expect(screen.getByText('Claim for yourself, share to the party stash, or roll for a winner.')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('同步暂停')
    expect(screen.getByText('房间正在重新同步，请恢复连接后再分配战利品。')).toBeInTheDocument()

    const split = screen.getByRole('button', { name: 'Split 25 gp' })
    const share = screen.getByRole('button', { name: 'Share Gate Token' })
    const roll = screen.getByRole('button', { name: 'Roll Gate Token' })
    expect(claim).toBeDisabled()
    expect(split).toBeDisabled()
    expect(share).toBeDisabled()
    expect(roll).toBeDisabled()
    expect(claim).toHaveAttribute('title', '房间正在重新同步，请恢复连接后再分配战利品。')

    fireEvent.click(claim)
    fireEvent.click(split)
    fireEvent.click(share)
    fireEvent.click(roll)
    expect(claimLootMock).not.toHaveBeenCalled()
  })

  it('splits gold loot across the party when requested', async () => {
    getLootMock.mockResolvedValue({
      items: [
        { id: 'loot_gold_0', name: '25 gp', category: 'gold', amount: 25, status: 'available' },
      ],
    })
    claimLootMock.mockResolvedValue({
      claimed: { id: 'loot_gold_0', name: '25 gp', claim_mode: 'split_party' },
      character_id: 'char-1',
      equipment: { gold: 16 },
      split_allocations: [
        { character_id: 'char-1', character_name: 'Tester', amount: 13 },
        { character_id: 'char-2', character_name: 'Ally', amount: 12 },
      ],
      loot_pool: {
        items: [
          { id: 'loot_gold_0', name: '25 gp', category: 'gold', amount: 25, status: 'claimed', claim_mode: 'split_party' },
        ],
      },
    })
    const onClaimed = vi.fn()

    render(
      <LootModal
        sessionId="sess-1"
        player={{ id: 'char-1', name: 'Tester' }}
        onClaimed={onClaimed}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Split 25 gp' }))

    await waitFor(() => {
      expect(claimLootMock).toHaveBeenCalledWith('sess-1', 'char-1', 'loot_gold_0', 'split_party')
      expect(onClaimed).toHaveBeenCalledWith(expect.objectContaining({
        split_allocations: expect.any(Array),
      }))
    })
    expect(screen.getByText('Split with party')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Split 25 gp' })).toBeDisabled()
  })

  it('marks item loot as shared party loot', async () => {
    getLootMock.mockResolvedValue({
      items: [
        { id: 'loot_gear_gate_token_0', name: 'Gate Token', category: 'gear', rarity: 'common', status: 'available' },
      ],
    })
    claimLootMock.mockResolvedValue({
      claimed: { id: 'loot_gear_gate_token_0', name: 'Gate Token', claim_mode: 'party_stash' },
      character_id: 'char-1',
      equipment: { gold: 5, gear: [] },
      loot_pool: {
        items: [
          { id: 'loot_gear_gate_token_0', name: 'Gate Token', category: 'gear', status: 'claimed', claim_mode: 'party_stash' },
        ],
      },
    })
    const onClaimed = vi.fn()

    render(
      <LootModal
        sessionId="sess-1"
        player={{ id: 'char-1', name: 'Tester' }}
        onClaimed={onClaimed}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Share Gate Token' }))

    await waitFor(() => {
      expect(claimLootMock).toHaveBeenCalledWith('sess-1', 'char-1', 'loot_gear_gate_token_0', 'party_stash')
      expect(onClaimed).toHaveBeenCalledWith(expect.objectContaining({
        claimed: expect.objectContaining({ claim_mode: 'party_stash' }),
      }))
    })
    expect(screen.getByText('Shared by party')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Share Gate Token' })).toBeDisabled()
  })

  it('rolls item loot across the party and shows the winner', async () => {
    getLootMock.mockResolvedValue({
      items: [
        { id: 'loot_gear_gate_token_0', name: 'Gate Token', category: 'gear', rarity: 'common', status: 'available' },
      ],
    })
    claimLootMock.mockResolvedValue({
      claimed: { id: 'loot_gear_gate_token_0', name: 'Gate Token', claim_mode: 'roll_party', claimed_by_name: 'Ally' },
      character_id: 'char-2',
      equipment_updates: {
        'char-2': { gold: 0, gear: [{ name: 'Gate Token' }] },
      },
      roll_allocations: [
        { character_id: 'char-1', character_name: 'Tester', d20: 8, winner: false },
        { character_id: 'char-2', character_name: 'Ally', d20: 17, winner: true },
      ],
      loot_pool: {
        items: [
          {
            id: 'loot_gear_gate_token_0',
            name: 'Gate Token',
            category: 'gear',
            status: 'claimed',
            claim_mode: 'roll_party',
            claimed_by_name: 'Ally',
            roll_allocations: [
              { character_id: 'char-1', character_name: 'Tester', d20: 8, winner: false },
              { character_id: 'char-2', character_name: 'Ally', d20: 17, winner: true },
            ],
          },
        ],
      },
    })
    const onClaimed = vi.fn()

    render(
      <LootModal
        sessionId="sess-1"
        player={{ id: 'char-1', name: 'Tester' }}
        onClaimed={onClaimed}
        onClose={vi.fn()}
      />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Roll Gate Token' }))

    await waitFor(() => {
      expect(claimLootMock).toHaveBeenCalledWith('sess-1', 'char-1', 'loot_gear_gate_token_0', 'roll_party')
      expect(onClaimed).toHaveBeenCalledWith(expect.objectContaining({
        roll_allocations: expect.any(Array),
      }))
    })
    expect(screen.getByText('Rolled to Ally')).toBeInTheDocument()
    expect(screen.getByText('Ally d20 17')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Roll Gate Token' })).toBeDisabled()
  })
})
