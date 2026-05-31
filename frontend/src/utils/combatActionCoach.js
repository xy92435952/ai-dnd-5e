const ACTION_KINDS = new Set(['attack', 'spell', 'action', 'item', 'move'])
const BONUS_KINDS = new Set(['bonus', 'bonus_action'])

export function buildCombatActionCoach({
  isPlayerTurn = false,
  isProcessing = false,
  syncBlocked = false,
  turnState = {},
  skillBar = [],
  selectedTarget = null,
  moveMode = false,
} = {}) {
  if (!isPlayerTurn || isProcessing || syncBlocked) {
    return { visible: false, items: [] }
  }

  const actionOpen = !turnState?.action_used
  const bonusOpen = !turnState?.bonus_action_used
  const reactionOpen = !turnState?.reaction_used
  const movementMax = readNumber(turnState?.movement_max, 6)
  const movementUsed = readNumber(turnState?.movement_used, 0)
  const movementLeft = Math.max(0, movementMax - movementUsed)
  const usableSkills = Array.isArray(skillBar) ? skillBar.filter(skill => skill?.available !== false) : []
  const hasActionOption = usableSkills.some(skill => ACTION_KINDS.has(skill.kind))
  const hasBonusOption = usableSkills.some(skill => BONUS_KINDS.has(skill.kind) || /bonus/i.test(String(skill.cost || '')))
  const targetNeeded = usableSkills.some(skill => skillNeedsTarget(skill))

  const items = [
    {
      key: 'action',
      label: 'Action',
      value: actionOpen
        ? selectedTarget || !targetNeeded
          ? hasActionOption ? 'Ready' : 'Choose'
          : 'Pick target'
        : 'Spent',
      tone: actionOpen ? selectedTarget || !targetNeeded ? 'ready' : 'warn' : 'spent',
    },
    {
      key: 'move',
      label: 'Move',
      value: moveMode ? 'Choose cell' : `${movementLeft} sq`,
      tone: movementLeft > 0 ? moveMode ? 'warn' : 'ready' : 'spent',
    },
    {
      key: 'reaction',
      label: 'Reaction',
      value: reactionOpen ? 'Held' : 'Spent',
      tone: reactionOpen ? 'ready' : 'spent',
    },
    {
      key: 'finish',
      label: 'Finish',
      value: actionOpen || movementLeft > 0 ? 'End when done' : 'End turn',
      tone: actionOpen || movementLeft > 0 ? '' : 'ready',
    },
  ]

  if (hasBonusOption || !bonusOpen) {
    items.splice(2, 0, {
      key: 'bonus',
      label: 'Bonus',
      value: bonusOpen ? 'Ready' : 'Spent',
      tone: bonusOpen ? 'ready' : 'spent',
    })
  }

  return { visible: true, items }
}

function skillNeedsTarget(skill = {}) {
  if (skill.requires_target || skill.needs_target) return true
  if (skill.target_required || skill.targeting?.requires_target) return true
  if (['attack', 'spell'].includes(skill.kind)) return true
  return false
}

function readNumber(value, fallback) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}
