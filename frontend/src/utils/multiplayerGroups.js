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

function formatMemberNames(items) {
  return items.map(item => item.name).join('、')
}

export function getGroupReadinessBreakdown(room, groupOrId) {
  const group = typeof groupOrId === 'string'
    ? (room?.party_groups || []).find(item => item.id === groupOrId)
    : groupOrId
  const memberStatuses = getGroupMemberStatuses(room, group)
  const readyMembers = memberStatuses.filter(item => item.status === 'ready')
  const waitingMembers = memberStatuses.filter(item => item.status === 'waiting')
  const draftingMembers = memberStatuses.filter(item => item.status === 'drafting')
  const notReadyMembers = memberStatuses.filter(item => item.status !== 'ready')
  const readyNames = readyMembers.map(item => item.name)
  const waitingNames = waitingMembers.map(item => item.name)
  const draftingNames = draftingMembers.map(item => item.name)
  const notReadyNames = notReadyMembers.map(item => item.name)
  const summaryLabel = memberStatuses.length === 0
    ? ''
    : notReadyNames.length ? `未确认：${formatMemberNames(notReadyMembers)}` : '全员已确认'

  return {
    group,
    memberStatuses,
    readyCount: readyMembers.length,
    memberCount: memberStatuses.length,
    readyNames,
    waitingNames,
    draftingNames,
    notReadyNames,
    readyLabel: readyNames.length ? `已确认：${formatMemberNames(readyMembers)}` : '',
    waitingLabel: waitingNames.length ? `等待补充：${formatMemberNames(waitingMembers)}` : '',
    draftingLabel: draftingNames.length ? `继续草拟：${formatMemberNames(draftingMembers)}` : '',
    summaryLabel,
  }
}

export function isGroupAllReady(room, group) {
  const members = group?.member_user_ids || []
  if (members.length === 0) return false
  const readiness = room?.group_readiness?.[group.id] || {}
  return members.every(uid => readiness[uid] === 'ready')
}

function getGroupLabel(group) {
  return group?.name || group?.id || ''
}

export function getNextReadyGroupInfo(room) {
  const groups = room?.party_groups || []
  const activeGroup = getActiveGroup(room)
  const candidate = groups.find(group => (
    getGroupPendingActions(room, group).length > 0 && isGroupAllReady(room, group)
  ))
  if (!candidate) return null
  const pendingCount = getGroupPendingActions(room, candidate).length
  const label = getGroupLabel(candidate)
  const isActive = activeGroup?.id === candidate.id
  const prefix = isActive ? '下一处理' : '已就绪'
  return {
    group: candidate,
    groupId: candidate.id,
    groupLabel: label,
    pendingCount,
    isActive,
    summaryLabel: `${prefix}：${label} · ${pendingCount} 条待处理 · 全员已确认`,
  }
}

export function getNextReadyGroupSummary(room) {
  return getNextReadyGroupInfo(room)?.summaryLabel || ''
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

function getReadinessPrompt({ pendingCount, memberCount, myStatus, needsMyConfirmation, readinessBreakdown }) {
  if (pendingCount === 0 || memberCount === 0) {
    return { readinessPrompt: '', readinessPromptTone: '', readinessReset: false }
  }

  const allReady = readinessBreakdown.readyCount === memberCount
  const readinessReset = readinessBreakdown.readyCount === 0
    && readinessBreakdown.draftingNames.length === memberCount

  if (allReady) {
    return { readinessPrompt: '本分队已全员确认，可以交给 DM 处理。', readinessPromptTone: 'ready', readinessReset }
  }

  if (needsMyConfirmation) {
    return {
      readinessPrompt: '你提交了意图，但这轮分队计划仍是草拟状态；点“我已确认”后 DM 才会处理。',
      readinessPromptTone: 'urgent',
      readinessReset,
    }
  }

  if (myStatus === 'drafting') {
    return {
      readinessPrompt: readinessReset
        ? '分队计划已更新，全队确认被重置；请确认当前意图或继续补充。'
        : '你还没有确认当前分队计划；可以确认，或继续补充你的行动。',
      readinessPromptTone: 'urgent',
      readinessReset,
    }
  }

  if (myStatus === 'waiting') {
    return {
      readinessPrompt: '你标记为等待补充；当前分队不会被视为全员确认。',
      readinessPromptTone: 'waiting',
      readinessReset,
    }
  }

  if (readinessBreakdown.notReadyNames.length > 0) {
    return {
      readinessPrompt: `等待${readinessBreakdown.notReadyNames.join('、')}确认当前分队计划。`,
      readinessPromptTone: 'pending',
      readinessReset,
    }
  }

  return { readinessPrompt: '', readinessPromptTone: '', readinessReset }
}

export function getGroupIntentFeedback({ room, myUserId, isMySpeakTurn = false, groupId = null }) {
  const group = groupId
    ? (room?.party_groups || []).find(item => item.id === groupId)
    : getMyGroup(room, myUserId)
  const pending = getGroupPendingActions(room, group)
  const memberStatuses = getGroupMemberStatuses(room, group)
  const readinessBreakdown = getGroupReadinessBreakdown(room, group)
  const submittedMine = pending.some(action => action.user_id === myUserId)
  const pendingCount = pending.length
  const readyCount = readinessBreakdown.readyCount
  const memberCount = memberStatuses.length
  const myStatus = memberStatuses.find(item => item.userId === myUserId)?.status || 'drafting'
  const needsMyConfirmation = submittedMine && myStatus !== 'ready'
  const { readinessPrompt, readinessPromptTone, readinessReset } = getReadinessPrompt({
    pendingCount,
    memberCount,
    myStatus,
    needsMyConfirmation,
    readinessBreakdown,
  })

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
    readinessReset,
    readinessPrompt,
    readinessPromptTone,
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
  const nextReadyGroup = getNextReadyGroupInfo(room)
  const nextReadySummary = nextReadyGroup?.summaryLabel || ''
  const tableReason = getLatestTableReason({ currentSeg, logs })
  const tableDecision = getLatestTableDecision({ currentSeg, logs })
  const tableDecisionLabel = getTableDecisionLabel(tableDecision)
  const myGroupPendingCount = getGroupPendingActions(room, myGroup).length
  const activeGroupLabel = getGroupLabel(activeGroup)
  const myGroupLabel = getGroupLabel(myGroup)
  const myGroupIsActive = Boolean(activeGroup?.id && myGroup?.id && activeGroup.id === myGroup.id)
  const aggregatedActionHint = isMySpeakTurn && myGroupPendingCount > 0
    ? `DM 会在主行动中带上 ${myGroupPendingCount} 条队友意图`
    : ''
  let processingHint = ''
  if (isMySpeakTurn && myGroupPendingCount > 0) {
    processingHint = myGroupIsActive
      ? `你的主行动会汇总当前镜头「${myGroupLabel}」的 ${myGroupPendingCount} 条意图`
      : activeGroupLabel
        ? `你的主行动会汇总「${myGroupLabel}」的 ${myGroupPendingCount} 条意图；当前镜头仍在「${activeGroupLabel}」`
        : `你的主行动会汇总「${myGroupLabel}」的 ${myGroupPendingCount} 条意图`
  } else if (nextReadyGroup?.isActive) {
    processingHint = `当前镜头「${nextReadyGroup.groupLabel}」已全员确认，等待当前发言者处理 ${nextReadyGroup.pendingCount} 条意图`
  } else if (nextReadyGroup) {
    processingHint = `「${nextReadyGroup.groupLabel}」已全员确认 ${nextReadyGroup.pendingCount} 条意图；当前镜头仍在「${activeGroupLabel || '未定'}」`
  }

  return {
    activeGroup,
    activeGroupLabel,
    myGroup,
    myGroupLabel,
    myGroupPendingCount,
    myGroupIsActive,
    aggregatedActionHint,
    processingHint,
    nextReadyGroup,
    nextReadySummary,
    tableReason,
    tableDecision,
    tableDecisionLabel,
    shouldShowNotice: Boolean(tableReason || nextReadySummary),
  }
}
