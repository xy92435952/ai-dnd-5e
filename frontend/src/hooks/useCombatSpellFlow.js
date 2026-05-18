import { useCallback } from 'react'
import { gameApi } from '../api/game'
import { rollDice3D } from '../components/DiceRollerOverlay'
import { applyAoeHpUpdates, applyHpUpdate, parseDiceNotation } from '../utils/combat'

function formatAoeMechanicalSummary(results = []) {
  const parts = results
    .map(result => {
      const name = result.name || result.target_name || result.target_id || '目标'
      const damage = result.damage ?? result.damage_total ?? result.total_damage
      if (damage == null) return null
      return `${name} ${damage}伤害`
    })
    .filter(Boolean)
  return parts.length ? `范围结算：${parts.join('；')}` : ''
}

export function useCombatSpellFlow({
  sessionId,
  playerId,
  selectedTarget,
  isProcessing,
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
}) {
  return useCallback(async (spell, level) => {
    if (!playerId || isProcessing) return
    const target = selectedTarget || null
    const effectiveTarget = spell.type === 'heal' ? (target || playerId) : target

    if (spell.type === 'damage' && !effectiveTarget) {
      setError('请先选择一个目标再施法')
      return
    }

    processingRef.current = true
    setIsProcessing(true)
    setSpellModalOpen(false)
    setError('')

    try {
      const targetIds = Array.isArray(effectiveTarget) ? effectiveTarget : (effectiveTarget ? [effectiveTarget] : [])
      const rollResult = await gameApi.spellRoll(
        sessionId, playerId, spell.name, level,
        targetIds[0] || null, targetIds,
      )

      if (rollResult.turn_state) setTurnState(rollResult.turn_state)

      const targetDesc = (rollResult.targets || []).map(t => t.name).join('、') || ''
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

          if (confirmResult.target_new_hp != null) {
            setCombat(prev => {
              if (!prev) return prev
              return applyHpUpdate(prev, confirmResult.target_id, confirmResult.target_new_hp)
            })
          }

          if (confirmResult.aoe_results?.length) {
            setCombat(prev => applyAoeHpUpdates(prev, confirmResult.aoe_results))
            const summary = formatAoeMechanicalSummary(confirmResult.aoe_results)
            if (summary) {
              addLog({ role: 'system', content: summary, log_type: 'combat_mechanics' })
            }
          }

          if (confirmResult.turn_state) setTurnState(confirmResult.turn_state)
          setPlayerSpellSlots(confirmResult.remaining_slots || {})
          addLog({ role: 'player', content: confirmResult.narration, log_type: 'combat' })
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
          setError(e2.message)
        } finally {
          processingRef.current = false
          setIsProcessing(false)
        }
      }, 1200)
    } catch (e) {
      setError(e.message)
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [
    addLog,
    isProcessing,
    playerId,
    processingRef,
    selectedTarget,
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
