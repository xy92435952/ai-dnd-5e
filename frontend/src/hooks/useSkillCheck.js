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

export function useSkillCheck({ sessionId, playerId, addLog }) {
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
      const { total: d20 } = await rollDice3D(20)
      showDice({ faces: 20, result: d20, label: `${pendingCheck.check_type}检定` })

      const result = await gameApi.skillCheck({
        session_id:   sessionId,
        character_id: pendingCheck.character_id || playerId,
        skill:        pendingCheck.check_type,
        dc:           pendingCheck.dc,
        d20_value:    d20,
      })

      const summary =
        `${pendingCheck.check_type}检定 (DC ${pendingCheck.dc})：` +
        `d20=${result.d20} ${result.modifier >= 0 ? '+' : ''}${result.modifier}` +
        `${result.proficient ? ' [熟练]' : ''} = ${result.total} → ` +
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
  }, [pendingCheck, checkRolling, sessionId, playerId, addLog, showDice])

  return {
    pendingCheck,
    setPendingCheck,
    checkRolling,
    rollPending,
  }
}
