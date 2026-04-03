import { useEffect, useRef, useState, useCallback } from 'react'
import { useGameStore } from '../store/gameStore'

/**
 * 3D 骰子动画覆盖层 — @3d-dice/dice-box-threejs
 *
 * 关键设计：DiceBox 容器始终存在于 DOM 中（用 visibility 控制显隐），
 * 避免每次掷骰重新创建 WebGL 上下文导致纹理加载失败。
 */

let diceBoxInstance = null
let initPromise = null

async function ensureDiceBox() {
  if (diceBoxInstance) return diceBoxInstance
  if (initPromise) return initPromise

  initPromise = (async () => {
    try {
      const mod = await import('@3d-dice/dice-box-threejs')
      const DiceBox = mod.default || mod

      const box = new DiceBox('#dice-roller-persistent', {
        assetPath: '/',
        theme_colorset: 'bronze',
        theme_material: 'metal',
        theme_surface: 'green-felt',
        gravity_multiplier: 500,
        baseScale: 100,
        strength: 2,
        shadows: true,
        sounds: false,
        light_intensity: 0.8,
      })

      await box.initialize()
      diceBoxInstance = box
      return box
    } catch (err) {
      console.warn('DiceBox 3D init failed:', err)
      initPromise = null
      return null
    }
  })()

  return initPromise
}

export default function DiceRollerOverlay() {
  const { diceRoll, hideDice, combatActive } = useGameStore()
  const [visible, setVisible] = useState(false)
  const [showResult, setShowResult] = useState(false)
  const [initFailed, setInitFailed] = useState(false)
  const hideTimerRef = useRef(null)
  const resultTimerRef = useRef(null)

  const dismiss = useCallback(() => {
    clearTimeout(hideTimerRef.current)
    clearTimeout(resultTimerRef.current)
    if (diceBoxInstance) { try { diceBoxInstance.clearDice() } catch {} }
    setVisible(false)
    setShowResult(false)
    hideDice()
  }, [hideDice])

  // 当 diceRoll 触发时：显示覆盖层 → 初始化(首次) → 掷骰
  useEffect(() => {
    if (!diceRoll) return

    const { faces = 20, result = 1 } = diceRoll
    setVisible(true)
    setShowResult(false)
    setInitFailed(false)

    const run = async () => {
      const box = await ensureDiceBox()

      if (box) {
        try {
          box.clearDice()
          await box.roll(`1d${faces}@${result}`)
        } catch (err) {
          console.warn('Roll error:', err)
        }
        resultTimerRef.current = setTimeout(() => setShowResult(true), 1800)
        hideTimerRef.current = setTimeout(dismiss, 4500)
      } else {
        // 3D 失败，直接显示结果
        setInitFailed(true)
        resultTimerRef.current = setTimeout(() => setShowResult(true), 200)
        hideTimerRef.current = setTimeout(dismiss, 2500)
      }
    }

    run()

    return () => {
      clearTimeout(resultTimerRef.current)
      clearTimeout(hideTimerRef.current)
    }
  }, [diceRoll, dismiss])

  const { faces = 20, result = 1, label = '' } = diceRoll || {}
  const isCrit = faces === 20 && result === 20
  const isFumble = faces === 20 && result === 1
  const numColor = isCrit ? '#22c55e' : isFumble ? '#ef4444' : combatActive ? '#f87171' : '#f5e280'

  return (
    <>
      {/* 持久化 3D 容器 — 始终存在于 DOM，用 visibility 控制 */}
      <div id="dice-roller-persistent" style={{
        position: 'fixed',
        top: visible ? '50%' : '-9999px',
        left: visible ? '50%' : '-9999px',
        transform: visible ? 'translate(-50%, -60%)' : 'none',
        width: Math.min(480, typeof window !== 'undefined' ? window.innerWidth - 32 : 480),
        height: 280,
        zIndex: visible ? 10000 : -1,
        borderRadius: 16,
        overflow: 'hidden',
        pointerEvents: visible ? 'auto' : 'none',
      }} />

      {/* 覆盖层 UI */}
      {visible && (
        <div onClick={dismiss} style={{
          position: 'fixed', inset: 0, zIndex: 9999, cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          background: combatActive
            ? 'radial-gradient(ellipse at center, rgba(40,5,5,0.92), rgba(0,0,0,0.96))'
            : 'radial-gradient(ellipse at center, rgba(35,25,8,0.90), rgba(0,0,0,0.95))',
          animation: 'diceFadeIn 0.2s ease',
        }}>
          {/* 3D 骰子区域的占位（实际渲染在持久化容器中） */}
          <div style={{
            width: Math.min(480, typeof window !== 'undefined' ? window.innerWidth - 32 : 480),
            height: 280,
            borderRadius: 16,
            background: 'radial-gradient(ellipse at center, rgba(60,45,25,0.3), rgba(20,15,8,0.5))',
            border: '1px solid rgba(201,168,76,0.1)',
          }} onClick={e => e.stopPropagation()} />

          {/* Fallback SVG（3D 失败时） */}
          {initFailed && <FallbackDice faces={faces} combatActive={combatActive} />}

          {/* 数值结果 */}
          {showResult && (
            <div style={{ textAlign: 'center', marginTop: 16, animation: 'dicePopIn 0.35s cubic-bezier(0.34,1.56,0.64,1)' }}>
              <p style={{
                fontSize: 76, fontWeight: 900, lineHeight: 1, margin: 0,
                fontFamily: 'Georgia, serif', color: numColor,
                textShadow: `0 0 30px ${numColor}88, 0 0 60px ${numColor}44, 0 4px 10px #000`,
              }}>{result}</p>
              {label && <p style={{ fontSize: 14, letterSpacing: 1, marginTop: 8, color: combatActive ? 'rgba(252,165,165,0.7)' : 'rgba(240,208,96,0.7)' }}>{label}</p>}
              {(isCrit || isFumble) && (
                <div style={{
                  marginTop: 10, padding: '8px 24px', borderRadius: 8, display: 'inline-block',
                  background: isCrit ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                  border: `1px solid ${isCrit ? '#22c55e55' : '#ef444455'}`,
                }}>
                  <p style={{ fontSize: 20, fontWeight: 900, letterSpacing: 2, margin: 0, color: isCrit ? '#22c55e' : '#ef4444' }}>
                    {isCrit ? '⚡ 大成功！' : '💀 大失败！'}
                  </p>
                </div>
              )}
            </div>
          )}

          <p style={{ fontSize: 10, marginTop: 14, opacity: 0.2, color: combatActive ? '#fca5a5' : '#c9a84c' }}>点击任意处关闭</p>
        </div>
      )}

      <style>{`
        @keyframes diceFadeIn { from{opacity:0} to{opacity:1} }
        @keyframes dicePopIn { from{transform:scale(.5) translateY(10px);opacity:0} to{transform:scale(1) translateY(0);opacity:1} }
        #dice-roller-persistent canvas { width:100%!important; height:100%!important; display:block; }
      `}</style>
    </>
  )
}

function FallbackDice({ faces, combatActive }) {
  const pts = { 4:'60,10 110,100 10,100', 6:'10,10 110,10 110,110 10,110', 8:'60,5 115,60 60,115 5,60',
    20:'60,5 112,35 98,95 22,95 8,35', 100:'60,5 112,35 98,95 22,95 8,35' }[faces] || '60,5 112,35 98,95 22,95 8,35'
  return (
    <div style={{ width:100, height:100, marginTop:20, animation:'diceTumble .4s ease-in-out infinite',
      filter:`drop-shadow(0 0 12px ${combatActive?'#dc2626':'#c9a84c'}88)` }}>
      <svg viewBox="0 0 120 120" width="100" height="100">
        <polygon points={pts} fill={combatActive?'#2d3340':'#c9a84c'} stroke={combatActive?'#4b5563':'#f0d060'} strokeWidth="2"/>
        <text x="60" y="65" textAnchor="middle" dominantBaseline="middle" fill={combatActive?'#8a8a9a':'#3a2a10'}
          fontSize="28" fontWeight="900" fontFamily="Georgia,serif" opacity=".6">d{faces}</text>
      </svg>
      <style>{`@keyframes diceTumble{0%{transform:rotate(0) scale(1)}25%{transform:rotate(15deg) scale(.9)}50%{transform:rotate(-10deg) scale(1.05)}75%{transform:rotate(8deg) scale(.95)}100%{transform:rotate(0) scale(1)}}`}</style>
    </div>
  )
}
