import { useCallback } from 'react'
import { charactersApi, gameApi } from '../api/client'
import { rollDice3D } from '../components/DiceRollerOverlay'
import { applyActionResultEntityStates, applyPlayerHpUpdate } from '../utils/combat'
import {
  getInventoryUseSuccessText,
  mergeConsumableUseResult,
  normalizeInventoryItem,
} from '../utils/inventory'

const FEATURE_DICE = {
  second_wind: { faces: 10, count: 1, label: '活力恢复' },
  ki_flurry: { faces: 20, count: 1, label: '疾风连击' },
  portent: { faces: 20, count: 1, label: '预言骰' },
  bardic_inspiration: { faces: 6, count: 1, label: '灵感骰' },
  shadow_step: { faces: 20, count: 1, label: '暗影步' },
}

export function useCombatPlayerActions({
  sessionId,
  playerId,
  combat,
  isProcessing,
  canActThisTurn = true,
  isPlayerTurn,
  processingRef,
  setIsProcessing,
  setError,
  setTurnState,
  setClassResources,
  setCombat,
  session,
  setSession,
  showDice,
  addLog,
}) {
  const runSimpleAction = useCallback(async (actionText, fallbackNarration) => {
    if (!canActThisTurn || !isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    try {
      const result = await gameApi.combatAction(sessionId, actionText, null, false)
      if (result.turn_state) setTurnState(result.turn_state)
      addLog({ role: 'player', content: result.narration || fallbackNarration, log_type: 'combat' })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    combat,
    canActThisTurn,
    isPlayerTurn,
    isProcessing,
    processingRef,
    sessionId,
    setError,
    setIsProcessing,
    setTurnState,
  ])

  const handleClassFeature = useCallback(async (featureName) => {
    if (!canActThisTurn || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const featureDice = FEATURE_DICE[featureName]
      if (featureDice) {
        const { total } = await rollDice3D(featureDice.faces, featureDice.count)
        showDice({ faces: featureDice.faces, result: total, label: featureDice.label, count: featureDice.count })
      }

      const result = await gameApi.classFeature(sessionId, featureName)
      addLog({ role: 'player', content: result.narration, log_type: 'combat' })
      if (result.turn_state) setTurnState(result.turn_state)
      if (result.class_resources) setClassResources(result.class_resources)
      setCombat(prev => {
        let updated = applyPlayerHpUpdate(prev, playerId, result.hp_current)
        const temporaryHp = result.temporary_hp ?? result.class_resources?.temporary_hp
        if (temporaryHp !== undefined) {
          updated = applyActionResultEntityStates(updated, {
            target_state: {
              target_id: playerId,
              hp_current: result.hp_current,
              temporary_hp: temporaryHp,
              class_resources: result.class_resources,
            },
          })
        }
        return updated
      })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    canActThisTurn,
    isProcessing,
    playerId,
    processingRef,
    sessionId,
    setClassResources,
    setCombat,
    setError,
    setIsProcessing,
    setTurnState,
    showDice,
  ])

  const handleHealingPotion = useCallback(async () => {
    if (!canActThisTurn || !isPlayerTurn(combat) || isProcessing) return
    const player = session?.player
    if (!player?.id) {
      setError('找不到当前角色，无法使用治疗药剂')
      return
    }
    const potion = (player.equipment?.gear || [])
      .map((item, index) => normalizeInventoryItem(item, 'gear', index))
      .find(item => item.name === 'Healing Potion' || item.name === 'Greater Healing Potion')
    if (!potion) {
      setError('背包中没有可用的治疗药剂')
      return
    }

    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const result = await charactersApi.useItem(player.id, potion.name, {
        session_id: sessionId,
        use_in_combat: true,
      })
      setSession?.(mergeConsumableUseResult(session, result))
      if (result.turn_state) setTurnState(result.turn_state)
      addLog({ role: 'player', content: getInventoryUseSuccessText(potion, result), log_type: 'combat' })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    canActThisTurn,
    combat,
    isPlayerTurn,
    isProcessing,
    processingRef,
    session,
    sessionId,
    setError,
    setIsProcessing,
    setSession,
    setTurnState,
  ])

  return {
    handleClassFeature,
    handleHealingPotion,
    handleDodge: () => runSimpleAction('闪避', '你采取了闪避姿态，专注于躲避攻击。'),
    handleDash: () => runSimpleAction('冲刺', '你使用冲刺，移动力翻倍！'),
    handleDisengage: () => runSimpleAction('脱离接战', '你脱离接战，本回合移动不触发借机攻击。'),
  }
}
