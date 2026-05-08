export function getRestoredTurnState(data, myUserId) {
  const lastTurn = data?.game_state?.last_turn
  if (!lastTurn) return { choices: null, pendingCheck: null, clearTurnState: false }

  const isMine = !data.is_multiplayer ||
    !lastTurn.last_actor_user_id ||
    lastTurn.last_actor_user_id === myUserId

  if (!isMine) {
    return { choices: [], pendingCheck: null, clearTurnState: true }
  }

  return {
    choices: Array.isArray(lastTurn.player_choices) && lastTurn.player_choices.length
      ? lastTurn.player_choices
      : null,
    pendingCheck: lastTurn.needs_check?.required ? lastTurn.needs_check : null,
    clearTurnState: false,
  }
}

export function prepareOpeningStage(data, {
  sessionId,
  dialogueQueueLength,
  openingTriggered,
}) {
  let displayLogs = data?.logs || []
  const sid = data?.session_id || sessionId

  if (openingTriggered?.has(sid) || dialogueQueueLength !== 0) {
    return { displayLogs, openingQueue: null, sessionKey: sid }
  }

  const dmNarratives = displayLogs.filter(l =>
    (l.role === 'dm' || l.role === 'system') &&
    (l.log_type === 'narrative' || !l.log_type) &&
    l.content
  )
  if (dmNarratives.length !== 1) {
    return { displayLogs, openingQueue: null, sessionKey: sid }
  }

  const opening = dmNarratives[0]
  const text = String(opening.content || '').replace(/^\[开场\]\s*/, '')
  if (!text) {
    return { displayLogs, openingQueue: null, sessionKey: sid }
  }

  displayLogs = displayLogs.filter(l => l.id !== opening.id)
  return {
    displayLogs,
    openingQueue: [{ speaker: 'DM', role: 'dm', text, color: 'gold' }],
    sessionKey: sid,
  }
}
