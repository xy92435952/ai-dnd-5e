import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAdventureDerivedState, useAdventureUiState } from '../useAdventureUiState'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-05-08T00:00:00Z'))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useAdventureUiState', () => {
  it('adds logs with the expected shape', () => {
    const { result } = renderHook(() => useAdventureUiState())

    act(() => {
      result.current.addLog('dm', '门打开了', 'narrative', { scene: 'gate' })
    })

    expect(result.current.logs).toHaveLength(1)
    expect(result.current.logs[0]).toMatchObject({
      role: 'dm',
      content: '门打开了',
      log_type: 'narrative',
      created_at: '2026-05-08T00:00:00.000Z',
      scene: 'gate',
    })
  })
})

describe('useAdventureDerivedState', () => {
  it('derives spell preparation, party members, quest and latest DM line', () => {
    const { result } = renderHook(() => useAdventureDerivedState({
      session: {
        game_state: { scene_vibe: { tone: 'tense' } },
        campaign_state: {
          clues: ['a', 'b', 'c', 'd', 'e'],
          quest_log: [
            { quest: '旧任务', status: 'completed' },
            { quest: '当前任务', status: 'active' },
          ],
        },
      },
      player: { id: 'p1', name: '法师', char_class: 'Wizard' },
      companions: [{ id: 'c1', name: '战士' }],
      logs: [
        { role: 'dm', log_type: 'narrative', content: '第一段' },
        { role: 'player', content: '我前进' },
        { role: 'dm', log_type: 'narrative', content: '第二段' },
      ],
    }))

    expect(result.current.canPrepareSpells).toBe(true)
    expect(result.current.sceneVibe).toEqual({ tone: 'tense' })
    expect(result.current.clues).toEqual(['b', 'c', 'd', 'e'])
    expect(result.current.questLine.quest).toBe('当前任务')
    expect(result.current.allMembers).toEqual([
      { id: 'p1', name: '法师', char_class: 'Wizard', isPlayer: true },
      { id: 'c1', name: '战士', isPlayer: false },
    ])
    expect(result.current.latestDmLine.content).toBe('第二段')
  })
})
