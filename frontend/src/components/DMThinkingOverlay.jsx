/**
 * DMThinkingOverlay — DM 思考中沉浸式等待层
 * ==========================================
 * 视觉隐喻：DM 在编织命运——中心能量核 + 8 个轨道节点 + 巡游命运游标
 *
 * 结构（垂直 flex）：
 *   ① FateWeave 命运之网 — 外环 + 内环 + 命运之核（核心能量 + 符文 + 节点 + 游标）
 *   ② Title       — "艾尔德林 · 编织命运 ●●●"
 *   ③ Hint        — 每 2.8s 轮播的命运提示词
 *
 * 顶部额外浮动一条金色流光条（z-index 最高）。
 *
 * 用法：
 *   <DMThinkingOverlay visible={isLoading} />
 */

import { useEffect, useState } from 'react'

const HINTS = [
  '为你拨动因果的丝线',
  '预演多条时间线的分叉',
  '称量每一次选择的代价',
  '在无尽可能中筛选命运',
  '倾听骰子落地前的回响',
  '翻阅命运之书的古老页章',
  '召唤远方世界的回声',
  '梳理故事的经纬',
  '在牌堆中寻找属于你的那一张',
  '对准此刻与下一刻的齿轮',
  '凝视未至的可能',
  '权衡规则与传说的边界',
]

const ORBIT_NODES = 8

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
    <div className="dm-thinking-overlay" aria-live="polite" aria-label="地下城主正在编织命运">
      {/* 顶部金色流光条（最高 z-index） */}
      <div className="dm-thinking-topbar" />

      {/* 背景暗化 + 轻模糊 */}
      <div className="dm-thinking-bg" />

      {/* 主内容 */}
      <div className="dm-thinking-content">

        {/* ① 命运之网 · 视觉中心 */}
        <div className="fate-weave">
          {/* 外层法阵装饰（12s 正向旋转） */}
          <div className="fate-ring outer" aria-hidden="true">
            <svg viewBox="0 0 240 240" width="240" height="240">
              <g fill="none" stroke="rgba(240,208,96,.55)" strokeWidth="1">
                <circle cx="120" cy="120" r="110" strokeDasharray="4 6" />
                <circle cx="120" cy="120" r="94" />
              </g>
              <g fill="rgba(240,208,96,.8)" fontFamily="serif" fontSize="14" textAnchor="middle">
                <text x="120" y="14">✦</text>
                <text x="120" y="232">✦</text>
                <text x="14" y="124">❖</text>
                <text x="228" y="124">❖</text>
              </g>
            </svg>
          </div>

          {/* 内层虚线环（反向旋转） */}
          <div className="fate-ring inner" aria-hidden="true" />

          {/* 命运之核：连线 + 节点 + 核心 + 游标 */}
          <div className="fate-core" aria-hidden="true">

            {/* 8 条连线（从中心到 8 个节点方向） */}
            <svg className="fate-lines" viewBox="-100 -100 200 200">
              {Array.from({ length: ORBIT_NODES }).map((_, i) => {
                const rad = (i * 2 * Math.PI) / ORBIT_NODES
                const x2 = Math.cos(rad) * 78
                const y2 = Math.sin(rad) * 78
                return (
                  <line
                    key={i}
                    x1="0" y1="0"
                    x2={x2} y2={y2}
                    className="fate-line"
                    style={{ '--i': i }}
                  />
                )
              })}
            </svg>

            {/* 8 个轨道节点（整体 20s 旋转） */}
            <div className="fate-orbit">
              {Array.from({ length: ORBIT_NODES }).map((_, i) => (
                <div
                  key={i}
                  className="orbit-node"
                  style={{ '--i': i, '--n': ORBIT_NODES }}
                />
              ))}
            </div>

            {/* 命运游标：匀速绕行 + 到节点时脉冲放大（"抓取"） */}
            <div className="fate-cursor-orbit">
              <div className="fate-cursor" />
            </div>

            {/* 中心能量核心 */}
            <div className="fate-nucleus">
              <div className="nucleus-glow" />
              <div className="nucleus-core" />
              {/* 核心内部三组缓慢旋转的神秘符号 */}
              <svg className="nucleus-runes" viewBox="-50 -50 100 100">
                <g className="rune-ring">
                  <text x="0"   y="-32" textAnchor="middle" fontSize="9">✦</text>
                  <text x="28"  y="16"  textAnchor="middle" fontSize="9">◈</text>
                  <text x="-28" y="16"  textAnchor="middle" fontSize="9">❖</text>
                </g>
                <g className="rune-ring mid">
                  <text x="-20" y="-18" textAnchor="middle" fontSize="7">✧</text>
                  <text x="22"  y="-14" textAnchor="middle" fontSize="7">⊕</text>
                  <text x="0"   y="25"  textAnchor="middle" fontSize="7">⊗</text>
                </g>
              </svg>
            </div>

          </div>
        </div>

        {/* ② 标题 */}
        <div className="dm-thinking-title">
          <span className="name">艾尔德林</span>
          <span className="sep">·</span>
          <span className="role">编织命运</span>
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
