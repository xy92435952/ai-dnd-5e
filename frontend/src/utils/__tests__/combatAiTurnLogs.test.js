import { describe, expect, it } from 'vitest'
import { buildAiTurnDiceResult } from '../combatAiTurnLogs'

describe('combatAiTurnLogs', () => {
  it('builds attack dice payloads for AI turn logs', () => {
    expect(buildAiTurnDiceResult({
      attack_result: {
        d20: 16,
        attack_total: 21,
        target_ac: 14,
        hit: true,
      },
      damage: 5,
      total_damage: 9,
      damage_roll: { notation: '1d6+2', rolls: [3], total: 5 },
      damage_type: 'piercing',
      damage_before_resistance: 18,
      damage_after_resistance: 9,
      resistance_applied: true,
      resistance_sources: ['piercing'],
      crit_extra: 4,
      sneak_attack: true,
      sneak_attack_damage: 4,
      extra_damage_notes: ['Sneak Attack +4'],
      weapon_resource: {
        consumed: true,
        resource_type: 'ammunition',
        weapon: 'Shortbow',
        ammo_remaining: 0,
      },
      tactical_decision: {
        role: 'striker',
        reason: 'focus wounded hero',
      },
    })).toEqual({
      attack: {
        d20: 16,
        attack_total: 21,
        target_ac: 14,
        hit: true,
      },
      damage: 5,
      total_damage: 9,
      damage_roll: { notation: '1d6+2', rolls: [3], total: 5 },
      damage_type: 'piercing',
      damage_before_resistance: 18,
      damage_after_resistance: 9,
      resistance_applied: true,
      resistance_sources: ['piercing'],
      crit_extra: 4,
      sneak_attack: true,
      sneak_attack_damage: 4,
      extra_damage_notes: ['Sneak Attack +4'],
      weapon_resource: {
        consumed: true,
        resource_type: 'ammunition',
        weapon: 'Shortbow',
        ammo_remaining: 0,
      },
      tactical_decision: {
        role: 'striker',
        reason: 'focus wounded hero',
      },
    })
  })

  it('preserves persisted AI spell dice payloads', () => {
    expect(buildAiTurnDiceResult({
      dice_result: {
        type: 'ai_spell',
        spell_name: 'Burning Hands',
        damage: 8,
      },
      tactical_decision: {
        role: 'blaster',
      },
      condition_end_saves: [{
        type: 'condition_end_save',
        condition: 'paralyzed',
        ended: true,
      }],
    })).toEqual({
      type: 'ai_spell',
      spell_name: 'Burning Hands',
      damage: 8,
      tactical_decision: {
        role: 'blaster',
      },
      condition_end_saves: [{
        type: 'condition_end_save',
        condition: 'paralyzed',
        ended: true,
      }],
    })
  })

  it('preserves player spell-confirm payloads from spell_result', () => {
    const spellResult = {
      dice: { notation: '3d4+3', rolls: [1, 2, 3], total: 9 },
      damage: 9,
      heal: 0,
      target_state: { target_id: 'enemy-1', hp_after: 3 },
    }

    expect(buildAiTurnDiceResult({
      spell_result: spellResult,
      concentration_effect_updates: [{
        caster_id: 'host-char',
        spell_name: 'Bless',
        ended: true,
      }],
    })).toEqual(spellResult)
  })

  it('preserves player spell-prepare payloads from dice_result', () => {
    const spellPrepare = {
      type: 'spell_prepare',
      actor_id: 'host-char',
      actor_name: 'Host Wizard',
      spell_name: 'Magic Missile',
      spell_level: 1,
      spell_type: 'damage',
      damage_dice: '3d4+3',
      save_type: null,
      save_dc: null,
      target_count: 1,
      spell_attack_required: false,
    }

    expect(buildAiTurnDiceResult({
      dice_result: spellPrepare,
      special_action: { type: 'spell_prepare' },
    })).toEqual(spellPrepare)
  })

  it('preserves player divine smite payloads from dice_result', () => {
    const smiteResult = {
      type: 'divine_smite',
      slot_level: 1,
      dice: '2d8',
      damage: 9,
      roll: { notation: '2d8', rolls: [4, 5], total: 9 },
      target_state: { target_id: 'enemy-1', hp_after: 3 },
      remaining_slots: { '1st': 0 },
    }

    expect(buildAiTurnDiceResult({
      dice_result: smiteResult,
      special_action: {
        type: 'divine_smite',
        damage: 9,
      },
    })).toEqual(smiteResult)
  })

  it('preserves player class feature payloads from dice_result', () => {
    const classFeatureResult = {
      type: 'class_feature',
      feature: 'second_wind',
      dice_roll: { faces: 10, result: 5, label: 'Second Wind' },
      target_state: { target_id: 'host-char', hp_current: 10 },
      class_resources: { second_wind_used: true },
      turn_state: { bonus_action_used: true },
    }

    expect(buildAiTurnDiceResult({
      dice_result: classFeatureResult,
      special_action: {
        type: 'class_feature',
        feature: 'second_wind',
      },
    })).toEqual(classFeatureResult)
  })

  it('preserves player maneuver payloads from dice_result', () => {
    const maneuverResult = {
      type: 'maneuver',
      maneuver: 'trip',
      superiority_die_roll: 5,
      superiority_die: 'd8',
      dice_remaining: 0,
      actor_id: 'host-char',
      actor_name: 'Host Fighter',
      target_id: 'enemy-1',
      target_name: 'Clockwork Sentry',
      tripped: true,
      extra_damage: 5,
      target_state: {
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        conditions: ['prone'],
      },
      class_resources: { superiority_dice_remaining: 0 },
    }

    expect(buildAiTurnDiceResult({
      dice_result: maneuverResult,
      special_action: {
        type: 'maneuver',
        maneuver: 'trip',
      },
    })).toEqual(maneuverResult)
  })

  it('preserves player contested-check payloads from dice_result', () => {
    const grappleResult = {
      type: 'grapple',
      success: true,
      attacker_name: 'Host Fighter',
      target_id: 'enemy-1',
      target_name: 'Clockwork Sentry',
      attacker_roll: { skill: 'Athletics', total: 18 },
      target_roll: { skill: 'Athletics', total: 10 },
      condition_result: { condition: 'grappled', applied: true, immune: false },
      target_state: {
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        conditions: ['grappled'],
      },
      turn_state: { attacks_made: 1, attacks_max: 2 },
    }
    const escapeResult = {
      type: 'grapple_escape',
      success: true,
      attacker_name: 'Host Fighter',
      source_id: 'enemy-1',
      source_name: 'Clockwork Sentry',
      target_state: {
        target_id: 'host-char',
        target_name: 'Host Fighter',
        conditions: [],
      },
      condition_result: { condition: 'grappled', applied: false, removed: true, immune: false },
      turn_state: { action_used: true },
    }

    expect(buildAiTurnDiceResult({
      dice_result: grappleResult,
      special_action: { type: 'grapple' },
    })).toEqual(grappleResult)
    expect(buildAiTurnDiceResult({
      dice_result: escapeResult,
      special_action: { type: 'grapple_escape' },
    })).toEqual(escapeResult)
  })

  it('preserves player death-save payloads from websocket fields', () => {
    const deathSaveResult = {
      type: 'death_save',
      character_id: 'guest-char',
      character_name: 'Guest Wizard',
      d20: 20,
      outcome: 'revive',
      revived: true,
      hp_current: 1,
      target_state: {
        target_id: 'guest-char',
        target_name: 'Guest Wizard',
        hp_current: 1,
        death_saves: { successes: 0, failures: 0, stable: false },
      },
    }

    expect(buildAiTurnDiceResult({
      death_save: deathSaveResult,
      dice_result: { type: 'wrapped_wrong_payload' },
    })).toEqual(deathSaveResult)
    expect(buildAiTurnDiceResult({
      dice_result: deathSaveResult,
      special_action: { type: 'death_save' },
    })).toEqual(deathSaveResult)
  })

  it('preserves ready-action declaration payloads from websocket dice fields', () => {
    const readyDeclaration = {
      type: 'ready_action_declared',
      ready_action: {
        type: 'ready_action',
        actor_id: 'host-char',
        actor_name: 'Host Fighter',
        target_id: 'enemy-1',
        target_name: 'Clockwork Sentry',
        action_type: 'attack',
        trigger: 'target_moves',
        condition_text: 'When the sentry moves, attack.',
      },
    }

    expect(buildAiTurnDiceResult({
      dice_result: readyDeclaration,
      special_action: { type: 'ready_action_declared' },
    })).toEqual(readyDeclaration)
    expect(buildAiTurnDiceResult({
      dice_result: {
        type: 'ready_action_declared',
        ready_action: {
          type: 'ready_action',
          redacted: true,
          visibility: 'other_character',
          actor_id: 'host-char',
          actor_name: 'Host Fighter',
        },
      },
    })).toEqual({
      type: 'ready_action_declared',
      ready_action: {
        type: 'ready_action',
        redacted: true,
        visibility: 'other_character',
        actor_id: 'host-char',
        actor_name: 'Host Fighter',
      },
    })
  })

  it('preserves voluntary concentration-end payloads from websocket dice fields', () => {
    const concentrationEnd = {
      type: 'concentration_end',
      actor_id: 'host-char',
      actor_name: 'Host Wizard',
      concentration_ended: true,
      concentration_spell_name: null,
      ready_action_failed: {
        type: 'ready_action_failed',
        redacted: true,
        visibility: 'other_character',
        actor_id: 'host-char',
        actor_name: 'Host Wizard',
      },
      actor_state: {
        target_id: 'host-char',
        concentration: null,
      },
    }

    expect(buildAiTurnDiceResult({
      dice_result: concentrationEnd,
      special_action: { type: 'concentration_end' },
    })).toEqual(concentrationEnd)
  })

  it('preserves manual condition update payloads from websocket dice fields', () => {
    const conditionUpdate = {
      type: 'condition_update',
      condition: 'blessed',
      condition_action: 'add',
      condition_result: {
        condition: 'blessed',
        condition_action: 'add',
        applied: true,
        removed: false,
        immune: false,
        target_id: 'guest-char',
        target_name: 'Guest Wizard',
      },
      target_id: 'guest-char',
      target_name: 'Guest Wizard',
      target_state: {
        target_id: 'guest-char',
        target_name: 'Guest Wizard',
        conditions: ['blessed'],
        condition_durations: { blessed: 2 },
      },
    }

    expect(buildAiTurnDiceResult({
      dice_result: conditionUpdate,
      special_action: { type: 'condition_update' },
    })).toEqual(conditionUpdate)
  })

  it('preserves reaction payloads from websocket dice fields', () => {
    const reactionResult = {
      type: 'reaction',
      reaction_type: 'shield',
      damage_prevented: 5,
      hp_before_reaction: 4,
      hp_after_reaction: 9,
      slot_used: '1st',
    }

    expect(buildAiTurnDiceResult({
      dice_result: reactionResult,
      special_action: { type: 'reaction' },
    })).toEqual(reactionResult)
  })

  it('preserves enemy inspect payloads from websocket dice fields', () => {
    const inspectResult = {
      type: 'enemy_inspect',
      actor_id: 'scout-1',
      target_id: 'enemy-1',
      skill: 'investigation',
      dc: 12,
      check: { total: 19, success: true },
      revealed_stats: ['actions'],
    }

    expect(buildAiTurnDiceResult({
      dice_result: inspectResult,
      special_action: { type: 'enemy_inspect' },
    })).toEqual(inspectResult)
  })

  it('preserves resolved lair and legendary action payloads', () => {
    const lairAction = {
      type: 'lair_action',
      action_id: 'seismic-pulse',
      target_results: [{ target_id: 'hero-1', damage: 8 }],
    }
    const legendaryAction = {
      type: 'legendary_action',
      action_id: 'tail',
      attack: { hit: true, attack_total: 18, target_ac: 14 },
    }

    expect(buildAiTurnDiceResult({ lair_action: lairAction })).toBe(lairAction)
    expect(buildAiTurnDiceResult({ legendary_action: legendaryAction })).toBe(legendaryAction)
  })
})
