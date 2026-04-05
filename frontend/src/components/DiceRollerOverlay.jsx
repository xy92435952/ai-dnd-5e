import { useEffect, useRef, useState, useCallback } from 'react'
import { useGameStore } from '../store/gameStore'

/**
 * 3D 骰子动画覆盖层 — @3d-dice/dice-box (Fantastic Dice)
 *
 * Phase 14 设计：
 *   - 前端物理模拟的骰子结果即为实际游戏数值
 *   - 玩家需要点击才投掷骰子（增强沉浸感）
 *   - 骰子落定面 = 显示数值 = 后端使用数值
 */

let diceBoxInstance = null
let initPromise = null

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    if (diceBoxInstance) { try { diceBoxInstance.clear() } catch {} }
    diceBoxInstance = null
    initPromise = null
  })
}

async function ensureDiceBox() {
  if (diceBoxInstance) return diceBoxInstance
  if (initPromise) return initPromise

  initPromise = (async () => {
    try {
      const mod = await import('@3d-dice/dice-box')
      const DiceBox = mod.default || mod

      const box = new DiceBox({
        container: '#dice-roller-persistent',
        assetPath: '/assets/',
        theme: 'default',
        scale: 6,
        gravity: 1.2,         // 较低重力 → 骰子在空中停留更久
        mass: 1,
        friction: 0.5,        // 较低摩擦 → 骰子滚动更久
        restitution: 0.3,     // 有弹性 → 骰子落地后多弹几下
        settleTimeout: 5000,  // 最长 5 秒落定
        spinForce: 6,         // 旋转力度
        throwForce: 5,        // 抛出力度
        delay: 10,
        enableShadows: true,
        lightIntensity: 1,
        onRollComplete: (results) => {
          if (box._onSettled) box._onSettled(results)
        },
      })

      await box.init()
      diceBoxInstance = box
      return box
    } catch (err) {
      console.warn('DiceBox init failed:', err)
      initPromise = null
      return null
    }
  })()

  return initPromise
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// rollDice3D — 需要玩家点击才投掷
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// 全局 resolve 函数引用，让组件的点击事件能 resolve 这个 Promise
let _pendingRollResolve = null
let _pendingRollConfig = null

/**
 * 掷骰子并返回物理结果
 * 流程：显示"点击投掷"提示 → 玩家点击 → 3D 骰子飞出 → 物理落定 → 返回结果
 */
export async function rollDice3D(faces = 20, count = 1) {
  // 预初始化 DiceBox
  await ensureDiceBox()

  return new Promise((resolve) => {
    _pendingRollConfig = { faces, count }
    _pendingRollResolve = resolve

    // 通知组件显示"点击投掷"界面
    useGameStore.getState().showDicePrompt({ faces, count })
  })
}

// 实际执行投掷（由组件点击事件调用）
async function _executeRoll(faces, count) {
  const box = diceBoxInstance
  if (!box) {
    const rolls = Array.from({ length: count }, () => Math.floor(Math.random() * faces) + 1)
    return { total: rolls.reduce((a, b) => a + b, 0), rolls }
  }

  try {
    box.clear()
    const diceCount = Math.max(1, Math.min(count, 10))

    const rollPromise = new Promise(resolve => {
      box._onSettled = (results) => {
        if (results && results.length > 0) {
          const allRolls = []
          let total = 0
          for (const group of results) {
            if (group.rolls) {
              for (const r of group.rolls) {
                allRolls.push(r.value)
                total += r.value
              }
            } else if (group.value != null) {
              allRolls.push(group.value)
              total += group.value
            }
          }
          resolve({ total, rolls: allRolls })
        } else {
          const rolls = Array.from({ length: diceCount }, () => Math.floor(Math.random() * faces) + 1)
          resolve({ total: rolls.reduce((a, b) => a + b, 0), rolls })
        }
      }
      // 安全超时
      setTimeout(() => {
        const rolls = Array.from({ length: diceCount }, () => Math.floor(Math.random() * faces) + 1)
        resolve({ total: rolls.reduce((a, b) => a + b, 0), rolls })
      }, 8000)
    })

    await box.roll(`${diceCount}d${faces}`)
    return await rollPromise
  } catch (err) {
    console.warn('Roll error:', err)
    try { box.clear() } catch (_) {}
    const rolls = Array.from({ length: count }, () => Math.floor(Math.random() * faces) + 1)
    return { total: rolls.reduce((a, b) => a + b, 0), rolls }
  }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// React 组件
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export default function DiceRollerOverlay() {
  const { diceRoll, dicePrompt, hideDice, hideDicePrompt, combatActive } = useGameStore()
  const [visible, setVisible] = useState(false)
  const [phase, setPhase] = useState('idle')  // 'idle' | 'waiting' | 'rolling' | 'result'
  const [rollResult, setRollResult] = useState(null)
  const hideTimerRef = useRef(null)
  const animIdRef = useRef(0)

  const dismiss = useCallback(() => {
    clearTimeout(hideTimerRef.current)
    hideTimerRef.current = null
    if (diceBoxInstance) { try { diceBoxInstance.clear() } catch {} }
    setVisible(false)
    setPhase('idle')
    setRollResult(null)
    hideDice()
    hideDicePrompt()
  }, [hideDice, hideDicePrompt])

  // ── 阶段1：等待玩家点击投掷 ──
  useEffect(() => {
    if (!dicePrompt) return
    setVisible(true)
    setPhase('waiting')
    setRollResult(null)
  }, [dicePrompt])

  // ── 阶段3：显示结果覆盖层 ──
  useEffect(() => {
    if (!diceRoll) return
    const myId = ++animIdRef.current
    setVisible(true)
    setPhase('result')
    setRollResult(diceRoll)

    hideTimerRef.current = setTimeout(() => {
      if (animIdRef.current === myId) dismiss()
    }, 3500)

    return () => clearTimeout(hideTimerRef.current)
  }, [diceRoll, dismiss])

  // ── 点击投掷处理 ──
  const handleThrow = async () => {
    if (phase !== 'waiting' || !dicePrompt) return

    setPhase('rolling')
    const { faces, count } = dicePrompt
    hideDicePrompt()  // 清除 prompt 状态

    const result = await _executeRoll(faces, count)

    // 将结果传回给 rollDice3D 的调用方
    if (_pendingRollResolve) {
      _pendingRollResolve(result)
      _pendingRollResolve = null
      _pendingRollConfig = null
    }
  }

  // 展示数据
  const promptData = dicePrompt || {}
  const resultData = rollResult || diceRoll || {}
  const faces = resultData.faces || promptData.faces || 20
  const result = resultData.result || resultData.total || 0
  const label = resultData.label || ''
  const count = promptData.count || 1
  const isCrit = faces === 20 && result === 20
  const isFumble = faces === 20 && result === 1
  const numColor = isCrit ? '#22c55e' : isFumble ? '#ef4444' : combatActive ? '#f87171' : '#f5e280'

  return (
    <>
      {/* 持久化 3D 容器 */}
      <div id="dice-roller-persistent" style={{
        position: 'fixed',
        top: visible ? '50%' : '-9999px',
        left: visible ? '50%' : '-9999px',
        transform: visible ? 'translate(-50%, -60%)' : 'none',
        width: Math.min(480, typeof window !== 'undefined' ? window.innerWidth - 32 : 480),
        height: 300,
        zIndex: visible ? 10000 : -1,
        borderRadius: 16,
        overflow: 'hidden',
        pointerEvents: visible ? 'auto' : 'none',
      }} />

      {/* 覆盖层 UI */}
      {visible && (
        <div onClick={phase === 'result' ? dismiss : undefined} style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          cursor: phase === 'result' ? 'pointer' : 'default',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          background: combatActive
            ? 'radial-gradient(ellipse at center, rgba(40,5,5,0.92), rgba(0,0,0,0.96))'
            : 'radial-gradient(ellipse at center, rgba(35,25,8,0.90), rgba(0,0,0,0.95))',
          animation: 'diceFadeIn 0.3s ease',
        }}>
          {/* 3D 区域 */}
          <div style={{
            width: Math.min(480, typeof window !== 'undefined' ? window.innerWidth - 32 : 480),
            height: 300,
            borderRadius: 16,
            background: 'radial-gradient(ellipse at center, rgba(60,45,25,0.3), rgba(20,15,8,0.5))',
            border: `1px solid ${phase === 'waiting' ? 'rgba(201,168,76,0.3)' : 'rgba(201,168,76,0.1)'}`,
            transition: 'border-color 0.3s',
          }} onClick={e => e.stopPropagation()} />

          {/* ── 等待点击投掷 ── */}
          {phase === 'waiting' && (
            <div style={{ textAlign: 'center', marginTop: 20, animation: 'diceFadeIn 0.4s ease' }}>
              <button
                onClick={handleThrow}
                style={{
                  background: combatActive
                    ? 'linear-gradient(135deg, #7f1d1d, #991b1b)'
                    : 'linear-gradient(135deg, #78350f, #92400e)',
                  border: `2px solid ${combatActive ? '#ef4444' : '#f59e0b'}`,
                  borderRadius: 12,
                  padding: '14px 40px',
                  cursor: 'pointer',
                  color: '#fff',
                  fontSize: 18,
                  fontWeight: 800,
                  fontFamily: 'Georgia, serif',
                  letterSpacing: 2,
                  textShadow: '0 2px 4px rgba(0,0,0,0.5)',
                  boxShadow: `0 0 20px ${combatActive ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)'}, 0 4px 12px rgba(0,0,0,0.4)`,
                  transition: 'all 0.2s',
                  animation: 'throwPulse 2s ease-in-out infinite',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.transform = 'scale(1.08)'
                  e.currentTarget.style.boxShadow = `0 0 30px ${combatActive ? 'rgba(239,68,68,0.5)' : 'rgba(245,158,11,0.5)'}, 0 6px 20px rgba(0,0,0,0.5)`
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.transform = 'scale(1)'
                  e.currentTarget.style.boxShadow = `0 0 20px ${combatActive ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)'}, 0 4px 12px rgba(0,0,0,0.4)`
                }}
              >
                🎲 投掷 {count > 1 ? `${count}` : ''}d{promptData.faces || 20}
              </button>
              <p style={{
                fontSize: 11, marginTop: 10, letterSpacing: 1,
                color: combatActive ? 'rgba(252,165,165,0.4)' : 'rgba(240,208,96,0.4)',
              }}>
                点击按钮投出骰子
              </p>
            </div>
          )}

          {/* ── 正在投掷 ── */}
          {phase === 'rolling' && (
            <p style={{
              fontSize: 14, fontWeight: 600, marginTop: 16, letterSpacing: 2,
              color: combatActive ? 'rgba(252,165,165,0.6)' : 'rgba(240,208,96,0.6)',
              animation: 'diceFadeIn 0.3s ease',
            }}>
              骰子飞出...
            </p>
          )}

          {/* ── 结果显示 ── */}
          {phase === 'result' && result > 0 && (
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
              <p style={{ fontSize: 10, marginTop: 12, opacity: 0.2, color: combatActive ? '#fca5a5' : '#c9a84c' }}>点击任意处关闭</p>
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes diceFadeIn { from{opacity:0} to{opacity:1} }
        @keyframes dicePopIn { from{transform:scale(.5) translateY(10px);opacity:0} to{transform:scale(1) translateY(0);opacity:1} }
        @keyframes throwPulse {
          0%, 100% { box-shadow: 0 0 20px rgba(245,158,11,0.3), 0 4px 12px rgba(0,0,0,0.4); }
          50% { box-shadow: 0 0 35px rgba(245,158,11,0.5), 0 6px 16px rgba(0,0,0,0.5); }
        }
        #dice-roller-persistent canvas { width:100%!important; height:100%!important; display:block; }
      `}</style>
    </>
  )
}
