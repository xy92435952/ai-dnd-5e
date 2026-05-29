import { describe, it, expect } from 'vitest'
import { getRestoredTurnState, prepareOpeningStage } from '../adventureSessionLoaded'

describe('getRestoredTurnState', () => {
  it('restores choices and pending check for the local actor', () => {
    const result = getRestoredTurnState({
      is_multiplayer: true,
      game_state: {
        last_turn: {
          last_actor_user_id: 'u1',
          player_choices: ['检查门', '离开'],
          needs_check: { required: true, ability: 'INT' },
        },
      },
    }, 'u1')

    expect(result).toEqual({
      choices: ['检查门', '离开'],
      pendingCheck: { required: true, ability: 'INT' },
      clearTurnState: false,
    })
  })

  it('clears choices and checks when last turn belongs to another player', () => {
    const result = getRestoredTurnState({
      is_multiplayer: true,
      game_state: {
        last_turn: {
          last_actor_user_id: 'u2',
          player_choices: ['检查门'],
          needs_check: { required: true },
        },
      },
    }, 'u1')

    expect(result).toEqual({
      choices: [],
      pendingCheck: null,
      clearTurnState: true,
    })
  })

  it('returns neutral state without last_turn', () => {
    expect(getRestoredTurnState({ game_state: {} }, 'u1')).toEqual({
      choices: null,
      pendingCheck: null,
      clearTurnState: false,
    })
  })
})

describe('prepareOpeningStage', () => {
  it('extracts a single opening narrative into theatre queue and removes the source log', () => {
    const openingTriggered = new Set()
    const result = prepareOpeningStage({
      session_id: 's1',
      logs: [
        { id: 'l1', role: 'dm', log_type: 'narrative', content: '[开场] 你站在矿洞口。' },
      ],
    }, {
      sessionId: 'fallback',
      dialogueQueueLength: 0,
      openingTriggered,
    })

    expect(result.displayLogs).toEqual([])
    expect(result.openingQueue).toEqual([
      { speaker: 'DM', role: 'dm', text: '你站在矿洞口。', color: 'gold' },
    ])
    expect(result.sessionKey).toBe('s1')
  })

  it('does not open theatre when already triggered', () => {
    const result = prepareOpeningStage({
      session_id: 's1',
      logs: [{ id: 'l1', role: 'dm', log_type: 'narrative', content: '开场' }],
    }, {
      sessionId: 'fallback',
      dialogueQueueLength: 0,
      openingTriggered: new Set(['s1']),
    })

    expect(result.openingQueue).toBeNull()
    expect(result.displayLogs).toHaveLength(1)
  })

  it('does not open theatre when there are multiple narrative logs', () => {
    const result = prepareOpeningStage({
      session_id: 's1',
      logs: [
        { id: 'l1', role: 'dm', log_type: 'narrative', content: '第一段' },
        { id: 'l2', role: 'dm', log_type: 'narrative', content: '第二段' },
      ],
    }, {
      sessionId: 'fallback',
      dialogueQueueLength: 0,
      openingTriggered: new Set(),
    })

    expect(result.openingQueue).toBeNull()
    expect(result.displayLogs).toHaveLength(2)
  })

  it('does not reopen theatre for an existing adventure turn with player history', () => {
    const result = prepareOpeningStage({
      session_id: 's1',
      logs: [
        { id: 'l1', role: 'dm', log_type: 'narrative', content: '石门后传来低沉回声。' },
        { id: 'l2', role: 'player', log_type: 'narrative', content: '我靠近石门。' },
      ],
    }, {
      sessionId: 'fallback',
      dialogueQueueLength: 0,
      openingTriggered: new Set(),
    })

    expect(result.openingQueue).toBeNull()
    expect(result.displayLogs).toHaveLength(2)
  })
})
