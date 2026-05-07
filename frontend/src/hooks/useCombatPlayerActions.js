import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { rollDice3D } from '../components/DiceRollerOverlay'
import { applyPlayerHpUpdate } from '../utils/combat'

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
  isPlayerTurn,
  processingRef,
  setIsProcessing,
  setError,
  setTurnState,
  setClassResources,
  setCombat,
  showDice,
  addLog,
}) {
  const runSimpleAction = useCallback(async (actionText, fallbackNarration) => {
    if (!isPlayerTurn(combat) || isProcessing) return
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
    isPlayerTurn,
    isProcessing,
    processingRef,
    sessionId,
    setError,
    setIsProcessing,
    setTurnState,
  ])

  const handleClassFeature = useCallback(async (featureName) => {
    if (isProcessing) return
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
      setCombat(prev => applyPlayerHpUpdate(prev, playerId, result.hp_current))
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
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

  return {
    handleClassFeature,
    handleDodge: () => runSimpleAction('闪避', '你采取了闪避姿态，专注于躲避攻击。'),
    handleDash: () => runSimpleAction('冲刺', '你使用冲刺，移动力翻倍！'),
    handleDisengage: () => runSimpleAction('脱离接战', '你脱离接战，本回合移动不触发借机攻击。'),
  }
}
