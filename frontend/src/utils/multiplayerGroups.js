export const READINESS_LABELS = {
  drafting: '草拟中',
  ready: '已确认',
  waiting: '等待中',
}

export function getMemberName(room, userId) {
  const member = (room?.members || []).find(item => item.user_id === userId)
  return member?.display_name || member?.username || userId
}

export function getMyGroup(room, myUserId) {
  const groups = room?.party_groups || []
  return groups.find(group => (group.member_user_ids || []).includes(myUserId))
    || groups.find(group => group.id === room?.active_group_id)
    || groups[0]
    || null
}

export function getActiveGroup(room) {
  const groups = room?.party_groups || []
  return groups.find(group => group.id === room?.active_group_id) || null
}

export function getGroupPendingActions(room, groupOrId) {
  const groupId = typeof groupOrId === 'string' ? groupOrId : groupOrId?.id
  if (!groupId) return []
  return room?.pending_actions_by_group?.[groupId] || []
}

export function getReadinessLabel(status) {
  return READINESS_LABELS[status] || READINESS_LABELS.drafting
}

export function getGroupMemberStatuses(room, group) {
  const readiness = room?.group_readiness?.[group?.id] || {}
  return (group?.member_user_ids || []).map(userId => {
    const status = readiness[userId] || 'drafting'
    const name = getMemberName(room, userId)
    return {
      userId,
      name,
      status,
      statusLabel: getReadinessLabel(status),
      label: `${name} · ${getReadinessLabel(status)}`,
    }
  })
}

export function isGroupAllReady(room, group) {
  const members = group?.member_user_ids || []
  if (members.length === 0) return false
  const readiness = room?.group_readiness?.[group.id] || {}
  return members.every(uid => readiness[uid] === 'ready')
}

export function getNextReadyGroupSummary(room) {
  const groups = room?.party_groups || []
  const activeGroup = getActiveGroup(room)
  const candidate = groups.find(group => (
    getGroupPendingActions(room, group).length > 0 && isGroupAllReady(room, group)
  ))
  if (!candidate) return ''
  const pendingCount = getGroupPendingActions(room, candidate).length
  const name = candidate.name || candidate.id
  const prefix = activeGroup?.id === candidate.id ? '下一处理' : '已就绪'
  return `${prefix}：${name} · ${pendingCount} 条待处理 · 全员已确认`
}

export function getGroupStatusSummary(room, group) {
  const pendingCount = getGroupPendingActions(room, group).length
  const memberStatuses = getGroupMemberStatuses(room, group)
  const allReady = isGroupAllReady(room, group)
  return {
    group,
    pendingCount,
    memberStatuses,
    allReady,
    isActive: group?.id === room?.active_group_id,
    membersLabel: memberStatuses.map(item => item.label).join(' / ') || '暂无成员',
  }
}

export function getGroupIntentFeedback({ room, myUserId, isMySpeakTurn = false, groupId = null }) {
  const group = groupId
    ? (room?.party_groups || []).find(item => item.id === groupId)
    : getMyGroup(room, myUserId)
  const pending = getGroupPendingActions(room, group)
  const memberStatuses = getGroupMemberStatuses(room, group)
  const submittedMine = pending.some(action => action.user_id === myUserId)
  const pendingCount = pending.length
  const readyCount = memberStatuses.filter(item => item.status === 'ready').length
  const memberCount = memberStatuses.length
  const myStatus = memberStatuses.find(item => item.userId === myUserId)?.status || 'drafting'
  const needsMyConfirmation = submittedMine && myStatus !== 'ready'

  let statusLabel = ''
  if (isMySpeakTurn && pendingCount > 0) {
    statusLabel = `你是当前发言者 · DM 会汇总本分队 ${pendingCount} 条意图`
  } else if (needsMyConfirmation) {
    statusLabel = '你已提交意图 · 点“我已确认”后 DM 才会处理'
  } else if (submittedMine) {
    statusLabel = '你已提交意图 · 等当前发言者带给 DM'
  } else if (pendingCount > 0) {
    statusLabel = `本分队已有 ${pendingCount} 条待汇总意图`
  } else {
    statusLabel = '你的分队还没有待汇总意图'
  }

  return {
    group,
    pending,
    pendingCount,
    submittedMine,
    needsMyConfirmation,
    readyCount,
    memberCount,
    statusLabel,
    readinessLabel: memberCount > 0 ? `确认进度：${readyCount}/${memberCount} 已确认` : '',
  }
}

export function getLatestTableReason({ currentSeg, logs }) {
  if (currentSeg?.role === 'dm' && currentSeg.table_reason) {
    return currentSeg.table_reason
  }
  const latest = [...(logs || [])].reverse().find(log => (
    log?.role === 'dm' && log.table_reason
  ))
  return latest?.table_reason || ''
}

export function getLatestTableDecision({ currentSeg, logs }) {
  if (currentSeg?.role === 'dm' && currentSeg.table_decision) {
    return currentSeg.table_decision
  }
  const latest = [...(logs || [])].reverse().find(log => (
    log?.role === 'dm' && log.table_decision
  ))
  return latest?.table_decision || {}
}

export function getTableDecisionLabel(tableDecision) {
  const code = tableDecision?.reason_code || tableDecision?.decision || ''
  const labels = {
    process_actor_group: '处理当前分队',
    process_active_group: '处理当前镜头',
    wait_for_group: '等待分队',
    switch_focus: '切换镜头',
    private_coordination: '私密协调',
  }
  return labels[code] || ''
}

export function getMultiplayerTableStatus({ room, myUserId, currentSeg = null, logs = [], isMySpeakTurn = false }) {
  const activeGroup = getActiveGroup(room)
  const myGroup = getMyGroup(room, myUserId)
  const nextReadySummary = getNextReadyGroupSummary(room)
  const tableReason = getLatestTableReason({ currentSeg, logs })
  const tableDecision = getLatestTableDecision({ currentSeg, logs })
  const tableDecisionLabel = getTableDecisionLabel(tableDecision)
  const myGroupPendingCount = getGroupPendingActions(room, myGroup).length
  const aggregatedActionHint = isMySpeakTurn && myGroupPendingCount > 0
    ? `DM 会在主行动中带上 ${myGroupPendingCount} 条队友意图`
    : ''

  return {
    activeGroup,
    activeGroupLabel: activeGroup?.name || activeGroup?.id || '',
    myGroup,
    myGroupLabel: myGroup?.name || myGroup?.id || '',
    myGroupPendingCount,
    aggregatedActionHint,
    nextReadySummary,
    tableReason,
    tableDecision,
    tableDecisionLabel,
    shouldShowNotice: Boolean(tableReason || nextReadySummary),
  }
}
