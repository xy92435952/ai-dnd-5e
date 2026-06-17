import { getPlayerTurnState } from './combat'
import { resolveReactionPromptTargetId } from './combatReactionPrompt'

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
  setLairActionPrompt,
  setLegendaryActionPrompt,
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
    pendingReaction = resolveCombatReactionPrompt({
      turnState: playerTurnState,
      playerId,
    })
    if (setReactionPrompt) setReactionPrompt(pendingReaction)
  }

  const lairActionPrompt = combatData?.lair_action_prompt || null
  const legendaryActionPrompt = lairActionPrompt
    ? null
    : (combatData?.legendary_action_prompt || null)
  if (setLairActionPrompt) setLairActionPrompt(lairActionPrompt)
  if (setLegendaryActionPrompt) setLegendaryActionPrompt(legendaryActionPrompt)

  const combatLogs = (sessionData?.logs || []).filter(l =>
    l.log_type === 'combat' || l.log_type === 'system'
  )
  setLogs(combatLogs)

  return {
    playerId,
    playerEntry: (combatData?.turn_order || []).find(t => t.character_id === playerId),
    pendingReaction,
    lairActionPrompt,
    legendaryActionPrompt,
  }
}

export function getPendingReactionPrompt(turnState, playerId) {
  if (!turnState || !playerId) return null

  const bardicSpellSaveReaction = turnState.pending_bardic_spell_save_reaction
  if (
    bardicSpellSaveReaction?.trigger === 'spell_save'
    || bardicSpellSaveReaction?.trigger === 'bardic_spell_save'
  ) {
    return {
      ...bardicSpellSaveReaction,
      reactor_character_id: bardicSpellSaveReaction.reactor_character_id || playerId,
    }
  }

  if (turnState.reaction_used) return null

  const attackReaction = turnState.pending_attack_reaction
  if (attackReaction?.trigger === 'incoming_attack') {
    const targetId = attackReaction.target_id || attackReaction.attacker_id || null
    return normalizePendingReactionPrompt({
      ...attackReaction,
      reactor_character_id: attackReaction.reactor_character_id || playerId,
      target_id: targetId,
    }, targetId)
  }

  const spellReaction = turnState.pending_spell_reaction
  if (spellReaction?.trigger === 'spell_cast') {
    const targetId = spellReaction.target_id || spellReaction.caster_id || null
    return normalizePendingReactionPrompt({
      ...spellReaction,
      reactor_character_id: spellReaction.reactor_character_id || playerId,
      target_id: targetId,
    }, targetId)
  }

  return null
}

function normalizePendingReactionPrompt(prompt, targetId = null) {
  if (!prompt || !targetId || !Array.isArray(prompt.options)) return prompt
  return {
    ...prompt,
    options: prompt.options.map(option => ({
      ...option,
      target_id: option.target_id || targetId,
    })),
  }
}

export function resolveCombatReactionPrompt({
  turnState = null,
  playerId = null,
  reactionPrompt = null,
  playerCanReact = false,
} = {}) {
  const pendingReaction = getPendingReactionPrompt(turnState, playerId)
  if (pendingReaction) return pendingReaction
  if (playerCanReact && reactionPrompt) {
    const targetId = resolveReactionPromptTargetId(reactionPrompt)
    const normalizedPrompt = {
      ...reactionPrompt,
      reactor_character_id: reactionPrompt.reactor_character_id || playerId,
    }
    if (targetId) normalizedPrompt.target_id = targetId
    return normalizePendingReactionPrompt(normalizedPrompt, targetId)
  }
  return null
}
