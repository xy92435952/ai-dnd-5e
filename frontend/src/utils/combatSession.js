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

  const combatLogs = (sessionData?.logs || []).filter(l =>
    l.log_type === 'combat' || l.log_type === 'system'
  )
  setLogs(combatLogs)

  return {
    playerId,
    playerEntry: (combatData?.turn_order || []).find(t => t.is_player),
  }
}
