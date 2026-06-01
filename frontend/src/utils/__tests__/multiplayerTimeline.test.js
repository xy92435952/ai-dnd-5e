import { describe, expect, it } from 'vitest'
import { buildMultiplayerTimeline, summarizeTimelineLane } from '../multiplayerTimeline'

describe('multiplayer timeline helpers', () => {
  const room = {
    active_group_id: 'alley',
    party_groups: [
      { id: 'alley', name: '后巷组', member_user_ids: ['u1'] },
      { id: 'tower', name: '钟楼组', member_user_ids: ['u2'] },
    ],
  }

  it('classifies already-visible logs into public, my group, and private lanes', () => {
    const logs = [
      { role: 'dm', content: '全队听见钟声。', visibility: { scope: 'party' } },
      { role: 'dm', content: '后巷门锁弹开。', visibility: { scope: 'group', group_id: 'alley', visible_to_user_ids: ['u1'] } },
      { role: 'dm', content: '你单独看见暗号。', visibility: { scope: 'private', visible_to_user_ids: ['u1'] } },
      { role: 'player', content: '我检查门缝。' },
    ]

    const timeline = buildMultiplayerTimeline({ logs, room, myUserId: 'u1' })

    expect(timeline.myGroup).toMatchObject({ id: 'alley', name: '后巷组' })
    expect(timeline.lanes.public.items.map(item => item.text)).toEqual(['全队听见钟声。'])
    expect(timeline.lanes.group.items.map(item => item.text)).toEqual(['后巷门锁弹开。'])
    expect(timeline.lanes.private.items.map(item => item.text)).toEqual(['你单独看见暗号。'])
  })

  it('keeps host-like users limited to their own visible group lane', () => {
    const logs = [
      { role: 'dm', content: '钟楼发现密信。', visibility: { scope: 'group', group_id: 'tower', visible_to_user_ids: ['u2'] } },
      { role: 'dm', content: '后巷发现钥匙。', visibility: { scope: 'group', group_id: 'alley', visible_to_user_ids: ['u1'] } },
    ]

    const timeline = buildMultiplayerTimeline({ logs, room: { ...room, host_user_id: 'u1' }, myUserId: 'u1' })

    expect(timeline.lanes.group.items.map(item => item.text)).toEqual(['后巷发现钥匙。'])
    expect(timeline.lanes.group.items.map(item => item.text)).not.toContain('钟楼发现密信。')
  })

  it('uses group membership as a safe fallback when group visibility lists are empty', () => {
    const logs = [
      { role: 'dm', content: '后巷低声交换口令。', visibility: { scope: 'group', group_id: 'alley', visible_to_user_ids: [] } },
      { role: 'dm', content: '钟楼找到了第二张地图。', visibility: { scope: 'group', group_id: 'tower', visible_to_user_ids: [] } },
      { role: 'dm', content: '无目标私密暗号。', visibility: { scope: 'private', visible_to_user_ids: [] } },
      { role: 'dm', content: '公共钟声照常响起。', visibility: { scope: 'party', visible_to_user_ids: [] } },
    ]

    const timeline = buildMultiplayerTimeline({ logs, room, myUserId: 'u1' })

    expect(timeline.lanes.public.items.map(item => item.text)).toEqual(['公共钟声照常响起。'])
    expect(timeline.lanes.group.items.map(item => item.text)).toEqual(['后巷低声交换口令。'])
    expect(timeline.lanes.group.items.map(item => item.text)).not.toContain('钟楼找到了第二张地图。')
    expect(timeline.lanes.private.items.map(item => item.text)).not.toContain('无目标私密暗号。')
  })

  it('summarizes lane counts for compact UI labels', () => {
    expect(summarizeTimelineLane({ label: '我的分队', items: [{}, {}] })).toBe('我的分队 2')
    expect(summarizeTimelineLane({ label: '私密', items: [] })).toBe('私密 0')
  })
})
