import { describe, expect, it } from 'vitest'
import {
  canRequestAiTakeover,
  getAiTakeoverStatus,
  getCombatTurnStatusText,
  getCombatTurnControllerStatus,
  getSpeakerOnlineStatus,
  getSpeakTurnStatusText,
} from '../multiplayerStatus'

describe('multiplayer status helpers', () => {
  it('explains Adventure speak ownership', () => {
    expect(getSpeakTurnStatusText({ isMySpeakTurn: true, currentSpeakerName: 'Alice' }))
      .toBe('轮到你了 · 说一句你的行动，DM 会回应并自动轮到下一位')
    expect(getSpeakTurnStatusText({ isMySpeakTurn: false, currentSpeakerName: 'Bob' }))
      .toBe('等待 Bob 发言 · 你可以阅读剧情或查看角色卡')
    expect(getSpeakTurnStatusText({ isMySpeakTurn: false, currentSpeakerName: '' }))
      .toBe('等待其他玩家发言 · 你可以阅读剧情或查看角色卡')
  })

  it('explains Combat turn ownership', () => {
    expect(getCombatTurnStatusText({ isMyTurnMP: true, controllerName: 'Alice' }))
      .toBe('你的回合 · 请选择移动、攻击、施法或结束回合')
    expect(getCombatTurnStatusText({ isMyTurnMP: false, controllerName: 'Bob' }))
      .toBe('等待 Bob 操作 · 你正在观战')
    expect(getCombatTurnStatusText({ isMyTurnMP: false, controllerName: '' }))
      .toBe('AI 托管行动中 · 你正在观战')
  })

  it('explains offline combat controller status', () => {
    const room = {
      members: [
        { user_id: 'u1', display_name: 'Bob', character_id: 'c1', is_online: false, seconds_since_seen: 44 },
      ],
    }
    expect(getCombatTurnControllerStatus({ room, currentTurnCharacterId: 'c1', isMyTurnMP: false })).toEqual({
      controllerName: 'Bob',
      isOnline: false,
      secondsSinceSeen: 44,
      label: 'Bob 离线 44 秒 · 可由队伍沟通后托管处理',
    })
    expect(getCombatTurnControllerStatus({ room, currentTurnCharacterId: 'enemy-1', isMyTurnMP: false })).toEqual({
      controllerName: '',
      isOnline: false,
      secondsSinceSeen: null,
      label: 'AI 托管行动中',
    })
  })

  it('only allows AI takeover when the current speaker is offline', () => {
    const room = {
      members: [
        { user_id: 'u1', display_name: 'Alice', is_online: true },
        { user_id: 'u2', display_name: 'Bob', is_online: false },
      ],
    }
    expect(getSpeakerOnlineStatus(room, 'u1')).toEqual({ isOnline: true, label: '在线' })
    expect(getSpeakerOnlineStatus(room, 'u2')).toEqual({ isOnline: false, label: '离线' })
    expect(canRequestAiTakeover({ room, currentSpeakerUid: 'u1', isMySpeakTurn: false })).toBe(false)
    expect(canRequestAiTakeover({ room, currentSpeakerUid: 'u2', isMySpeakTurn: false })).toBe(true)
    expect(canRequestAiTakeover({ room, currentSpeakerUid: 'u2', isMySpeakTurn: true })).toBe(false)
  })

  it('describes AI takeover countdown from heartbeat age', () => {
    const room = {
      members: [
        { user_id: 'u1', is_online: true, seconds_since_seen: 8 },
        { user_id: 'u2', is_online: false, seconds_since_seen: 42 },
      ],
    }
    expect(getAiTakeoverStatus({ room, currentSpeakerUid: 'u1', isMySpeakTurn: false })).toEqual({
      canTakeover: false,
      label: '8秒无动作，22秒后可代演',
      secondsRemaining: 22,
    })
    expect(getAiTakeoverStatus({ room, currentSpeakerUid: 'u2', isMySpeakTurn: false })).toEqual({
      canTakeover: true,
      label: '玩家离线，可 AI 代演',
      secondsRemaining: 0,
    })
  })
})
