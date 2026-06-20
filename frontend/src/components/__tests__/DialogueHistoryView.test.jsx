import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'

import DialogueHistoryView, { logsToHistoryEntries } from '../DialogueHistoryView'

describe('DialogueHistoryView logsToHistoryEntries', () => {
  it('shows Feather Fall reaction dice from restored DM logs', () => {
    const entries = logsToHistoryEntries([
      {
        id: 'log-1',
        role: 'dm',
        log_type: 'narrative',
        content: 'The pit opens, but the fall slows.',
        dice_result: {
          kind: 'reaction',
          reaction_type: 'feather_fall',
          spell_name: 'Feather Fall',
          slot_level: '1st',
          damage_prevented: 9,
        },
      },
    ])

    expect(entries).toHaveLength(2)
    expect(entries[0]).toMatchObject({
      kind: 'narration',
      txt: 'The pit opens, but the fall slows.',
    })
    expect(entries[1]).toMatchObject({
      kind: 'roll',
      rawText: 'Feather Fall reaction：prevented 9 damage · spent 1st slot',
      result: 'neutral',
    })
  })

  it('preserves DM narration and expands restored dice_result arrays', () => {
    const entries = logsToHistoryEntries([
      {
        id: 'log-1',
        role: 'dm',
        log_type: 'narrative',
        content: 'The hidden pit opens, but the fall slows.',
        dice_result: [
          {
            kind: 'saving_throw',
            label: 'Hidden Pit saving throw',
            raw: 3,
            modifier: 2,
            total: 5,
            dc: 14,
            success: false,
          },
          {
            kind: 'damage',
            label: 'Hidden Pit damage',
            raw: 7,
            total: 0,
          },
          {
            kind: 'reaction',
            reaction_type: 'feather_fall',
            spell_name: 'Feather Fall',
            slot_level: '1st',
            damage_prevented: 7,
          },
        ],
      },
    ])

    expect(entries).toHaveLength(4)
    expect(entries[0]).toMatchObject({
      kind: 'narration',
      txt: 'The hidden pit opens, but the fall slows.',
    })
    expect(entries[1]).toMatchObject({
      kind: 'roll',
      label: 'Hidden Pit saving throw',
      roll: 3,
      mod: 2,
      total: 5,
      dc: 14,
      result: 'failure',
    })
    expect(entries[2]).toMatchObject({
      kind: 'roll',
      label: 'Hidden Pit damage',
      roll: 7,
      mod: null,
      total: 0,
      result: 'neutral',
    })
    expect(entries[3]).toMatchObject({
      kind: 'roll',
      rawText: 'Feather Fall reaction：prevented 7 damage · spent 1st slot',
      result: 'neutral',
    })
  })
})

describe('DialogueHistoryView', () => {
  const session = {
    module_name: 'Lost Mine',
    save_name: 'Session One',
    current_scene: 'The goblin trail bends north.',
    campaign_state: {
      completed_scenes: ['Road Ambush'],
    },
    logs: [
      { id: 'dm-1', role: 'dm', log_type: 'narrative', content: 'The woods grow quiet.' },
      { id: 'player-1', role: 'player', log_type: 'narrative', content: 'I check the wagon tracks.' },
      { id: 'comp-1', role: 'companion_Mira', log_type: 'companion', content: 'I will watch the ridge.' },
      {
        id: 'dice-1',
        role: 'dice',
        log_type: 'dice',
        content: '',
        dice_result: {
          label: 'Survival check',
          d20: 12,
          modifier: 3,
          total: 15,
          dc: 13,
          success: true,
        },
      },
    ],
  }

  it('renders the history shell with labelled navigation and filters', () => {
    const onBack = vi.fn()
    render(<DialogueHistoryView session={session} player={{ name: 'Aria' }} onBack={onBack} />)

    expect(screen.getByRole('button', { name: '返回对话' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '返回对话' }))
    expect(onBack).toHaveBeenCalledTimes(1)

    expect(screen.getByRole('heading', { name: '对话史册 · Lost Mine' })).toBeInTheDocument()
    const nav = screen.getByLabelText('对话史册导航')
    expect(within(nav).getByText('章节目录')).toBeInTheDocument()
    expect(within(nav).getByText('Road Ambush')).toBeInTheDocument()
    expect(within(nav).getByText('The goblin trail ben')).toBeInTheDocument()

    const filters = within(nav).getByRole('group', { name: '筛选对话记录' })
    expect(within(filters).getByRole('button', { name: /全部/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(filters).getByRole('button', { name: /仅玩家发言/ })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('status')).toHaveTextContent('全部')
    expect(screen.getByRole('status')).toHaveTextContent('4')
    expect(screen.getByText('The woods grow quiet.')).toBeInTheDocument()
    expect(screen.getByText('I check the wagon tracks.')).toBeInTheDocument()
    expect(screen.getByText('I will watch the ridge.')).toBeInTheDocument()
    expect(document.querySelector('.hist-current-divider')).toHaveClass('hist-current-divider-spaced')
  })

  it('updates the live count and empty state when filters change', () => {
    render(<DialogueHistoryView session={session} player={{ name: 'Aria' }} onBack={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /仅检定结果/ }))
    expect(screen.getByRole('button', { name: /仅检定结果/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('status')).toHaveTextContent('仅检定结果')
    expect(screen.getByRole('status')).toHaveTextContent('1')
    expect(screen.getByText('Survival check · DC 13')).toBeInTheDocument()
    expect(screen.queryByText('The woods grow quiet.')).not.toBeInTheDocument()
    expect(document.querySelector('.hist-current-divider')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /仅玩家发言/ }))
    expect(screen.getByRole('status')).toHaveTextContent('仅玩家发言')
    expect(screen.getByText('I check the wagon tracks.')).toBeInTheDocument()
  })

  it('shows an empty state for filters with no matching entries', () => {
    const emptySession = { ...session, logs: [{ id: 'dm-only', role: 'dm', content: 'Only narration.' }] }
    render(<DialogueHistoryView session={emptySession} player={{ name: 'Aria' }} onBack={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /仅玩家发言/ }))
    expect(screen.getByRole('status')).toHaveTextContent('0')
    expect(screen.getByText('当前筛选下没有匹配的记录')).toBeInTheDocument()
  })
})
