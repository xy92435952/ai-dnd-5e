export function getSpeakTurnStatusText({ isMySpeakTurn, currentSpeakerName }) {
  if (isMySpeakTurn) {
    return '轮到你了 · 说一句你的行动，DM 会回应并自动轮到下一位'
  }
  if (currentSpeakerName) {
    return `等待 ${currentSpeakerName} 发言 · 你可以阅读剧情或查看角色卡`
  }
  return '等待其他玩家发言 · 你可以阅读剧情或查看角色卡'
}

export function getCombatTurnStatusText({ isMyTurnMP, controllerName }) {
  if (isMyTurnMP) {
    return '你的回合 · 请选择移动、攻击、施法或结束回合'
  }
  if (controllerName) {
    return `等待 ${controllerName} 操作 · 你正在观战`
  }
  return 'AI 托管行动中 · 你正在观战'
}

export function getCombatTurnControllerStatus({ room, currentTurnCharacterId, isMyTurnMP }) {
  if (!room || !currentTurnCharacterId) {
    return { controllerName: '', isOnline: false, secondsSinceSeen: null, label: '' }
  }
  const member = (room.members || []).find(item => item.character_id === currentTurnCharacterId)
  if (!member) {
    return {
      controllerName: '',
      isOnline: false,
      secondsSinceSeen: null,
      label: 'AI 托管行动中',
    }
  }
  const controllerName = member.display_name || member.username || '玩家'
  const isOnline = Boolean(member.is_online)
  const secondsSinceSeen = member.seconds_since_seen ?? null
  if (isMyTurnMP) {
    return {
      controllerName,
      isOnline,
      secondsSinceSeen,
      label: isOnline ? '你正在控制当前回合' : '你的连接状态异常，行动可能无法同步',
    }
  }
  if (!isOnline) {
    return {
      controllerName,
      isOnline,
      secondsSinceSeen,
      label: `${controllerName} 离线${secondsSinceSeen == null ? '' : ` ${secondsSinceSeen} 秒`} · 可由队伍沟通后托管处理`,
    }
  }
  return {
    controllerName,
    isOnline,
    secondsSinceSeen,
    label: `${controllerName} 在线 · 等待其完成回合`,
  }
}

export function getSpeakerOnlineStatus(room, currentSpeakerUid) {
  const member = (room?.members || []).find(item => item.user_id === currentSpeakerUid)
  const isOnline = member ? Boolean(member.is_online) : false
  return {
    isOnline,
    label: isOnline ? '在线' : '离线',
  }
}

export function canRequestAiTakeover({ room, currentSpeakerUid, isMySpeakTurn }) {
  return getAiTakeoverStatus({ room, currentSpeakerUid, isMySpeakTurn }).canTakeover
}

export function getAiTakeoverStatus({ room, currentSpeakerUid, isMySpeakTurn, thresholdSeconds = 30 }) {
  if (!room || !currentSpeakerUid || isMySpeakTurn) {
    return { canTakeover: false, label: '', secondsRemaining: thresholdSeconds }
  }
  const member = (room.members || []).find(item => item.user_id === currentSpeakerUid)
  if (!member) {
    return { canTakeover: false, label: '等待发言者状态同步', secondsRemaining: thresholdSeconds }
  }
  if (member.is_online) {
    return { canTakeover: false, label: '发言者在线，暂不能代演', secondsRemaining: thresholdSeconds }
  }
  if (!member.is_online && member.seconds_since_seen == null) {
    return { canTakeover: true, label: '玩家离线，可 AI 代演', secondsRemaining: 0 }
  }
  const secondsSinceSeen = Math.max(0, member?.seconds_since_seen ?? 0)
  const secondsRemaining = Math.max(0, thresholdSeconds - secondsSinceSeen)
  const canTakeover = secondsRemaining === 0
  if (canTakeover) {
    return { canTakeover: true, label: '玩家离线，可 AI 代演', secondsRemaining: 0 }
  }
  return {
    canTakeover: false,
    label: `离线 ${secondsSinceSeen}秒，${secondsRemaining}秒后可代演`,
    secondsRemaining,
  }
}
