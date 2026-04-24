/**
 * DMThinkingOverlay — DM 思考中沉浸式等待层
 * ==========================================
 * 当 isLoading=true 时覆盖在对话舞台上。
 * 结构（垂直 flex）：
 *   ① Stack       — 符文环 + 兜帽老者 silhouette（3 层叠加）
 *   ② Title       — "艾尔德林 · 编织故事中 ●●●"
 *   ③ Hint        — 每 2.8s 轮播的提示词
 *
 * 顶部额外浮动一条金色流光条（z-index 最高）。
 *
 * 用法：
 *   <DMThinkingOverlay visible={isLoading} />
 */

import { useEffect, useState } from 'react'

const HINTS = [
  '翻阅命运之书的古老页章',
  '掷出藏在时间背后的骰',
  '召唤远方世界的回响',
  '梳理故事的经纬',
  '倾听每个角色心中的声音',
  '校对规则之书的细则',
  '描绘光与影的边界',
  '从无数可能中挑一条路径',
  '等待灵感从黑暗中浮现',
  '拨动命运之轮的第一齿',
  '在牌堆中寻找属于你的那一张',
  '搜集散落在风中的低语',
]

export default function DMThinkingOverlay({ visible }) {
  const [hintIdx, setHintIdx] = useState(() => Math.floor(Math.random() * HINTS.length))

  useEffect(() => {
    if (!visible) return
    const id = setInterval(() => {
      setHintIdx(i => (i + 1) % HINTS.length)
    }, 2800)
    return () => clearInterval(id)
  }, [visible])

  if (!visible) return null

  return (
    <div className="dm-thinking-overlay" aria-live="polite" aria-label="地下城主正在思考">
      {/* 顶部金色流光条（最高 z-index） */}
      <div className="dm-thinking-topbar" />

      {/* 背景暗化 + 轻模糊 */}
      <div className="dm-thinking-bg" />

      {/* 主内容：垂直 flex */}
      <div className="dm-thinking-content">

        {/* ① 视觉中心：3 层叠加（外环 / 内环 / portrait） */}
        <div className="dm-thinking-stack">
          <div className="dm-thinking-ring outer" aria-hidden="true">
            <svg viewBox="0 0 240 240" width="240" height="240">
              <g fill="none" stroke="rgba(240,208,96,.55)" strokeWidth="1">
                <circle cx="120" cy="120" r="110" strokeDasharray="4 6" />
                <circle cx="120" cy="120" r="92" />
              </g>
              <g fill="rgba(240,208,96,.8)" fontFamily="serif" fontSize="14" textAnchor="middle">
                <text x="120" y="14">✦</text>
                <text x="120" y="232">✦</text>
                <text x="14" y="124">❖</text>
                <text x="228" y="124">❖</text>
              </g>
            </svg>
          </div>

          <div className="dm-thinking-ring inner" aria-hidden="true" />

          <div className="dm-thinking-portrait" aria-hidden="true">
            <div className="hood" />
            <div className="eye left" />
            <div className="eye right" />
          </div>
        </div>

        {/* ② 标题 */}
        <div className="dm-thinking-title">
          <span className="name">艾尔德林</span>
          <span className="sep">·</span>
          <span className="role">编织故事中</span>
          <span className="dots" aria-hidden="true">
            <span /><span /><span />
          </span>
        </div>

        {/* ③ 轮播提示词 */}
        <div className="dm-thinking-hint" key={hintIdx}>
          ✦ {HINTS[hintIdx]} ✦
        </div>
      </div>
    </div>
  )
}
