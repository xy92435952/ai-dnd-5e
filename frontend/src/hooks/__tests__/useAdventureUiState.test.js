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
          clues: [
            { id: 'a', text: 'a' },
            { id: 'b', text: 'b' },
            { id: 'c', text: 'c' },
            { id: 'hidden-vault', text: '隐藏金库', hidden: true },
            { id: 'moonwell-door', text: '暗门在井底', category: 'location' },
            { id: 'e', text: 'e' },
          ],
          quest_log: [
            { quest: '旧任务', status: 'completed' },
            { quest: '当前任务', status: 'active' },
          ],
          npc_registry: {
            铁匠: { relationship: '友好', key_facts: ['愿意修装备'] },
          },
          key_decisions: ['救下铁匠', '信任铁匠'],
          recent_updates: [
            { type: 'quest', label: '旧任务', detail: 'completed', at: '1' },
            { type: 'quest', label: '当前任务', detail: '发现第二道暗门', at: '1.5' },
            { type: 'npc', label: '铁匠', detail: '友好', at: '2' },
            { type: 'decision', label: '信任铁匠', detail: '关键决定', at: '3' },
            { type: 'clue', label: '暗门在井底', detail: 'location', at: '4' },
            { type: 'clue', clue_id: 'hidden-vault', label: '隐藏金库', detail: 'secret', at: '4.5' },
            { type: 'world', label: 'smith_trusted', detail: '已触发', at: '5' },
          ],
          companion_bonds: {
            c1: {
              relationship: '认可',
              approval: 18,
              last_approval_delta: 6,
              last_approval_reason: '听取前线建议',
              personal_quest: {
                title: '旧誓言',
                next_step: '询问铁匠的徽章',
              },
            },
          },
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
    expect(result.current.clues.map(clue => clue.text)).toEqual(['b', 'c', '暗门在井底', 'e'])
    expect(result.current.questLine.quest).toBe('当前任务')
    expect(result.current.questLine.progressCount).toBe(1)
    expect(result.current.npcUpdates).toEqual([
      { name: '铁匠', relationship: '友好', keyFacts: ['愿意修装备'] },
    ])
    expect(result.current.keyDecisions).toEqual(['救下铁匠', '信任铁匠'])
    expect(result.current.recentConsequences).toEqual([
      { type: 'world', label: 'smith_trusted', detail: '已触发', at: '5' },
      { type: 'clue', label: '暗门在井底', detail: 'location', at: '4' },
      { type: 'decision', label: '信任铁匠', detail: '关键决定', at: '3' },
      { type: 'npc', label: '铁匠', detail: '友好', at: '2' },
    ])
    expect(result.current.companionSignals).toHaveLength(1)
    expect(result.current.companionSignals[0]).toMatchObject({
      id: 'c1',
      name: '战士',
      summary: '好感 +6',
      detail: '询问铁匠的徽章',
      tone: 'good',
    })
    expect(result.current.companionSignals[0].title).toContain('最近影响：听取前线建议')
    expect(result.current.allMembers).toEqual([
      { id: 'p1', name: '法师', char_class: 'Wizard', isPlayer: true },
      { id: 'c1', name: '战士', isPlayer: false },
    ])
    expect(result.current.latestDmLine.content).toBe('第二段')
  })

  it('keeps the latest resolved quest visible when no active quest remains', () => {
    const { result } = renderHook(() => useAdventureDerivedState({
      session: {
        campaign_state: {
          quest_log: [
            { quest: '守住营地', status: 'failed', outcome: '幸存者撤入旧矿道' },
          ],
        },
      },
      player: null,
      companions: [],
      logs: [],
    }))

    expect(result.current.questLine).toEqual({
      quest: '守住营地',
      status: 'failed',
      outcome: '幸存者撤入旧矿道',
      progressCount: 0,
    })
  })
})
