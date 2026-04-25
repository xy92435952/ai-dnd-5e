/**
 * useCombatTargeting — 战斗界面"瞄准 / 视觉模式"集合状态。
 *
 * Combat.jsx 顶部原本有 7 个相关 useState，散落在多个 handler 里互相清除。
 * 抽到这里后：
 *   1. 状态集中，复用更容易
 *   2. clearTargeting / enterMoveMode / enterHelpMode 把"互斥模式切换"
 *      封装成一行，避免散落的 3 行 setter 调用
 *
 * 这是**纯客户端 UI 状态**，不调任何 API 也不维护订阅，安全地放在 hook 里。
 */
import { useCallback, useState } from 'react'

export function useCombatTargeting() {
  // 选中目标（点击敌人 / 队友头像后高亮）
  const [selectedTarget, setSelectedTarget] = useState(null)

  // 移动模式：地图格子变成"点击移动到此格"
  const [moveMode, setMoveMode] = useState(false)
  const [isRanged, setIsRanged] = useState(false)

  // 威胁区显示开关：红色斜纹覆盖敌人攻击范围
  const [showThreat, setShowThreat] = useState(false)

  // AoE 法术预览：选中 AoE 法术后地图 hover 显示冲击半径
  const [aoePreview, setAoePreview] = useState(null) // { radius, spellName } | null
  const [aoeHover,   setAoeHover]   = useState(null) // "x_y" | null

  // 协助模式：点击友军使其下次攻击获得优势
  const [helpMode, setHelpMode] = useState(false)

  // ── 互斥切换辅助 ──────────────────────────────────────

  /** 清除所有瞄准模式，回到中立。新一轮行动前调一下。 */
  const clearTargeting = useCallback(() => {
    setMoveMode(false)
    setHelpMode(false)
    setSelectedTarget(null)
  }, [])

  /** 切换移动模式。激活时会清掉协助模式和已选目标。 */
  const toggleMoveMode = useCallback(() => {
    setMoveMode(prev => !prev)
    setHelpMode(false)
    setSelectedTarget(null)
  }, [])

  /** 进入协助模式（互斥地关掉移动模式）。 */
  const enterHelpMode = useCallback(() => {
    setHelpMode(true)
    setMoveMode(false)
  }, [])

  /** 关闭 AoE 预览（spell modal 关闭时用）。 */
  const clearAoePreview = useCallback(() => {
    setAoePreview(null)
    setAoeHover(null)
  }, [])

  return {
    // 状态
    selectedTarget,
    moveMode, isRanged,
    showThreat,
    aoePreview, aoeHover,
    helpMode,
    // 直接 setter（外部偶尔需要细粒度控制时用）
    setSelectedTarget,
    setMoveMode, setIsRanged,
    setShowThreat,
    setAoePreview, setAoeHover,
    setHelpMode,
    // 高层动作（推荐使用）
    clearTargeting,
    toggleMoveMode,
    enterHelpMode,
    clearAoePreview,
  }
}
