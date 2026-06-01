import { formatTacticalRole, getTacticalRoleHint } from './combatTacticalContext'

function actorName(entry, entity) {
  return entity?.name || entry?.name || '当前单位'
}

function controlledName(controlledCharacter, entry, entity) {
  return controlledCharacter?.name || actorName(entry, entity)
}

export function buildCombatTurnCoach({
  currentTurnEntry,
  currentTurnEntity,
  controlledCharacter,
  isPlayerTurn = false,
  isProcessing = false,
  syncBlocked = false,
  room = null,
  controllerName = '',
} = {}) {
  if (syncBlocked) {
    return {
      tone: 'blocked',
      label: '同步暂停',
      detail: '等待战斗同步恢复后再操作，避免使用过期回合状态。',
    }
  }

  if (isProcessing) {
    return {
      tone: 'processing',
      label: '结算中',
      detail: '上一项动作正在结算，结果写入后会刷新可用操作。',
    }
  }

  if (!currentTurnEntry) {
    return {
      tone: 'waiting',
      label: '等待回合',
      detail: '正在读取先攻顺序，暂时不要提交动作。',
    }
  }

  const name = actorName(currentTurnEntry, currentTurnEntity)
  const isEnemy = currentTurnEntity?.is_enemy === true || currentTurnEntry?.is_enemy === true
  const isPlayerLike = currentTurnEntity?.is_player === true || currentTurnEntry?.is_player === true

  if (isPlayerTurn) {
    return {
      tone: 'active',
      label: '你的回合',
      detail: `正在控制 ${controlledName(controlledCharacter, currentTurnEntry, currentTurnEntity)}。先确认位置与目标，再选择攻击、法术、物品或完成本轮。`,
    }
  }

  if (room?.is_multiplayer && controllerName) {
    return {
      tone: 'watching',
      label: '等待队友',
      detail: `${name} 由 ${controllerName} 控制。你可以观察战场、查看日志，或准备可能出现的反应。`,
    }
  }

  if (isEnemy) {
    const role = currentTurnEntity?.tactical_role || currentTurnEntry?.tactical_role || ''
    const roleLabel = role ? formatTacticalRole(role) : ''
    const roleHint = getTacticalRoleHint(role)
    const turnLead = roleLabel ? `${name}（${roleLabel}）正在行动。` : `${name} 正在行动。`
    return {
      tone: 'danger',
      label: '敌方行动',
      detail: `${turnLead}${roleHint ? `${roleHint} ` : ''}留意反应提示、伤害结算和位置变化。`,
    }
  }

  if (!isPlayerLike) {
    return {
      tone: 'watching',
      label: '队友行动',
      detail: `${name} 正在行动。你可以观察战场并准备下一步。`,
    }
  }

  return {
    tone: 'waiting',
    label: '等待回合',
    detail: `当前轮到 ${name}。你可以观察战场、查看角色或准备下一步。`,
  }
}
