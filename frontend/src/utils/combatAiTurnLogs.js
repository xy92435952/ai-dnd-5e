export function buildAiTurnDiceResult(result = {}) {
  if (result.confusion_end_save) {
    return result.confusion_end_save
  }
  const conditionEndSaves = Array.isArray(result.condition_end_saves) ? result.condition_end_saves : []
  const tacticalDecision = result.tactical_decision || result.tacticalDecision
  const dcSource = result.dc_source || result.dcSource
  const lairAction = result.lair_action || result.lairAction
  const legendaryAction = result.legendary_action || result.legendaryAction
  const spellResult = result.spell_result || result.spellResult
  const deathSave = result.death_save || result.deathSave
  const persistedDice = result.dice_result || result.diceResult
  if (lairAction && typeof lairAction === 'object') {
    return lairAction
  }
  if (legendaryAction && typeof legendaryAction === 'object') {
    return legendaryAction
  }
  if (spellResult && typeof spellResult === 'object') {
    return {
      ...spellResult,
      ...(tacticalDecision && !spellResult.tactical_decision ? { tactical_decision: tacticalDecision } : {}),
      ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
    }
  }
  if (deathSave && typeof deathSave === 'object') {
    return {
      ...deathSave,
      ...(tacticalDecision && !deathSave.tactical_decision ? { tactical_decision: tacticalDecision } : {}),
      ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
    }
  }
  if (persistedDice?.type === 'divine_smite') {
    return {
      ...persistedDice,
      ...(tacticalDecision && !persistedDice.tactical_decision ? { tactical_decision: tacticalDecision } : {}),
      ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
    }
  }
  if (persistedDice?.type === 'class_feature') {
    return {
      ...persistedDice,
      ...(tacticalDecision && !persistedDice.tactical_decision ? { tactical_decision: tacticalDecision } : {}),
      ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
    }
  }
  if (persistedDice?.type === 'maneuver'
    || persistedDice?.type === 'grapple'
    || persistedDice?.type === 'shove'
    || persistedDice?.type === 'grapple_escape'
    || persistedDice?.type === 'death_save'
    || persistedDice?.type === 'ready_action_declared'
    || persistedDice?.type === 'concentration_end'
    || persistedDice?.type === 'condition_update'
    || persistedDice?.type === 'reaction'
    || persistedDice?.type === 'spell_prepare'
    || persistedDice?.type === 'attack_prepare'
    || persistedDice?.type === 'enemy_inspect') {
    return {
      ...persistedDice,
      ...(tacticalDecision && !persistedDice.tactical_decision ? { tactical_decision: tacticalDecision } : {}),
      ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
    }
  }
  if (persistedDice?.type === 'ai_spell') {
    return {
      ...persistedDice,
      ...(tacticalDecision && !persistedDice.tactical_decision ? { tactical_decision: tacticalDecision } : {}),
      ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
    }
  }

  if (result.attack_result?.d20) {
    return {
      attack: result.attack_result,
      damage: result.damage,
      ...(result.damage_roll ? { damage_roll: result.damage_roll } : {}),
      ...(result.total_damage !== undefined && result.total_damage !== null ? { total_damage: result.total_damage } : {}),
      ...(result.damage_type ? { damage_type: result.damage_type } : {}),
      ...(result.damage_before_resistance !== undefined && result.damage_before_resistance !== null ? { damage_before_resistance: result.damage_before_resistance } : {}),
      ...(result.damage_after_resistance !== undefined && result.damage_after_resistance !== null ? { damage_after_resistance: result.damage_after_resistance } : {}),
      ...(result.resistance_applied !== undefined && result.resistance_applied !== null ? { resistance_applied: result.resistance_applied } : {}),
      ...(Array.isArray(result.resistance_sources) && result.resistance_sources.length > 0 ? { resistance_sources: result.resistance_sources } : {}),
      ...(result.crit_extra ? { crit_extra: result.crit_extra } : {}),
      ...(result.sneak_attack !== undefined && result.sneak_attack !== null ? { sneak_attack: result.sneak_attack } : {}),
      ...(result.sneak_attack_damage ? { sneak_attack_damage: result.sneak_attack_damage } : {}),
      ...(Array.isArray(result.extra_damage_notes) && result.extra_damage_notes.length > 0 ? { extra_damage_notes: result.extra_damage_notes } : {}),
      ...(result.weapon_resource ? { weapon_resource: result.weapon_resource } : {}),
      ...(Array.isArray(result.weapon_resources) && result.weapon_resources.length > 0 ? { weapon_resources: result.weapon_resources } : {}),
      ...(result.enemy_action ? { enemy_action: result.enemy_action } : {}),
      ...(Array.isArray(result.enemy_actions) && result.enemy_actions.length > 0 ? { enemy_actions: result.enemy_actions } : {}),
      ...(tacticalDecision ? { tactical_decision: tacticalDecision } : {}),
      ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
    }
  }

  if (result.weapon_resource) {
    return {
      type: 'weapon_resource',
      weapon_resource: result.weapon_resource,
      ...(Array.isArray(result.weapon_resources) && result.weapon_resources.length > 0 ? { weapon_resources: result.weapon_resources } : {}),
      ...(tacticalDecision ? { tactical_decision: tacticalDecision } : {}),
      ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
    }
  }

  if (!result.special_action) {
    if (conditionEndSaves.length > 0 || tacticalDecision) {
      return {
        type: conditionEndSaves.length > 0 ? 'condition_end_saves' : 'tactical_decision',
        ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
        ...(tacticalDecision ? { tactical_decision: tacticalDecision } : {}),
      }
    }
    return null
  }

  return {
    special: result.special_action,
    damage: result.damage,
    damage_roll: result.damage_roll,
    save: result.save,
    target_results: result.target_results,
    aoe: result.aoe_results,
    ...(dcSource ? { dc_source: dcSource } : {}),
    ...(tacticalDecision ? { tactical_decision: tacticalDecision } : {}),
    ...(conditionEndSaves.length > 0 ? { condition_end_saves: conditionEndSaves } : {}),
  }
}
