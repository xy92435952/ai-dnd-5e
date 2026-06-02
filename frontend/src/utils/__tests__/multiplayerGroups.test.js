import { describe, expect, it } from 'vitest'
import {
  getActiveGroup,
  getGroupMemberStatuses,
  getGroupPendingActions,
  getGroupIntentFeedback,
  getGroupReadinessBreakdown,
  getMultiplayerTableStatus,
  getMyGroup,
  getNextReadyGroupInfo,
  getNextReadyGroupSummary,
  isGroupAllReady,
} from '../multiplayerGroups'

const room = {
  active_group_id: 'tavern',
  members: [
    { user_id: 'me', display_name: '我', username: 'me' },
    { user_id: 'u2', display_name: '凯伦', username: 'karen', role: 'host' },
    { user_id: 'u3', username: 'shadow' },
  ],
  party_groups: [
    { id: 'alley', name: '后巷组', location: '后门', member_user_ids: ['me'] },
    { id: 'tavern', name: '酒馆组', location: '大厅', member_user_ids: ['u2', 'u3'] },
  ],
  pending_actions_by_group: {
    tavern: [{ user_id: 'u2', display_name: '凯伦', text: '我继续套话。' }],
  },
  group_readiness: {
    tavern: { u2: 'ready', u3: 'waiting' },
  },
}

describe('multiplayer group helpers', () => {
  it('finds my group and active group without giving host special visibility semantics', () => {
    expect(getMyGroup(room, 'me')?.id).toBe('alley')
    expect(getActiveGroup(room)?.name).toBe('酒馆组')
    expect(getGroupMemberStatuses(room, room.party_groups[1]).map(item => item.label)).toEqual([
      '凯伦 · 已确认',
      'shadow · 等待中',
    ])
  })

  it('summarizes ready pending groups for shared lobby and adventure hints', () => {
    const readyRoom = {
      ...room,
      group_readiness: {
        tavern: { u2: 'ready', u3: 'ready' },
      },
    }

    expect(getGroupPendingActions(readyRoom, 'tavern')).toHaveLength(1)
    expect(isGroupAllReady(readyRoom, readyRoom.party_groups[1])).toBe(true)
    expect(getNextReadyGroupInfo(readyRoom)).toMatchObject({
      groupId: 'tavern',
      groupLabel: '酒馆组',
      pendingCount: 1,
      isActive: true,
      summaryLabel: '下一处理：酒馆组 · 1 条待处理 · 全员已确认',
    })
    expect(getNextReadyGroupSummary(readyRoom)).toBe('下一处理：酒馆组 · 1 条待处理 · 全员已确认')
  })

  it('builds one table status model for room, adventure, and table notices', () => {
    const readyRoom = {
      ...room,
      group_readiness: {
        tavern: { u2: 'ready', u3: 'ready' },
      },
    }

    expect(getMultiplayerTableStatus({
      room: readyRoom,
      myUserId: 'me',
      currentSeg: {
        role: 'dm',
        table_reason: '多个分队都已确认，按当前行动分队先处理。',
        table_decision: {
          decision: 'process_actor_group',
          reason_code: 'process_actor_group',
          target_group_id: 'alley',
        },
      },
      logs: [
        { role: 'dm', table_reason: '旧原因' },
      ],
    })).toMatchObject({
      activeGroupLabel: '酒馆组',
      myGroupLabel: '后巷组',
      aggregatedActionHint: '',
      nextReadySummary: '下一处理：酒馆组 · 1 条待处理 · 全员已确认',
      processingHint: '当前镜头「酒馆组」已全员确认，等待当前发言者处理 1 条意图',
      tableReason: '多个分队都已确认，按当前行动分队先处理。',
      tableDecisionLabel: '处理当前分队',
      shouldShowNotice: true,
    })

    expect(getMultiplayerTableStatus({
      room: readyRoom,
      myUserId: 'me',
      currentSeg: {
        role: 'dm',
        table_reason: '玩家明确要求切镜头。',
        table_decision: {
          decision: 'switch_focus',
          reason_code: 'switch_focus',
          target_group_id: 'tavern',
        },
      },
    }).tableDecisionLabel).toBe('切换镜头')

    expect(getMultiplayerTableStatus({
      room: readyRoom,
      myUserId: 'me',
      currentSeg: null,
      logs: [
        { role: 'dm', table_reason: '等待钟楼组补充行动。' },
      ],
    }).tableReason).toBe('等待钟楼组补充行动。')

    expect(getMultiplayerTableStatus({
      room: { ...readyRoom, pending_actions_by_group: {}, group_readiness: {} },
      myUserId: 'me',
      currentSeg: null,
      logs: [],
    }).shouldShowNotice).toBe(false)

    expect(getMultiplayerTableStatus({
      room: {
        ...readyRoom,
        active_group_id: 'alley',
        pending_actions_by_group: {
          alley: [
            { user_id: 'u2', text: '我压低声音守门。' },
            { user_id: 'u3', text: '我检查脚印。' },
          ],
        },
      },
      myUserId: 'me',
      isMySpeakTurn: true,
    }).aggregatedActionHint).toBe('DM 会在主行动中带上 2 条队友意图')

    expect(getMultiplayerTableStatus({
      room: {
        ...readyRoom,
        active_group_id: 'alley',
        pending_actions_by_group: {
          tavern: [
            { user_id: 'u2', display_name: '凯伦', text: '我继续套话。' },
          ],
        },
      },
      myUserId: 'me',
      isMySpeakTurn: false,
    })).toMatchObject({
      activeGroupLabel: '后巷组',
      nextReadySummary: '已就绪：酒馆组 · 1 条待处理 · 全员已确认',
      processingHint: '「酒馆组」已全员确认 1 条意图；当前镜头仍在「后巷组」',
    })

    expect(getMultiplayerTableStatus({
      room: {
        ...readyRoom,
        active_group_id: 'tavern',
        pending_actions_by_group: {
          alley: [
            { user_id: 'me', display_name: '我', text: '我守住后门。' },
          ],
        },
      },
      myUserId: 'me',
      isMySpeakTurn: true,
    })).toMatchObject({
      activeGroupLabel: '酒馆组',
      myGroupLabel: '后巷组',
      myGroupIsActive: false,
      processingHint: '你的主行动会汇总「后巷组」的 1 条意图；当前镜头仍在「酒馆组」',
    })
  })

  it('summarizes my pending intent and group readiness feedback', () => {
    const activeRoom = {
      ...room,
      active_group_id: 'tavern',
      pending_actions_by_group: {
        tavern: [
          { user_id: 'u2', display_name: '凯伦', text: '我继续套话。' },
          { user_id: 'u3', display_name: 'shadow', text: '我盯着门口。' },
        ],
      },
      group_readiness: {
        tavern: { u2: 'ready', u3: 'drafting' },
      },
    }

    expect(getGroupIntentFeedback({
      room: activeRoom,
      myUserId: 'u2',
      isMySpeakTurn: false,
    })).toMatchObject({
      submittedMine: true,
      needsMyConfirmation: false,
      pendingCount: 2,
      readyCount: 1,
      memberCount: 2,
      statusLabel: '你已提交意图 · 等当前发言者带给 DM',
      readinessLabel: '确认进度：1/2 已确认',
    })

    expect(getGroupIntentFeedback({
      room: activeRoom,
      myUserId: 'u3',
      isMySpeakTurn: true,
    })).toMatchObject({
      submittedMine: true,
      needsMyConfirmation: true,
      statusLabel: '你是当前发言者 · DM 会汇总本分队 2 条意图',
      readinessLabel: '确认进度：1/2 已确认',
    })

    expect(getGroupIntentFeedback({
      room: activeRoom,
      myUserId: 'u3',
      isMySpeakTurn: false,
    })).toMatchObject({
      submittedMine: true,
      needsMyConfirmation: true,
      statusLabel: '你已提交意图 · 点“我已确认”后 DM 才会处理',
    })

    expect(getGroupIntentFeedback({
      room: activeRoom,
      myUserId: 'u3',
      isMySpeakTurn: false,
      groupId: 'alley',
    }).statusLabel).toBe('你的分队还没有待汇总意图')
  })

  it('breaks down ready and not-ready members by display name', () => {
    const activeRoom = {
      ...room,
      party_groups: [
        { id: 'tavern', name: '酒馆组', location: '大厅', member_user_ids: ['me', 'u2', 'u3'] },
      ],
      group_readiness: {
        tavern: { me: 'drafting', u2: 'ready', u3: 'waiting' },
      },
    }

    expect(getGroupReadinessBreakdown(activeRoom, 'tavern')).toMatchObject({
      readyCount: 1,
      memberCount: 3,
      readyNames: ['凯伦'],
      waitingNames: ['shadow'],
      draftingNames: ['我'],
      notReadyNames: ['我', 'shadow'],
      readyLabel: '已确认：凯伦',
      waitingLabel: '等待补充：shadow',
      draftingLabel: '继续草拟：我',
      summaryLabel: '未确认：我、shadow',
    })
  })
})
