/**
 * useCombatPageActions — Combat 页面级动作胶水。
 *
 * 把 WS 事件分发、技能点击路由、移动操作、AoE hover 这类“页面知道很多、
 * 但单个子组件不该知道”的动作收拢在一起，Combat.jsx 只保留布局和状态拼装。
 */
import { useCallback, useEffect, useState } from 'react'
import { gameApi, roomsApi } from '../api/client'
import { rollDice3D } from '../components/DiceRollerOverlay'
import { buildSpellAoePreview, getAoePreviewCenterKey, getCombatTurnToken, getSkillUnavailableReason } from '../utils/combat'
import { buildAiTurnDiceResult } from '../utils/combatAiTurnLogs'
import { createCombatSkillClickHandler, getCuttingWordsAbilityCheckOption } from '../utils/combatSkillActions'
import { formatCombatError } from '../utils/combatErrors'
import { buildHazardDiceResult, formatHazardLog } from '../utils/combatHazards'
import { buildCombatResultImpactSummary, buildCombatStateChangeSummary } from '../utils/combatLog'
import { resolveCombatReactionPrompt } from '../utils/combatSession'
import {
  buildConditionFrightenedMoveBlockedReason,
  buildConditionSpeedLockReason,
  buildConditionStandUpMoveNotice,
} from '../utils/conditionRules'
import { buildGrappleDragMovePreview } from '../utils/grappleDrag'
import { buildDifficultTerrainMovePreview } from '../utils/movementCost'
import { formatConditionEndSaveLog, formatDelayedTurnLog, formatReadyActionExpiryLog } from '../utils/turnLogs'
import { mergeRealtimeRoomEvent } from './useRoomRealtime'

function formatOpportunityAttackMoveLog(opportunity = {}) {
  const attacker = opportunity.attacker || '\u654c\u4eba'
  const target = opportunity.target || '\u76ee\u6807'
  const attack = opportunity.attack_result || opportunity.attack_roll || opportunity.attack || {}
  const total = attack.attack_total ?? attack.total
  const ac = attack.target_ac ?? attack.ac
  const hitText = attack.is_crit
    ? '\u66b4\u51fb'
    : attack.hit === false || attack.is_fumble
      ? '\u672a\u547d\u4e2d'
      : '\u547d\u4e2d'
  const rollText = total != null && ac != null ? ` (${total} vs AC${ac})` : ''
  const damage = opportunity.damage ?? opportunity.total_damage ?? 0
  const damageText = Number(damage) > 0 ? `\uff0c\u9020\u6210 ${damage} \u4f24\u5bb3` : ''
  const movementStop = opportunity.movement_stop || opportunity.movementStop
  const stopText = movementStop?.applied
    ? ` ${target} \u79fb\u52a8\u88ab ${movementStop.attacker || attacker} \u622a\u505c\uff0c\u79fb\u52a8\u529b\u5f52\u96f6\u3002`
    : ''
  return `\u501f\u673a\u653b\u51fb\uff1a${attacker} \u653b\u51fb ${target}\uff0c${hitText}${rollText}${damageText}\u3002${stopText}`
}

function getViewerTurnStateFromCombat(combatSnapshot, characterId = null) {
  const turnStates = combatSnapshot?.turn_states
  if (!turnStates) return null
  if (characterId && Object.prototype.hasOwnProperty.call(turnStates, characterId)) {
    return turnStates[characterId] || null
  }
  const entry = combatSnapshot.turn_order?.[combatSnapshot.current_turn_index]
  return entry?.character_id ? (turnStates[entry.character_id] || null) : null
}

function formatReadyActionMoveLog(readyAction = {}) {
  const actor = readyAction.actor_name || readyAction.actor || '\u76ee\u6807'
  const target = readyAction.target_name || readyAction.target || '\u76ee\u6807'
  const actionType = readyAction.action_type || readyAction.actionType
  const conditionText = readyAction.condition_text || readyAction.conditionText
  const conditionPrefix = conditionText ? `\u6761\u4ef6\u300c${conditionText}\u300d\uff0c` : ''
  if (actionType === 'move') {
    const from = readyAction.from || {}
    const to = readyAction.to || {}
    const steps = readyAction.steps ?? 0
    const distanceFt = readyAction.distance_ft ?? readyAction.distanceFt ?? Number(steps || 0) * 5
    const pathText = from.x != null && to.x != null
      ? `\uff08${from.x},${from.y} \u2192 ${to.x},${to.y}\uff09`
      : ''
    return `\u51c6\u5907\u52a8\u4f5c\u89e6\u53d1\uff1a${actor} ${conditionPrefix}${conditionText ? '' : `\u5728 ${target} \u79fb\u52a8\u65f6`}\u79fb\u52a8 ${distanceFt}ft${pathText}\u3002`
  }
  const damage = readyAction.damage ?? readyAction.total_damage ?? 0
  const spellName = readyAction.spell_name || readyAction.spellName
  if (actionType === 'spell') {
    const damageText = Number(damage) > 0 ? `\uff0c\u9020\u6210 ${damage} \u4f24\u5bb3` : ''
    return `\u51c6\u5907\u52a8\u4f5c\u89e6\u53d1\uff1a${actor} ${conditionPrefix}${conditionText ? '' : `\u5728 ${target} \u79fb\u52a8\u65f6`}\u65bd\u653e ${spellName || '\u6cd5\u672f'}${damageText}\u3002`
  }
  return `\u51c6\u5907\u52a8\u4f5c\u89e6\u53d1\uff1a${actor} ${conditionPrefix}\u5bf9 ${target} \u53d1\u52a8\u51c6\u5907\u653b\u51fb${Number(damage) > 0 ? `\uff0c\u9020\u6210 ${damage} \u4f24\u5bb3` : ''}\u3002`
}

function resolveMovementPayload(event = {}) {
  const dice = event.dice_result || event.diceResult
  if (event.movement && typeof event.movement === 'object') return event.movement
  if (dice?.type === 'movement') return dice
  return null
}

function formatMovementLog(movement = {}, event = {}) {
  const actor = movement.entity_name || movement.entityName || movement.entity_id || event.entity_id || 'A combatant'
  const from = movement.from || {}
  const to = movement.to || movement.position || event.position || {}
  const distanceFt = movement.distance_ft ?? movement.distanceFt ?? Number(movement.steps || movement.movement_steps || 0) * 5
  if (movement.stood_up && !Number(distanceFt || 0)) return `${actor} stands up.`
  const route = from.x != null && to.x != null
    ? ` (${from.x},${from.y} -> ${to.x},${to.y})`
    : ''
  const cost = movement.movement_cost ?? movement.movementCost
  const costText = cost != null ? `, cost ${cost}` : ''
  const difficultExtra = Number(movement.difficult_terrain_extra ?? movement.difficultTerrainExtra ?? 0)
  const terrainText = difficultExtra > 0 ? `, difficult terrain +${difficultExtra}` : ''
  const stop = movement.movement_stop || movement.movementStop
  const stopText = stop?.applied ? ', stopped' : ''
  const standText = movement.stood_up ? ' stands and' : ''
  return `${actor}${standText} moves ${distanceFt || 0} ft${route}${costText}${terrainText}${stopText}.`
}

function appendMovementLog(addLog, event = {}) {
  const movement = resolveMovementPayload(event)
  if (!movement) return
  const movementUsed = movement.movement_used ?? movement.movementUsed
  const movementMax = movement.movement_max ?? movement.movementMax
  const stateSource = {
    ...movement,
    ...(movementUsed != null && movementMax != null
      ? { turn_state: { movement_used: movementUsed, movement_max: movementMax } }
      : {}),
  }
  addLog?.({
    role: 'system',
    content: event.narration || movement.narration || formatMovementLog(movement, event),
    log_type: 'combat',
    dice_result: {
      type: 'movement',
      ...movement,
    },
    state_changes: buildCombatStateChangeSummary(stateSource),
  })
}

function appendReadyActionResultLogs(addLog, readyActionResults = []) {
  ;(readyActionResults || []).forEach(readyAction => {
    addLog?.({
      role: 'system',
      content: readyAction.narration || formatReadyActionMoveLog(readyAction),
      log_type: 'combat',
      dice_result: {
        type: 'ready_action',
        applied: readyAction.applied !== false,
        trigger: readyAction.trigger || 'target_moves',
        actor_id: readyAction.actor_id,
        actor_name: readyAction.actor_name,
        target_id: readyAction.target_id,
        target_name: readyAction.target_name,
        condition_text: readyAction.condition_text || readyAction.conditionText || null,
        action_type: readyAction.action_type || readyAction.actionType || 'attack',
        from: readyAction.from || null,
        to: readyAction.to || null,
        steps: readyAction.steps ?? null,
        distance_ft: readyAction.distance_ft ?? readyAction.distanceFt ?? null,
        damage: readyAction.damage ?? readyAction.total_damage ?? 0,
        heal: readyAction.heal ?? 0,
        attack: readyAction.attack_result || readyAction.attack_roll || readyAction.attack || {},
        spell_name: readyAction.spell_name || readyAction.spellName || null,
        dice: readyAction.dice_detail || readyAction.dice || null,
        target_state: readyAction.target_state || null,
        actor_state: readyAction.actor_state || null,
        hazard_result: readyAction.hazard_result || null,
        opportunity_attacks: readyAction.opportunity_attacks || readyAction.opportunityAttacks || [],
      },
    })
    ;(readyAction.opportunity_attacks || readyAction.opportunityAttacks || []).forEach(opportunity => {
      const opportunityAttack = opportunity.attack_result || opportunity.attack_roll || opportunity.attack || {}
      addLog?.({
        role: 'system',
        content: formatOpportunityAttackMoveLog(opportunity),
        log_type: 'combat',
        dice_result: {
          attack: opportunityAttack,
          damage: opportunity.damage ?? opportunity.total_damage ?? 0,
          damage_roll: opportunity.damage_roll || null,
          opportunity: true,
          ready_action: true,
          attacker: opportunity.attacker,
          target: opportunity.target,
          movement_stop: opportunity.movement_stop || opportunity.movementStop || null,
        },
      })
    })
    if (readyAction.hazard_result?.triggered) {
      addLog?.({
        role: 'system',
        content: formatHazardLog(readyAction.hazard_result),
        log_type: 'combat',
        dice_result: buildHazardDiceResult(readyAction.hazard_result),
      })
    }
  })
}

function appendCombatUpdateTurnAdvanceLogs(addLog, event = {}) {
  ;(event.opportunity_attacks || []).forEach(opportunity => {
    const opportunityAttack = opportunity.attack_result || opportunity.attack_roll || opportunity.attack || {}
    addLog?.({
      role: 'system',
      content: formatOpportunityAttackMoveLog(opportunity),
      log_type: 'combat',
      dice_result: {
        attack: opportunityAttack,
        damage: opportunity.damage ?? opportunity.total_damage ?? 0,
        damage_roll: opportunity.damage_roll || null,
        opportunity: true,
        attacker: opportunity.attacker,
        target: opportunity.target,
        movement_stop: opportunity.movement_stop || opportunity.movementStop || null,
      },
    })
  })
  if (event.confusion_end_save) {
    addLog?.({
      role: 'system',
      content: formatConditionEndSaveLog(event.confusion_end_save),
      log_type: 'combat',
      dice_result: event.confusion_end_save,
    })
  }
  ;(event.condition_end_saves || []).forEach(save => {
    addLog?.({
      role: 'system',
      content: formatConditionEndSaveLog(save),
      log_type: 'combat',
      dice_result: save,
    })
  })
  if (event.turn_start_hazard_log) {
    addLog?.({
      role: 'system',
      content: event.turn_start_hazard_log,
      log_type: 'combat',
      dice_result: buildHazardDiceResult(event.turn_start_hazard),
    })
  }
  if (event.expired_ready_action) {
    addLog?.({
      role: 'system',
      content: event.ready_action_expired_log || formatReadyActionExpiryLog(event.expired_ready_action),
      log_type: 'combat',
      dice_result: {
        type: 'ready_action_expired',
        applied: false,
        ...event.expired_ready_action,
      },
    })
  }
}

function appendCombatUpdateActionLog(addLog, event = {}) {
  if (!event.narration) return
  const impactSummary = buildCombatResultImpactSummary(event)
  const diceResult = buildAiTurnDiceResult(event)
  const targetName = event.target_name
    || event.target_state?.target_name
    || diceResult?.target_name
    || diceResult?.target_state?.target_name
    || event.target_id
  addLog?.({
    role: event.actor_id?.startsWith?.('enemy') ? 'enemy' : `companion_${event.actor_name || event.actor_id || 'AI'}`,
    content: event.narration,
    log_type: 'combat',
    ...(diceResult ? { dice_result: diceResult } : {}),
    ...(impactSummary.length > 0 ? { impact_summary: impactSummary } : {}),
    state_changes: buildCombatStateChangeSummary(event, {
      targetName,
    }),
  })
}

export function useCombatPageActions({
  sessionId,
  setRoom,
  myCharacterId,
  playerId,
  moveMode,
  helpMode = false,
  isProcessing,
  setIsProcessing,
  canActThisTurn,
  selectedTarget,
  entities = {},
  entityPositions,
  playerPos,
  setError,
  setCombat,
  setTurnState,
  setClassResources,
  setReactionPrompt,
  setLairActionPrompt,
  setLegendaryActionPrompt,
  addLog,
  setSpellModalOpen,
  setSpellQuickPick,
  setHelpMode,
  handleAttack,
  handleDash,
  handleDisengage,
  handleDodge,
  handleHealingPotion,
  handleClassFeature,
  setMoveMode,
  setAoePreview,
  setAoeHover,
  setAoeLockedCenter,
  clearAoePreview,
  onLoadCombat,
  setCombatOver,
  onCombatEnded,
  showDice,
  combat,
}) {
  const actorId = playerId || myCharacterId
  const actor = actorId ? (entities?.[actorId] || combat?.entities?.[actorId] || null) : null
  const [readyMoveDraft, setReadyMoveDraft] = useState(null)

  useEffect(() => {
    if (!moveMode && readyMoveDraft) setReadyMoveDraft(null)
  }, [moveMode, readyMoveDraft])

  const onWsEvent = useCallback((event) => {
    switch (event.type) {
      case 'combat_update':
        {
          const lairPrompt = event.lair_action_prompt || null
          const legendaryPrompt = event.legendary_action_prompt || null
          const combatSnapshot = event.combat || null
          const turnState = combatSnapshot ? getViewerTurnStateFromCombat(combatSnapshot, actorId) : null
          const reactionPrompt = resolveCombatReactionPrompt({
            turnState,
            playerId: actorId,
            reactionPrompt: event.reaction_prompt,
            playerCanReact: event.player_can_react,
          })
          const hasReactionPrompt = !!reactionPrompt
          if (event.combat_over && !event.combat) {
            setCombatOver?.(event.outcome || 'ended')
            setReactionPrompt?.(null)
            setTurnState?.(null)
            setCombat?.(null)
            onCombatEnded?.(event.outcome || 'ended')
            break
          }
          if (event.combat) {
            setCombat(event.combat)
            setTurnState(turnState)
          } else if (event.entity_positions) {
            setCombat(prev => prev ? {
              ...prev,
              entity_positions: {
                ...(prev.entity_positions || {}),
                ...event.entity_positions,
              },
            } : prev)
          }
          if (hasReactionPrompt) {
            setReactionPrompt?.(reactionPrompt)
          } else {
            setReactionPrompt?.(null)
          }
          if (lairPrompt) {
            setLairActionPrompt?.(lairPrompt)
            setLegendaryActionPrompt?.(null)
          } else if (event.lair_action) {
            setLairActionPrompt?.(null)
          }
          if (!lairPrompt && legendaryPrompt) setLegendaryActionPrompt?.(legendaryPrompt)
          if (event.legendary_action) setLegendaryActionPrompt?.(null)
          if (event.action === 'lair_action_skip') setLairActionPrompt?.(null)
          if (event.action === 'legendary_action_skip') setLegendaryActionPrompt?.(null)
          if (event.combat_over) {
            setCombatOver?.(event.outcome)
          }
          appendCombatUpdateActionLog(addLog, event)
          appendReadyActionResultLogs(addLog, event.ready_action_results || [])
          appendCombatUpdateTurnAdvanceLogs(addLog, event)
          if (!hasReactionPrompt && !lairPrompt && !legendaryPrompt) onLoadCombat()
          break
        }
      case 'turn_changed':
        {
          const lairPrompt = event.lair_action_prompt || null
          const legendaryPrompt = event.legendary_action_prompt || null
          const combatSnapshot = event.combat || null
          const turnState = combatSnapshot ? getViewerTurnStateFromCombat(combatSnapshot, actorId) : null
          const reactionPrompt = resolveCombatReactionPrompt({
            turnState,
            playerId: actorId,
            reactionPrompt: event.reaction_prompt,
            playerCanReact: event.player_can_react,
          })
          const hasReactionPrompt = !!reactionPrompt
          if (event.combat) {
            setCombat(event.combat)
            setTurnState(turnState)
          }
          setReactionPrompt?.(reactionPrompt)
          if (event.turn_order_delayed && event.delayed_turn) {
            addLog?.({
              role: 'system',
              content: formatDelayedTurnLog(event.delayed_turn),
              log_type: 'combat',
              dice_result: {
                type: 'delay_turn',
                ...event.delayed_turn,
              },
            })
          }
          setLairActionPrompt?.(lairPrompt)
          setLegendaryActionPrompt?.(lairPrompt ? null : legendaryPrompt)
          if (hasReactionPrompt || lairPrompt || legendaryPrompt) break
          onLoadCombat()
          break
        }
      case 'entity_moved':
        appendMovementLog(addLog, event)
        ;(event.opportunity_attacks || []).forEach(opportunity => {
          const opportunityAttack = opportunity.attack_result || opportunity.attack_roll || opportunity.attack || {}
          addLog?.({
            role: 'system',
            content: formatOpportunityAttackMoveLog(opportunity),
            log_type: 'combat',
            dice_result: {
              attack: opportunityAttack,
              damage: opportunity.damage ?? opportunity.total_damage ?? 0,
              damage_roll: opportunity.damage_roll || null,
              opportunity: true,
              attacker: opportunity.attacker,
              target: opportunity.target,
              movement_stop: opportunity.movement_stop || opportunity.movementStop || null,
            },
          })
        })
        appendReadyActionResultLogs(addLog, event.ready_action_results || [])
        if (event.hazard_result?.triggered) {
          addLog?.({
            role: 'system',
            content: formatHazardLog(event.hazard_result),
            log_type: 'combat',
            dice_result: buildHazardDiceResult(event.hazard_result),
          })
        }
        if (event.combat_over) {
          const outcome = event.outcome || 'ended'
          setCombatOver?.(outcome)
          setReactionPrompt?.(null)
          setLairActionPrompt?.(null)
          setLegendaryActionPrompt?.(null)
          setTurnState?.(null)
          setCombat?.(null)
          onCombatEnded?.(outcome)
          break
        }
        onLoadCombat()
        break
      case 'dm_responded':
        onLoadCombat()
        break
      case 'room_state_updated':
        setRoom(prev => mergeRealtimeRoomEvent(prev, event))
        break
      case 'member_offline':
      case 'member_online':
        if (Array.isArray(event.members)) {
          setRoom(prev => mergeRealtimeRoomEvent(prev, event))
          break
        }
        break
      default:
        break
    }
  }, [
    sessionId,
    setRoom,
    setCombat,
    setCombatOver,
    setReactionPrompt,
    setLairActionPrompt,
    setLegendaryActionPrompt,
    setTurnState,
    addLog,
    onLoadCombat,
    onCombatEnded,
    actorId,
  ])

  const onSkillClick = createCombatSkillClickHandler({
    getIsProcessing: () => isProcessing,
    getIsPlayerTurn: () => canActThisTurn,
    getUnavailableReason: (skill) => {
      const movementSkill = skill?.kind === 'move' || ['dash', 'cunning_action_dash', 'ki_step_of_the_wind_dash'].includes(skill?.k)
      if (movementSkill) {
        const speedLockReason = buildConditionSpeedLockReason(
          actor?.conditions || [],
          actor?.condition_durations || {},
        )
        if (speedLockReason) return speedLockReason
      }
      return getSkillUnavailableReason({
        skill,
        turnState: combat?.turn_states?.[actorId],
        isPlayerTurn: canActThisTurn,
        syncBlocked: false,
        isProcessing,
        selectedTarget,
      })
    },
    getSelectedTarget: () => selectedTarget,
    setError,
    handleAttack,
    setSpellModalOpen,
    setSpellQuickPick,
    gameApi,
    sessionId,
    setCombat,
    setTurnState,
    setClassResources,
    addLog,
    setHelpMode,
    handleDash,
    handleDisengage,
    handleDodge,
    handleHealingPotion,
    handleClassFeature,
    getTurnToken: () => getCombatTurnToken(combat),
    getCuttingWordsAbilityCheckOption: () => getCuttingWordsAbilityCheckOption({
      ...(actor || {}),
      turn_state: combat?.turn_states?.[actorId],
    }),
    confirmCuttingWordsAbilityCheck: ({ die }) => (
      globalThis.confirm?.(`Use Cutting Words ${die} on the target's contested check?`) ?? false
    ),
    rollCuttingWordsDie: (faces) => rollDice3D(faces, 1),
    showDice,
    getActorId: () => actorId,
    beginReadyMove: ({ actorId: readyActorId, targetId, trigger, triggerMatch, conditionText }) => {
      setReadyMoveDraft({
        actorId: readyActorId || actorId,
        targetId,
        trigger: trigger || 'target_moves',
        triggerMatch: triggerMatch || null,
        conditionText: conditionText || null,
      })
      setHelpMode?.(false)
      clearAoePreview?.()
      setMoveMode(true)
    },
  })

  const handleMoveTo = useCallback(async (x, y) => {
    if (!moveMode || !canActThisTurn || isProcessing) return
    try {
      const entityId = actorId
      if (!entityId) return
      const movementBlockedReason = buildConditionSpeedLockReason(
        actor?.conditions || [],
        actor?.condition_durations || {},
      )
      if (movementBlockedReason) {
        setError(movementBlockedReason)
        setMoveMode(false)
        return
      }
      const standUpNotice = buildConditionStandUpMoveNotice({
        conditions: actor?.conditions || [],
        durations: actor?.condition_durations || {},
        turnState: combat?.turn_states?.[entityId],
      })
      if (standUpNotice?.blocksMovement) {
        setError(standUpNotice.reason)
        setMoveMode(false)
        return
      }
      const frightenedMoveBlockedReason = buildConditionFrightenedMoveBlockedReason({
        conditions: actor?.conditions || [],
        durations: actor?.condition_durations || {},
        from: playerPos || combat?.entity_positions?.[entityId],
        to: { x, y },
        entityPositions: entityPositions || combat?.entity_positions || {},
      })
      if (frightenedMoveBlockedReason) {
        setError(frightenedMoveBlockedReason)
        setMoveMode(false)
        return
      }
      const grappleDragPreview = buildGrappleDragMovePreview({
        actorId: entityId,
        actorPosition: playerPos || combat?.entity_positions?.[entityId],
        destination: { x, y },
        entities: entities || combat?.entities || {},
        entityPositions: entityPositions || combat?.entity_positions || {},
        turnState: combat?.turn_states?.[entityId],
        reservedMovementCost: standUpNotice?.cost || 0,
      })
      if (grappleDragPreview?.blockedReason) {
        setError(grappleDragPreview.blockedReason)
        setMoveMode(false)
        return
      }
      const difficultTerrainPreview = buildDifficultTerrainMovePreview({
        actorPosition: playerPos || combat?.entity_positions?.[entityId],
        destination: { x, y },
        gridData: combat?.grid_data || {},
        turnState: combat?.turn_states?.[entityId],
        reservedMovementCost: standUpNotice?.cost || 0,
        baseMovementCost: grappleDragPreview?.movementCost ?? null,
      })
      if (difficultTerrainPreview?.blockedReason) {
        setError(difficultTerrainPreview.blockedReason)
        setMoveMode(false)
        return
      }
      const result = readyMoveDraft
        ? await gameApi.readyAction(sessionId, readyMoveDraft.actorId || entityId, readyMoveDraft.targetId, {
          actionType: 'move',
          trigger: readyMoveDraft.trigger || 'target_moves',
          ...(readyMoveDraft.triggerMatch || readyMoveDraft.trigger_match
            ? { triggerMatch: readyMoveDraft.triggerMatch || readyMoveDraft.trigger_match }
            : {}),
          moveToX: x,
          moveToY: y,
          ...(readyMoveDraft.conditionText || readyMoveDraft.condition_text
            ? { conditionText: readyMoveDraft.conditionText || readyMoveDraft.condition_text }
            : {}),
          expectedTurnToken: getCombatTurnToken(combat),
        })
        : await gameApi.move(sessionId, entityId, x, y, getCombatTurnToken(combat))
      if (result) {
        if (result.combat) {
          setCombat(result.combat)
        } else {
          setCombat(prev => prev ? { ...prev, entity_positions: result.entity_positions || prev.entity_positions } : prev)
        }
        if (result.turn_state) setTurnState(result.turn_state)
        if (readyMoveDraft && result.narration) {
          addLog?.({
            role: 'player',
            content: result.narration,
            log_type: 'combat',
            state_changes: buildCombatStateChangeSummary(result, { targetName: result.ready_action?.target_name || readyMoveDraft.targetId }),
            dice_result: result.ready_action ? { type: 'ready_action_declared', ready_action: result.ready_action } : undefined,
          })
        }
        ;(result.opportunity_attacks || []).forEach(opportunity => {
          const attack = opportunity.attack_result || opportunity.attack_roll || opportunity.attack || {}
          addLog?.({
            role: 'system',
            content: formatOpportunityAttackMoveLog(opportunity),
            log_type: 'combat',
            dice_result: {
              attack,
              damage: opportunity.damage ?? opportunity.total_damage ?? 0,
              damage_roll: opportunity.damage_roll || null,
              opportunity: true,
              attacker: opportunity.attacker,
              target: opportunity.target,
              movement_stop: opportunity.movement_stop || opportunity.movementStop || null,
            },
          })
        })
        ;(result.ready_action_results || []).forEach(readyAction => {
          addLog?.({
            role: 'system',
            content: readyAction.narration || formatReadyActionMoveLog(readyAction),
            log_type: 'combat',
            dice_result: {
              type: 'ready_action',
              applied: readyAction.applied !== false,
              trigger: readyAction.trigger || 'target_moves',
              actor_id: readyAction.actor_id,
              actor_name: readyAction.actor_name,
              target_id: readyAction.target_id,
              target_name: readyAction.target_name,
              condition_text: readyAction.condition_text || readyAction.conditionText || null,
              action_type: readyAction.action_type || readyAction.actionType || 'attack',
              from: readyAction.from || null,
              to: readyAction.to || null,
              steps: readyAction.steps ?? null,
              distance_ft: readyAction.distance_ft ?? readyAction.distanceFt ?? null,
              damage: readyAction.damage ?? readyAction.total_damage ?? 0,
              heal: readyAction.heal ?? 0,
              attack: readyAction.attack_result || readyAction.attack_roll || readyAction.attack || {},
              spell_name: readyAction.spell_name || readyAction.spellName || null,
              dice: readyAction.dice_detail || readyAction.dice || null,
              target_state: readyAction.target_state || null,
              actor_state: readyAction.actor_state || null,
              hazard_result: readyAction.hazard_result || null,
              opportunity_attacks: readyAction.opportunity_attacks || readyAction.opportunityAttacks || [],
            },
          })
          ;(readyAction.opportunity_attacks || readyAction.opportunityAttacks || []).forEach(opportunity => {
            const opportunityAttack = opportunity.attack_result || opportunity.attack_roll || opportunity.attack || {}
            addLog?.({
              role: 'system',
              content: formatOpportunityAttackMoveLog(opportunity),
              log_type: 'combat',
              dice_result: {
                attack: opportunityAttack,
                damage: opportunity.damage ?? opportunity.total_damage ?? 0,
                damage_roll: opportunity.damage_roll || null,
                opportunity: true,
                ready_action: true,
                attacker: opportunity.attacker,
                target: opportunity.target,
                movement_stop: opportunity.movement_stop || opportunity.movementStop || null,
              },
            })
          })
          if (readyAction.hazard_result?.triggered) {
            addLog?.({
              role: 'system',
              content: formatHazardLog(readyAction.hazard_result),
              log_type: 'combat',
              dice_result: buildHazardDiceResult(readyAction.hazard_result),
            })
          }
        })
        if (result.hazard_result?.triggered) {
          addLog?.({
            role: 'system',
            content: formatHazardLog(result.hazard_result),
            log_type: 'combat',
            dice_result: buildHazardDiceResult(result.hazard_result),
          })
        }
        if (result.grapple_drag?.applied) {
          addLog?.({
            role: 'system',
            content: '擒抱拖拽',
            log_type: 'combat',
            state_changes: buildCombatStateChangeSummary(result),
            dice_result: {
              grapple_drag: result.grapple_drag,
            },
          })
        }
      }
      if (readyMoveDraft) setReadyMoveDraft(null)
      setMoveMode(false)
    } catch (e) {
      setError(formatCombatError(e))
    }
  }, [actor, actorId, addLog, canActThisTurn, combat, entityPositions, isProcessing, moveMode, playerPos, readyMoveDraft, sessionId, setCombat, setError, setMoveMode, setTurnState])

  const handleHelpTarget = useCallback(async (entityId) => {
    if (!helpMode || !canActThisTurn || isProcessing) return false
    const target = entityId ? entities?.[entityId] : null
    if (!entityId || entityId === playerId || entityId === myCharacterId || target?.is_enemy) {
      setError('请选择一名队友作为协助目标')
      return false
    }
    try {
      const result = await gameApi.combatAction(sessionId, '协助', entityId, false, false, getCombatTurnToken(combat))
      if (result?.turn_state) setTurnState(result.turn_state)
      const fresh = await gameApi.getCombat(sessionId)
      if (fresh) setCombat(fresh)
      setHelpMode(false)
      return true
    } catch (e) {
      setError(formatCombatError(e))
      return false
    }
  }, [
    canActThisTurn,
    combat,
    entities,
    helpMode,
    isProcessing,
    myCharacterId,
    playerId,
    sessionId,
    setCombat,
    setError,
    setHelpMode,
    setTurnState,
  ])

  const handleInspectTarget = useCallback(async (skill = 'investigation') => {
    if (!selectedTarget || !playerId) return false
    const target = entities?.[selectedTarget]
    if (!target?.is_enemy) {
      setError('Select an enemy to inspect.')
      return false
    }
    if (!canActThisTurn || isProcessing) {
      setError('Inspect requires your available action.')
      return false
    }
    try {
      setIsProcessing?.(true)
      const result = await gameApi.inspectEnemy(sessionId, {
        character_id: playerId,
        target_id: selectedTarget,
        skill,
        expected_turn_token: getCombatTurnToken(combat),
      })
      if (result?.combat) setCombat(result.combat)
      if (result?.turn_state) setTurnState(result.turn_state)
      const total = result?.check?.total
      const dc = result?.dc
      const outcome = result?.success ? 'success' : 'failed'
      addLog?.('system', `Inspect ${target.name}: ${total} vs DC ${dc} (${outcome})`, 'dice')
      return true
    } catch (e) {
      setError(formatCombatError(e))
      return false
    } finally {
      setIsProcessing?.(false)
    }
  }, [
    addLog,
    canActThisTurn,
    combat,
    entities,
    isProcessing,
    playerId,
    selectedTarget,
    sessionId,
    setCombat,
    setError,
    setIsProcessing,
    setTurnState,
  ])

  const handleSpellHover = useCallback((spell) => {
    if (spell && spell.aoe) {
      const preview = buildSpellAoePreview(spell)
      setAoePreview(preview)
      const centerKey = getAoePreviewCenterKey({
        selectedTarget: preview?.template === 'aura' ? null : selectedTarget,
        entityPositions,
        playerPos,
      })
      setAoeHover(centerKey)
      setAoeLockedCenter(null)
    } else {
      clearAoePreview()
    }
  }, [clearAoePreview, entityPositions, playerPos, selectedTarget, setAoeHover, setAoeLockedCenter, setAoePreview])

  return {
    onWsEvent,
    onSkillClick,
    handleMoveTo,
    handleHelpTarget,
    handleInspectTarget,
    handleSpellHover,
  }
}
