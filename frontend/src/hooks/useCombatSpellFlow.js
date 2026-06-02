import { useCallback } from 'react'
import { gameApi } from '../api/client'
import { rollDice3D } from '../components/DiceRollerOverlay'
import {
  applyActionResultEntityStates,
  collectSpellCastTargetIds,
  getCombatTurnToken,
  getSpellCastDisabledReason,
  parseDiceNotation,
  spellRequiresAttackRoll,
} from '../utils/combat'
import { formatCombatError } from '../utils/combatErrors'
import { buildCombatResultImpactSummary, buildCombatStateChangeSummary } from '../utils/combatLog'

export function useCombatSpellFlow({
  sessionId,
  playerId,
  selectedTarget,
  aoeHover = null,
  isProcessing,
  canActThisTurn = true,
  processingRef,
  setIsProcessing,
  setSpellModalOpen,
  setError,
  setTurnState,
  setCombat,
  setPlayerSpellSlots,
  addLog,
  setSelectedTarget,
  setCombatOver,
  showDice,
  combat,
}) {
  return useCallback(async (spell, level) => {
    if (!playerId || !canActThisTurn || isProcessing) return
    const blockedReason = getSpellCastDisabledReason({
      spell,
      level,
      selectedTarget,
      playerId,
      combat,
      aoeHover,
    })
    if (blockedReason) {
      setError(blockedReason)
      return
    }
    const targetIds = collectSpellCastTargetIds({
      spell,
      selectedTarget,
      playerId,
      combat,
      aoeHover,
      level,
    })

    processingRef.current = true
    setIsProcessing(true)
    setSpellModalOpen(false)
    setError('')

    try {
      const needsSpellAttackRoll = spellRequiresAttackRoll(spell) && targetIds.length === 1
      let spellAttackD20 = null
      if (needsSpellAttackRoll) {
        const attackRoll = await rollDice3D(20)
        spellAttackD20 = attackRoll.total
        showDice({ faces: 20, result: spellAttackD20, label: 'Spell attack' })
      }

      const rollResult = await gameApi.spellRoll(
        sessionId, playerId, spell.name, level,
        targetIds[0] || null, targetIds, getCombatTurnToken(combat), spellAttackD20,
      )

      if (rollResult.turn_state) setTurnState(rollResult.turn_state)

      const targetDesc = (rollResult.targets || []).map(t => t.name).join('、') || ''
      if (rollResult.spell_attack_required && rollResult.hit === false) {
        const attack = rollResult.attack_roll || {}
        addLog({
          role: 'player',
          content: `${spell.name}${targetDesc ? ` -> ${targetDesc}` : ''} spell attack missed (${attack.attack_total ?? '-'} vs AC${attack.target_ac ?? '-'})`,
          log_type: 'combat',
          dice_result: { attack: { ...attack, hit: false } },
          rule_result: 'spell attack missed',
        })
        const confirmResult = await gameApi.spellConfirm(sessionId, rollResult.pending_spell_id, null)
        if (confirmResult.turn_state) setTurnState(confirmResult.turn_state)
        setPlayerSpellSlots(confirmResult.remaining_slots || {})
        setSelectedTarget(null)
        processingRef.current = false
        setIsProcessing(false)
        return
      }
      const diceInfo = rollResult.damage_dice || rollResult.heal_dice || ''
      if (diceInfo) {
        addLog({
          role: 'system',
          content: `${spell.name}${targetDesc ? ` → ${targetDesc}` : ''} — 掷骰 ${diceInfo}`,
          log_type: 'system',
        })
      }

      setTimeout(async () => {
        try {
          const diceStr = rollResult.damage_dice || rollResult.heal_dice || ''
          const { count: diceCount, faces: diceFaces } = parseDiceNotation(diceStr, { defaultFaces: 6 })
          let spellRolls = null
          if (diceStr) {
            const { total: spellTotal, rolls: spellDiceRolls } = await rollDice3D(diceFaces, diceCount)
            spellRolls = spellDiceRolls
            showDice({ faces: diceFaces, result: spellTotal, label: spell.name, count: diceCount })
          }

          const confirmResult = await gameApi.spellConfirm(sessionId, rollResult.pending_spell_id, spellRolls)

          setCombat(prev => applyActionResultEntityStates(prev, confirmResult))

          if (confirmResult.turn_state) setTurnState(confirmResult.turn_state)
          setPlayerSpellSlots(confirmResult.remaining_slots || {})
          const impactSummary = buildCombatResultImpactSummary(confirmResult)
          addLog({
            role: 'player',
            content: confirmResult.narration,
            log_type: 'combat',
            dice_result: confirmResult.dice_result || confirmResult.log_dice_result || null,
            ...(impactSummary.length > 0 ? { impact_summary: impactSummary } : {}),
            state_changes: buildCombatStateChangeSummary(confirmResult, {
              targetName: targetDesc,
            }),
          })
          setSelectedTarget(null)

          if (confirmResult.wild_magic_check) {
            const wmc = confirmResult.wild_magic_check
            if (wmc.forced) {
              addLog({
                role: 'system',
                content: `🌀 混沌反噬！${confirmResult.wild_magic_surge?.effect || '野蛮魔法涌动！'}`,
                log_type: 'system',
              })
              if (wmc.surge_roll) {
                const { total: surgeD20 } = await rollDice3D(20)
                showDice({ faces: 20, result: surgeD20, label: `涌动效果 #${wmc.surge_roll}` })
              }
            } else {
              const { total: surgeCheck } = await rollDice3D(20)
              const triggered = surgeCheck === 1
              showDice({ faces: 20, result: surgeCheck, label: triggered ? '🌀 野蛮魔法涌动！' : '野蛮魔法检测' })

              if (triggered && confirmResult.wild_magic_surge) {
                addLog({
                  role: 'system',
                  content: `🌀 野蛮魔法涌动！d20=${surgeCheck} — ${confirmResult.wild_magic_surge.effect}`,
                  log_type: 'system',
                })
              } else {
                addLog({
                  role: 'system',
                  content: `🎲 野蛮魔法检测: d20=${surgeCheck}（安全，未触发涌动）`,
                  log_type: 'system',
                })
              }
            }
          }

          if (confirmResult.combat_over) { setCombatOver(confirmResult.outcome) }
        } catch (e2) {
          setError(formatCombatError(e2))
        } finally {
          processingRef.current = false
          setIsProcessing(false)
        }
      }, 1200)
    } catch (e) {
      setError(formatCombatError(e))
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    canActThisTurn,
    combat,
    isProcessing,
    playerId,
    processingRef,
    selectedTarget,
    aoeHover,
    sessionId,
    setCombat,
    setCombatOver,
    setError,
    setIsProcessing,
    setPlayerSpellSlots,
    setSelectedTarget,
    setSpellModalOpen,
    setTurnState,
    showDice,
  ])
}
