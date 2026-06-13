import { describe, expect, it } from 'vitest'
import { formatConditionEndSaveLog, formatDelayedTurnLog, formatReadyActionExpiryLog } from '../turnLogs'

describe('turnLogs', () => {
  it('formats default delay-to-round-end logs', () => {
    expect(formatDelayedTurnLog({
      actor_id: 'hero-1',
      actor_name: 'Delay Hero',
    })).toBe('Delay Hero \u5ef6\u8fdf\u884c\u52a8\uff0c\u5c06\u56de\u5408\u79fb\u5230\u672c\u8f6e\u672b\u5c3e\u3002')
  })

  it('formats targeted delay placement logs', () => {
    expect(formatDelayedTurnLog({
      actor_name: 'Delay Hero',
      after_entity_id: 'goblin-1',
      after_entity_name: 'Goblin Guard',
    })).toBe('Delay Hero \u5ef6\u8fdf\u884c\u52a8\uff0c\u5c06\u56de\u5408\u79fb\u5230 Goblin Guard \u4e4b\u540e\u3002')
  })

  it('formats ready-action expiry with custom trigger text', () => {
    expect(formatReadyActionExpiryLog({
      actor_name: 'Ready Host',
      action_type: 'spell',
      spell_name: 'Magic Missile',
      condition_text: 'when the ogre opens the gate',
    })).toBe('Ready Host \u7684\u51c6\u5907\u6cd5\u672f Magic Missile\u6761\u4ef6\u300cwhen the ogre opens the gate\u300d\u672a\u89e6\u53d1\uff0c\u5230\u4e0b\u4e2a\u56de\u5408\u5f00\u59cb\u65f6\u5931\u6548\u3002')
  })

  it('formats condition end-save logs', () => {
    expect(formatConditionEndSaveLog({
      type: 'condition_end_save',
      actor_name: 'Held Guest',
      condition: 'paralyzed',
      spell_name: 'Hold Person',
      ended: false,
      save: { total: 10, dc: 13 },
    })).toBe('Held Guest \u672a\u901a\u8fc7Hold Person\u56de\u5408\u7ed3\u675f\u8c41\u514d\uff0810 vs DC13\uff09\uff0c\u4fdd\u7559\u9ebb\u75f9\u3002')
  })
})
