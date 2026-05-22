/**
 * useCombatPageActions — Combat 页面级动作胶水。
 *
 * 把 WS 事件分发、技能点击路由、移动操作、AoE hover 这类“页面知道很多、
 * 但单个子组件不该知道”的动作收拢在一起，Combat.jsx 只保留布局和状态拼装。
 */
import { useCallback } from 'react'
import { gameApi } from '../api/game'
import { roomsApi } from '../api/rooms'
import { getAoePreviewCenterKey, aoeRadiusCells } from '../utils/combat'
import { createCombatSkillClickHandler } from '../utils/combatSkillActions'
import { mergeRealtimeRoomEvent } from './useRoomRealtime'

export function useCombatPageActions({
  sessionId,
  setRoom,
  myCharacterId,
  playerId,
  moveMode,
  isProcessing,
  isPlayerTurn,
  selectedTarget,
  entityPositions,
  playerPos,
  setError,
  setCombat,
  setTurnState,
  setSpellModalOpen,
  setHelpMode,
  handleAttack,
  handleDash,
  handleDisengage,
  handleDodge,
  handleClassFeature,
  setMoveMode,
  setAoePreview,
  setAoeHover,
  clearAoePreview,
  onLoadCombat,
}) {
  const onWsEvent = useCallback((event) => {
    switch (event.type) {
      case 'combat_update':
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
  }, [sessionId, setRoom, onLoadCombat])

  const onSkillClick = createCombatSkillClickHandler({
    getIsProcessing: () => isProcessing,
    getIsPlayerTurn: () => isPlayerTurn,
    getSelectedTarget: () => selectedTarget,
    setError,
    handleAttack,
    setSpellModalOpen,
    gameApi,
    sessionId,
    setCombat,
    setHelpMode,
    handleDash,
    handleDisengage,
    handleDodge,
    handleClassFeature,
  })

  const handleMoveTo = useCallback(async (x, y) => {
    if (!moveMode || !isPlayerTurn || isProcessing) return
    try {
      const entityId = playerId || myCharacterId
      const result = await gameApi.move(sessionId, entityId, x, y)
      if (result) {
        setCombat(prev => prev ? { ...prev, entity_positions: result.entity_positions || prev.entity_positions } : prev)
        if (result.turn_state) setTurnState(result.turn_state)
      }
      setMoveMode(false)
    } catch (e) {
      setError(e.message)
    }
  }, [isPlayerTurn, isProcessing, myCharacterId, moveMode, playerId, sessionId, setCombat, setError, setMoveMode, setTurnState])

  const handleSpellHover = useCallback((spell) => {
    if (spell && spell.aoe) {
      const radius = aoeRadiusCells(spell)
      setAoePreview({ radius, spellName: spell.name })
      const centerKey = getAoePreviewCenterKey({
        selectedTarget,
        entityPositions,
        playerPos,
      })
      setAoeHover(centerKey)
    } else {
      clearAoePreview()
    }
  }, [clearAoePreview, entityPositions, playerPos, selectedTarget, setAoeHover, setAoePreview])

  return {
    onWsEvent,
    onSkillClick,
    handleMoveTo,
    handleSpellHover,
  }
}
