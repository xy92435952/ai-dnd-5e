import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { rollDice3D } from '../components/DiceRollerOverlay'
import { applyActionResultEntityStates } from '../utils/combat'
import { formatCombatError } from '../utils/combatErrors'
import { buildCombatStateChangeSummary } from '../utils/combatLog'

export function useCombatDeathSave({
  sessionId,
  playerId,
  isProcessing,
  canActThisTurn = true,
  processingRef,
  setIsProcessing,
  setError,
  setCombat,
  setSession,
  showDice,
  addLog,
}) {
  return useCallback(async () => {
    if (!playerId || !canActThisTurn || isProcessing) return

    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const { total: d20 } = await rollDice3D(20)
      showDice({ faces: 20, result: d20, label: '死亡豁免' })

      const result = await gameApi.deathSave(sessionId, playerId, d20)
      setCombat(prev => applyActionResultEntityStates(prev, result))
      setSession?.(prev => {
        if (!prev?.player || prev.player.id !== playerId) return prev
        const targetState = result.target_state || {}
        const nextDeathSaves = Object.prototype.hasOwnProperty.call(targetState, 'death_saves')
          ? targetState.death_saves
          : Object.prototype.hasOwnProperty.call(result, 'death_saves')
            ? result.death_saves
            : prev.player.death_saves
        return {
          ...prev,
          player: {
            ...prev.player,
            hp_current: targetState.hp_current ?? result.hp_current ?? prev.player.hp_current,
            death_saves: nextDeathSaves,
            conditions: targetState.conditions ?? prev.player.conditions,
            life_state: targetState.life_state ?? result.life_state ?? prev.player.life_state,
          },
        }
      })

      const saves = result.death_saves || result.target_state?.death_saves || {}
      const label = result.outcome === 'revive'
        ? `${result.character_name || '角色'} 掷出自然 20，恢复 1 HP！`
        : result.outcome === 'stable'
          ? `${result.character_name || '角色'} 死亡豁免成功并稳定下来。`
          : result.outcome === 'dead'
            ? `${result.character_name || '角色'} 死亡豁免失败，生命消逝。`
            : `${result.character_name || '角色'} 死亡豁免 d20=${result.d20}（成功 ${saves.successes || 0}/3，失败 ${saves.failures || 0}/3）`
      addLog({
        role: 'system',
        content: label,
        log_type: 'dice',
        dice_result: { type: 'death_save', d20: result.d20, outcome: result.outcome },
        state_changes: buildCombatStateChangeSummary(result, {
          targetName: result.character_name || '角色',
        }),
      })
    } catch (e) {
      setError(formatCombatError(e))
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
    setCombat,
    setError,
    setIsProcessing,
    setSession,
    showDice,
  ])
}
