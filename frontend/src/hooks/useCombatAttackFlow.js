import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { JuiceAudio, shake as JuiceShake } from '../juice'
import {
  applyActionResultEntityStates,
  applyWeaponResourceToCombat,
  formatWeaponResourceLog,
  getCombatTurnToken,
  parseDiceNotation,
} from '../utils/combat'
import { formatCombatError } from '../utils/combatErrors'
import { buildCombatStateChangeSummary } from '../utils/combatLog'
import { rollDice3D } from '../components/DiceRollerOverlay'

function ignoreOptionalEffect(fn) {
  try {
    fn()
  } catch {
    // Optional audio / haptics may fail in tests or unsupported browsers.
  }
}

function buildAttackLogDice(atkResult, hit) {
  return {
    d20: atkResult.d20,
    attack_bonus: atkResult.attack_bonus,
    attack_total: atkResult.attack_total,
    target_ac: atkResult.target_ac,
    hit,
    is_crit: hit ? atkResult.is_crit : false,
    is_fumble: hit ? false : atkResult.is_fumble,
    ...(atkResult.defender_interception
      ? {
          defender_interception: atkResult.defender_interception,
          disadvantage: true,
        }
      : {}),
  }
}

export function useCombatAttackFlow({
  sessionId,
  playerId,
  selectedTarget,
  isRanged,
  selectedWeaponName,
  combat,
  isProcessing,
  canActThisTurn = true,
  isPlayerTurn,
  processingRef,
  setIsProcessing,
  setError,
  showDice,
  addLog,
  setTurnState,
  setCombat,
  setSelectedTarget,
  setSmitePrompt,
  setCombatOver,
}) {
  return useCallback(async () => {
    if (!selectedTarget || !canActThisTurn || !isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const { total: d20 } = await rollDice3D(20)
      showDice({ faces: 20, result: d20, label: '攻击检定' })

      const atkResult = await gameApi.attackRoll(
        sessionId, playerId, selectedTarget,
        isRanged ? 'ranged' : 'melee', false, d20, getCombatTurnToken(combat), selectedWeaponName || null,
      )

      if (atkResult.turn_state) setTurnState(atkResult.turn_state)
      if (atkResult.weapon_resource) {
        const resourceText = formatWeaponResourceLog(atkResult.weapon_resource)
        if (resourceText) addLog({ role: 'system', content: resourceText, log_type: 'system' })
        setCombat(prev => applyWeaponResourceToCombat(prev, playerId, atkResult.weapon_resource))
      }

      const attacksRemaining = atkResult.attacks_max - atkResult.attacks_made
      if (attacksRemaining > 0) {
        addLog({
          role: 'system',
          content: `\u2694\uFE0F 额外攻击：还可攻击 ${attacksRemaining} 次`,
          log_type: 'system',
        })
      }

      if (!atkResult.hit) {
        ignoreOptionalEffect(() => JuiceAudio.miss())
        if (atkResult.is_fumble) {
          ignoreOptionalEffect(() => JuiceShake(document.querySelector('.combat-stage') || document.body, 6, 320))
        }
        const missText = atkResult.narration || (atkResult.is_fumble
          ? `\uD83D\uDC80 大失手！${atkResult.attacker_name} 对 ${atkResult.target_name} 攻击失手。（${atkResult.attack_total} vs AC${atkResult.target_ac}）`
          : `${atkResult.attacker_name} 攻击 ${atkResult.target_name}，未命中。（${atkResult.attack_total} vs AC${atkResult.target_ac}）`)
        addLog({ role: 'player', content: missText, log_type: 'combat',
          dice_result: { attack: buildAttackLogDice(atkResult, false) },
          rule_result: atkResult.is_fumble ? '大失手' : '攻击未命中',
          state_changes: buildCombatStateChangeSummary(atkResult, { includeDefenderInterception: false }),
        })
        setSelectedTarget(null)
        processingRef.current = false
        setIsProcessing(false)
        return
      }

      if (atkResult.is_crit) {
        ignoreOptionalEffect(() => JuiceAudio.crit())
        ignoreOptionalEffect(() => JuiceShake(document.querySelector('.combat-stage') || document.body, 10, 420))
      } else {
        ignoreOptionalEffect(() => JuiceAudio.hit())
      }
      const hitLabel = atkResult.is_crit ? '\uD83D\uDCA5 暴击！' : '命中！'
      addLog({ role: 'system', content: `${hitLabel} ${atkResult.attacker_name} 对 ${atkResult.target_name}（${atkResult.attack_total} vs AC${atkResult.target_ac}）`, log_type: 'combat',
        dice_result: { attack: buildAttackLogDice(atkResult, true) },
        rule_result: atkResult.is_crit ? '暴击命中' : '攻击命中',
        state_changes: buildCombatStateChangeSummary(atkResult, { includeDefenderInterception: false }),
      })

      setTimeout(async () => {
        try {
          const { count: dmgCount, faces: damageFaces } = parseDiceNotation(atkResult.damage_dice || '1d8')
          const { total: dmgTotal, rolls: dmgRolls } = await rollDice3D(damageFaces, dmgCount)
          showDice({ faces: damageFaces, result: dmgTotal, label: '伤害骰', count: dmgCount })

          const dmgResult = await gameApi.damageRoll(sessionId, atkResult.pending_attack_id, dmgRolls)

          setCombat(prev => {
            if (!prev) return prev
            return applyActionResultEntityStates(prev, dmgResult)
          })

          if (dmgResult.turn_state) setTurnState(dmgResult.turn_state)

          addLog({ role: 'player', content: dmgResult.narration, log_type: 'combat',
            dice_result: { damage: dmgResult.damage_total, total_damage: dmgResult.total_damage },
            rule_result: dmgResult.total_damage !== undefined
              ? `实际伤害 ${dmgResult.total_damage}`
              : undefined,
            state_changes: buildCombatStateChangeSummary(dmgResult, {
              targetName: atkResult.target_name,
            }),
          })

          if (dmgResult.sneak_attack_damage > 0) {
            addLog({ role: 'system', content: `\uD83D\uDDE1\uFE0F 偷袭！额外造成 ${dmgResult.sneak_attack_damage} 点伤害`, log_type: 'system' })
          }

          if (dmgResult.can_smite) {
            setSmitePrompt({
              show: true,
              targetId: dmgResult.target_id,
              isCrit: Boolean(dmgResult.is_crit),
            })
          }

          if (dmgResult.combat_over) { setCombatOver(dmgResult.outcome) }
        } catch (e2) {
          setError(formatCombatError(e2))
        } finally {
          setSelectedTarget(null)
          processingRef.current = false
          setIsProcessing(false)
        }
      }, 1800)
    } catch (e) {
      setError(formatCombatError(e))
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    combat,
    canActThisTurn,
    isPlayerTurn,
    isProcessing,
    isRanged,
    playerId,
    processingRef,
    selectedTarget,
    selectedWeaponName,
    sessionId,
    setCombat,
    setCombatOver,
    setError,
    setIsProcessing,
    setSelectedTarget,
    setSmitePrompt,
    setTurnState,
    showDice,
  ])
}
