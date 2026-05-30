/**
 * useCombatPageActions — Combat 页面级动作胶水。
 *
 * 把 WS 事件分发、技能点击路由、移动操作、AoE hover 这类“页面知道很多、
 * 但单个子组件不该知道”的动作收拢在一起，Combat.jsx 只保留布局和状态拼装。
 */
import { useCallback } from 'react'
import { gameApi, roomsApi } from '../api/client'
import { buildSpellAoePreview, getAoePreviewCenterKey, getCombatTurnToken, getSkillUnavailableReason } from '../utils/combat'
import { createCombatSkillClickHandler } from '../utils/combatSkillActions'
import { formatCombatError } from '../utils/combatErrors'
import { mergeRealtimeRoomEvent } from './useRoomRealtime'

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
  setReactionPrompt,
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
  combat,
}) {
  const onWsEvent = useCallback((event) => {
    switch (event.type) {
      case 'combat_update':
        {
          const hasReactionPrompt = !!(event.player_can_react && event.reaction_prompt)
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
            const entry = event.combat.turn_order?.[event.combat.current_turn_index]
            if (entry?.character_id && event.combat.turn_states) {
              setTurnState(event.combat.turn_states[entry.character_id] || null)
            }
          }
          if (hasReactionPrompt) {
            setReactionPrompt?.(event.reaction_prompt)
          } else {
            setReactionPrompt?.(null)
          }
          if (event.combat_over) {
            setCombatOver?.(event.outcome)
          }
          if (!hasReactionPrompt) onLoadCombat()
          break
        }
      case 'turn_changed':
      case 'entity_moved':
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
        roomsApi.get(sessionId).then(r => r?.is_multiplayer && setRoom(r)).catch(() => undefined)
        break
      default:
        break
    }
  }, [sessionId, setRoom, setCombat, setCombatOver, setReactionPrompt, setTurnState, onLoadCombat, onCombatEnded])

  const onSkillClick = createCombatSkillClickHandler({
    getIsProcessing: () => isProcessing,
    getIsPlayerTurn: () => canActThisTurn,
    getUnavailableReason: (skill) => getSkillUnavailableReason({
      skill,
      turnState: combat?.turn_states?.[playerId || myCharacterId],
      isPlayerTurn: canActThisTurn,
      syncBlocked: false,
      isProcessing,
      selectedTarget,
    }),
    getSelectedTarget: () => selectedTarget,
    setError,
    handleAttack,
    setSpellModalOpen,
    setSpellQuickPick,
    gameApi,
    sessionId,
    setCombat,
    setTurnState,
    addLog,
    setHelpMode,
    handleDash,
    handleDisengage,
    handleDodge,
    handleHealingPotion,
    handleClassFeature,
    getTurnToken: () => getCombatTurnToken(combat),
  })

  const handleMoveTo = useCallback(async (x, y) => {
    if (!moveMode || !canActThisTurn || isProcessing) return
    try {
      const entityId = playerId || myCharacterId
      if (!entityId) return
      const result = await gameApi.move(sessionId, entityId, x, y, getCombatTurnToken(combat))
      if (result) {
        setCombat(prev => prev ? { ...prev, entity_positions: result.entity_positions || prev.entity_positions } : prev)
        if (result.turn_state) setTurnState(result.turn_state)
      }
      setMoveMode(false)
    } catch (e) {
      setError(formatCombatError(e))
    }
  }, [canActThisTurn, combat, isProcessing, myCharacterId, moveMode, playerId, sessionId, setCombat, setError, setMoveMode, setTurnState])

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
