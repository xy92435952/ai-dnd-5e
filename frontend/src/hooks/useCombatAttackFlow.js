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
import { selectD20Roll } from '../utils/d20Roll'
import { getLuckyPointsRemaining } from '../utils/lucky'
import { getBardicInspiration } from '../utils/bardicInspiration'

function ignoreOptionalEffect(fn) {
  try {
    fn()
  } catch {
    // Optional audio / haptics may fail in tests or unsupported browsers.
  }
}

function buildAttackD20Plan(prediction = null) {
  const hasAdvantage = Boolean(prediction?.advantage)
  const hasDisadvantage = Boolean(prediction?.disadvantage)
  if (hasAdvantage && !hasDisadvantage) {
    return { count: 2, mode: 'advantage', label: '攻击检定（优势）' }
  }
  if (hasDisadvantage && !hasAdvantage) {
    return { count: 2, mode: 'disadvantage', label: '攻击检定（劣势）' }
  }
  return { count: 1, mode: 'normal', label: '攻击检定' }
}

async function refreshAttackPredictionForRoll({
  sessionId,
  playerId,
  selectedTarget,
  isRanged,
  prediction,
}) {
  if (typeof gameApi.predict !== 'function') return prediction

  try {
    return await gameApi.predict(sessionId, playerId, selectedTarget, 'atk', isRanged) || prediction
  } catch {
    return prediction
  }
}

function buildAttackLogDice(atkResult, hit) {
  const fallbackDisadvantageSources = atkResult.defender_interception
    ? ['defender interception']
    : []
  const disadvantageSources = atkResult.disadvantage_sources || fallbackDisadvantageSources
  const hasDisadvantage = Boolean(atkResult.disadvantage) || (
    Boolean(atkResult.defender_interception) && !atkResult.advantage
  )

  return {
    d20: atkResult.d20,
    d20_rolls: atkResult.d20_rolls || null,
    selected_d20: atkResult.selected_d20 || null,
    other_roll: atkResult.other_roll || null,
    d20_selection: atkResult.d20_selection || null,
    attack_bonus: atkResult.attack_bonus,
    attack_total: atkResult.attack_total,
    target_ac: atkResult.target_ac,
    cover_bonus: atkResult.cover_bonus || 0,
    hit,
    is_crit: hit ? atkResult.is_crit : false,
    is_fumble: hit ? false : atkResult.is_fumble,
    advantage: Boolean(atkResult.advantage),
    disadvantage: hasDisadvantage,
    advantage_sources: atkResult.advantage_sources || [],
    disadvantage_sources: disadvantageSources,
    roll_state: atkResult.roll_state,
    ...(atkResult.lucky ? { lucky: atkResult.lucky } : {}),
    ...(atkResult.bardic_inspiration ? { bardic_inspiration: atkResult.bardic_inspiration } : {}),
    ...(atkResult.defender_interception
      ? {
          defender_interception: atkResult.defender_interception,
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
  prediction = null,
  classResources = {},
  useLuckyAttack = false,
  setUseLuckyAttack = null,
  useBardicAttack = false,
  setUseBardicAttack = null,
  setClassResources = null,
}) {
  return useCallback(async () => {
    if (!selectedTarget || !canActThisTurn || !isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      const effectivePrediction = await refreshAttackPredictionForRoll({
        sessionId,
        playerId,
        selectedTarget,
        isRanged,
        prediction,
      })
      const d20Plan = buildAttackD20Plan(effectivePrediction)
      const d20Roll = await rollDice3D(20, d20Plan.count)
      const { d20, secondD20, selected } = selectD20Roll(d20Roll, d20Plan.mode)
      showDice({ faces: 20, result: selected ?? d20, label: d20Plan.label, count: d20Plan.count })
      const luckyEnabled = Boolean(useLuckyAttack) && getLuckyPointsRemaining(classResources) > 0
      let luckyD20 = null
      if (luckyEnabled) {
        const luckyRoll = await rollDice3D(20)
        luckyD20 = luckyRoll.total
        showDice({ faces: 20, result: luckyD20, label: 'Lucky reroll', count: 1 })
      } else if (useLuckyAttack && typeof setUseLuckyAttack === 'function') {
        setUseLuckyAttack(false)
      }
      const bardic = getBardicInspiration(classResources)
      const bardicEnabled = Boolean(useBardicAttack) && Boolean(bardic)
      let bardicRoll = null
      if (bardicEnabled) {
        const bardicDice = await rollDice3D(bardic.faces)
        bardicRoll = bardicDice.total
        showDice({ faces: bardic.faces, result: bardicRoll, label: `Bardic Inspiration ${bardic.die}`, count: 1 })
      } else if (useBardicAttack && typeof setUseBardicAttack === 'function') {
        setUseBardicAttack(false)
      }

      const attackArgs = [
        sessionId, playerId, selectedTarget,
        isRanged ? 'ranged' : 'melee', false, d20, getCombatTurnToken(combat), selectedWeaponName || null, secondD20,
      ]
      const attackOptions = {
        ...(luckyEnabled ? { useLucky: true, luckyD20Value: luckyD20 } : {}),
        ...(bardicEnabled ? { useBardicInspiration: true, bardicInspirationRoll: bardicRoll } : {}),
      }
      if (Object.keys(attackOptions).length) attackArgs.push(attackOptions)
      const atkResult = await gameApi.attackRoll(...attackArgs)
      if (atkResult.lucky?.spent) {
        if (typeof setClassResources === 'function') {
          setClassResources(prev => ({
            ...(prev || {}),
            lucky_points_remaining: atkResult.lucky.lucky_points_remaining,
          }))
        }
        if (typeof setUseLuckyAttack === 'function') setUseLuckyAttack(false)
      }
      if (atkResult.bardic_inspiration?.spent) {
        if (typeof setClassResources === 'function') {
          setClassResources(prev => ({
            ...(prev || {}),
            ...(atkResult.class_resources || {}),
            bardic_inspiration: {
              ...((prev || {}).bardic_inspiration || {}),
              ...((atkResult.class_resources || {}).bardic_inspiration || {}),
              uses_remaining: atkResult.bardic_inspiration.uses_remaining,
            },
          }))
        }
        if (typeof setUseBardicAttack === 'function') setUseBardicAttack(false)
      }

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
    classResources,
    combat,
    canActThisTurn,
    isPlayerTurn,
    isProcessing,
    isRanged,
    playerId,
    processingRef,
    prediction,
    selectedTarget,
    selectedWeaponName,
    sessionId,
    setCombat,
    setCombatOver,
    setError,
    setClassResources,
    setIsProcessing,
    setSelectedTarget,
    setSmitePrompt,
    setTurnState,
    setUseBardicAttack,
    setUseLuckyAttack,
    showDice,
    useBardicAttack,
    useLuckyAttack,
  ])
}
