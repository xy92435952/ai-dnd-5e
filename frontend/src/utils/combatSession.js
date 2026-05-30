import { getPlayerTurnState } from './combat'

export function applyCombatSessionSnapshot({
  combatData,
  sessionData,
  setCombat,
  setSession,
  setPlayerId,
  setPlayerSpellSlots,
  setPlayerKnownSpells,
  setPlayerCantrips,
  setPlayerClass,
  setPlayerLevel,
  setClassResources,
  setPlayerSubclass,
  setPlayerSubclassEffects,
  setTurnState,
  setReactionPrompt,
  setLogs,
}) {
  setCombat(combatData)
  setSession(sessionData)

  const player = sessionData?.player
  const playerId = player?.id
  setPlayerId(playerId)

  if (player?.spell_slots) setPlayerSpellSlots(player.spell_slots)
  if (player?.known_spells) setPlayerKnownSpells(player.known_spells)
  if (player?.cantrips) setPlayerCantrips(player.cantrips)
  if (player?.char_class) setPlayerClass(player.char_class)
  if (player?.level) setPlayerLevel(player.level)
  if (player?.class_resources) setClassResources(player.class_resources || {})
  if (player?.subclass) setPlayerSubclass(player.subclass)
  if (player?.derived?.subclass_effects) setPlayerSubclassEffects(player.derived.subclass_effects)

  let pendingReaction = null
  if (playerId) {
    const playerTurnState = getPlayerTurnState(combatData, playerId)
    setTurnState(playerTurnState)
    pendingReaction = getPendingReactionPrompt(playerTurnState, playerId)
    if (setReactionPrompt) setReactionPrompt(pendingReaction)
  }

  const combatLogs = (sessionData?.logs || []).filter(l =>
    l.log_type === 'combat' || l.log_type === 'system'
  )
  setLogs(combatLogs)

  return {
    playerId,
    playerEntry: (combatData?.turn_order || []).find(t => t.character_id === playerId),
    pendingReaction,
  }
}

export function getPendingReactionPrompt(turnState, playerId) {
  if (!turnState || !playerId || turnState.reaction_used) return null

  const attackReaction = turnState.pending_attack_reaction
  if (attackReaction?.trigger === 'incoming_attack') {
    return {
      ...attackReaction,
      reactor_character_id: attackReaction.reactor_character_id || playerId,
    }
  }

  const spellReaction = turnState.pending_spell_reaction
  if (spellReaction?.trigger === 'spell_cast') {
    return {
      ...spellReaction,
      reactor_character_id: spellReaction.reactor_character_id || playerId,
    }
  }

  return null
}
