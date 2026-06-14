/**
 * useSkillCheck — 封装"技能检定"的状态机与副作用。
 *
 * 原位：Adventure.jsx 主组件里 pendingCheck / checkRolling 两个 state
 * 和 handleDiceRoll 一个 async handler。抽到这里后 Adventure 只用
 * 解构暴露的 API 触发 UI 和后续业务动作。
 *
 * 流程：
 *   1. DM 响应里带 needs_check -> Adventure 调 setPendingCheck(check)
 *   2. 玩家点"投掷 d20" -> rollPending()
 *   3. hook 内部：掷骰动画 → 服务端计算 → 写日志 → 播音效 → 清掉 pending
 *   4. rollPending 返回 autoMsg（或 null），Adventure 决定如何把它塞给 DM
 *
 * 为什么不把 handleAction 调用也放进来？
 *   - handleAction 与 DM 响应、剧场模式强耦合，还在 Adventure 主体里
 *   - 保持 hook 只管"检定本身"，让 Adventure 决定后续流程（解耦更自然）
 *
 * @param {{ sessionId: string, playerId?: string|null, addLog: (role:string, content:string, logType?:string, extra?:object) => void }} deps
 */
import { useState, useCallback } from 'react'
import { useGameStore } from '../store/gameStore'
import { gameApi } from '../api/client'
import { rollDice3D } from '../components/DiceRollerOverlay'
import { JuiceAudio, shake as JuiceShake } from '../juice'
import { getLuckyPointsRemaining } from '../utils/lucky'
import { getBardicInspiration } from '../utils/bardicInspiration'

function needsSecondD20(check) {
  return Boolean(check?.advantage || check?.disadvantage)
}

function getExhaustionLevel(character) {
  const level = Number(character?.condition_durations?.exhaustion_level || 0)
  return Number.isFinite(level) ? Math.max(0, Math.min(6, level)) : 0
}

function buildCheckRollState(check, player) {
  const exhaustionLevel = getExhaustionLevel(player)
  const exhaustionDisadvantage = exhaustionLevel >= 1
  const advantage = Boolean(check?.advantage)
  const disadvantage = Boolean(check?.disadvantage || exhaustionDisadvantage)
  return {
    advantage: advantage && !disadvantage,
    disadvantage: disadvantage && !advantage,
  }
}

function formatD20Roll(result) {
  const d20 = `d20=${result.d20}`
  if (result.other_roll == null) return d20
  return `${d20}/${result.other_roll}`
}

function formatLuckyDetail(result) {
  const lucky = result?.lucky
  if (!lucky?.spent) return ''
  return ` [Lucky ${lucky.d20_before}->${lucky.d20_after} · ${lucky.lucky_points_remaining}]`
}

function formatBardicDetail(result) {
  const bardic = result?.bardic_inspiration
  if (!bardic?.spent) return ''
  return ` [Bardic ${bardic.die || ''}+${bardic.roll} · ${bardic.uses_remaining}]`
}

export function useSkillCheck({
  sessionId,
  playerId,
  player = null,
  addLog,
  onLuckySpent = null,
  onBardicInspirationSpent = null,
}) {
  const showDice = useGameStore(s => s.showDice)

  const [pendingCheck, setPendingCheck] = useState(null)
  const [checkRolling, setCheckRolling] = useState(false)

  /**
   * 执行一次检定。返回要回传给 DM 的 autoMsg（失败或被中断时返回 null）。
   * 调用方负责：根据返回值决定是否调 handleAction，以及处理 UI focus。
   *
   * @returns {Promise<string|null>}
   */
  const rollPending = useCallback(async () => {
    if (!pendingCheck || checkRolling) return null
    setCheckRolling(true)
    try {
      // 3D 骰子动画 → 服务端计算
      const rollState = buildCheckRollState(pendingCheck, player)
      const hasAdvantageState = needsSecondD20(rollState)
      const { rolls = [], total } = await rollDice3D(20, hasAdvantageState ? 2 : 1)
      const d20 = rolls[0] ?? total
      const secondD20 = hasAdvantageState ? rolls[1] : null
      showDice({
        faces: 20,
        result: hasAdvantageState ? (rollState.advantage ? Math.max(d20, secondD20) : Math.min(d20, secondD20)) : d20,
        label: `${pendingCheck.check_type}检定`,
        count: hasAdvantageState ? 2 : 1,
      })
      const useLucky = Boolean(pendingCheck.use_lucky) && getLuckyPointsRemaining(player) > 0
      let luckyD20 = null
      if (useLucky) {
        const luckyRoll = await rollDice3D(20)
        luckyD20 = luckyRoll.total
        showDice({ faces: 20, result: luckyD20, label: 'Lucky reroll', count: 1 })
      }
      const bardic = getBardicInspiration(player)
      const useBardic = Boolean(pendingCheck.use_bardic_inspiration) && Boolean(bardic)
      let bardicRoll = null
      if (useBardic) {
        const bardicDice = await rollDice3D(bardic.faces)
        bardicRoll = bardicDice.total
        showDice({ faces: bardic.faces, result: bardicRoll, label: `Bardic Inspiration ${bardic.die}`, count: 1 })
      }

      const result = await gameApi.skillCheck({
        session_id:   sessionId,
        character_id: pendingCheck.character_id || playerId,
        skill:        pendingCheck.check_type,
        dc:           pendingCheck.dc,
        d20_value:    d20,
        second_d20_value: secondD20,
        ...(useLucky ? { use_lucky: true, lucky_d20_value: luckyD20 } : {}),
        ...(useBardic ? { use_bardic_inspiration: true, bardic_inspiration_roll: bardicRoll } : {}),
      })
      if (result.lucky?.spent && typeof onLuckySpent === 'function') {
        onLuckySpent(result.lucky.lucky_points_remaining)
      }
      if (result.bardic_inspiration?.spent && typeof onBardicInspirationSpent === 'function') {
        onBardicInspirationSpent(result.bardic_inspiration.uses_remaining)
      }

      const summary =
        `${pendingCheck.check_type}检定 (DC ${pendingCheck.dc})：` +
        `${formatD20Roll(result)} ${result.modifier >= 0 ? '+' : ''}${result.modifier}` +
        `${result.proficient ? ' [熟练]' : ''}` +
        `${result.disadvantage ? ' [劣势]' : ''}` +
        `${result.advantage ? ' [优势]' : ''}` +
        `${formatLuckyDetail(result)}` +
        `${formatBardicDetail(result)}` +
        ` = ${result.total} → ` +
        `${result.success ? '✅ 成功' : '❌ 失败'}`
      addLog('dice', summary, 'dice', { dice_result: result })

      // Juice：关键成功/失败的音效 + 震屏
      try {
        if (result.d20 === 20)      JuiceAudio.crit()
        else if (result.d20 === 1)  { JuiceAudio.miss(); JuiceShake(document.body, 6, 340) }
        else if (result.success)    JuiceAudio.unlock()
        else                        JuiceAudio.miss()
      } catch (_) {}

      // 带 context（原选项文本）一起送给 DM，不丢行动语义
      const ctxPart = pendingCheck.context ? ` 我的行动："${pendingCheck.context}"` : ''
      const autoMsg =
        `[${pendingCheck.check_type}检定 ${result.success ? '成功' : '失败'}: ` +
        `${result.total} vs DC${pendingCheck.dc}]${ctxPart}`

      setPendingCheck(null)
      return autoMsg
    } catch (e) {
      addLog('system', `检定失败: ${e.message}`, 'system')
      setPendingCheck(null)
      return null
    } finally {
      setCheckRolling(false)
    }
  }, [
    pendingCheck,
    checkRolling,
    sessionId,
    playerId,
    player,
    addLog,
    onLuckySpent,
    onBardicInspirationSpent,
    showDice,
  ])

  return {
    pendingCheck,
    setPendingCheck,
    checkRolling,
    rollPending,
  }
}
