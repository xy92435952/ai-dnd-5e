import { getPlayerTurnState } from './combat'

function pendingAiAttackToReactionPrompt(turnState) {
  const pending = turnState?.pending_ai_attack
  if (!pending) return null

  return {
    can_react: true,
    context: 'Choose a reaction',
    attack_roll: pending.attack_roll?.attack_total || 0,
    incoming_damage: pending.damage || 0,
    attacker_name: pending.actor_name,
    attacker_id: pending.actor_id,
    pending_attack_id: pending.pending_attack_id,
    available_reactions: pending.available_reactions || [],
    options: pending.options || [],
  }
}

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

  if (playerId) setTurnState(getPlayerTurnState(combatData, playerId))
  const playerTurnState = playerId ? getPlayerTurnState(combatData, playerId) : null
  if (setReactionPrompt) {
    setReactionPrompt(pendingAiAttackToReactionPrompt(playerTurnState))
  }

  const combatLogs = (sessionData?.logs || []).filter(l =>
    l.log_type === 'combat' || l.log_type === 'system'
  )
  setLogs(combatLogs)

  return {
    playerId,
    playerEntry: (combatData?.turn_order || []).find(t => t.is_player),
  }
}
