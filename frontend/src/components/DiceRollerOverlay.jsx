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

export function normalizeDiceRollResult(results, faces = 20, count = 1) {
  const diceCount = Math.max(1, Math.min(Number(count) || 1, 10))
  const dieFaces = Math.max(1, Number(faces) || 20)
  const rolls = []

  for (const group of Array.isArray(results) ? results : []) {
    const childRolls = extractRollValues(group?.rollsArray)
    if (childRolls.length) {
      rolls.push(...childRolls)
      continue
    }

    const nestedRolls = extractRollValues(group?.rolls)
    if (nestedRolls.length) {
      rolls.push(...nestedRolls)
      continue
    }

    if (group?.value != null) {
      const value = Number(group.value)
      if (Number.isFinite(value)) rolls.push(value)
    }
  }

  while (rolls.length < diceCount) {
    rolls.push(Math.floor(Math.random() * dieFaces) + 1)
  }

  const boundedRolls = rolls
    .slice(0, diceCount)
    .map(value => Math.max(1, Math.min(dieFaces, Math.floor(Number(value) || 1))))
  return {
    total: boundedRolls.reduce((sum, value) => sum + value, 0),
    rolls: boundedRolls,
  }
}

function extractRollValues(value) {
  const items = Array.isArray(value)
    ? value
    : value && typeof value === 'object'
      ? Object.values(value)
      : []
  return items
    .map(item => Number(item?.value ?? item?.roll ?? item))
    .filter(number => Number.isFinite(number))
}

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
  // Juice：投掷开始时播放骰子音效（WebAudio 合成木桌上的骰声）
  try { window.JuiceAudio?.dice?.() } catch (e) {}

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
        resolve(normalizeDiceRollResult(results, faces, diceCount))
      }
      // 安全超时
      setTimeout(() => {
        resolve(normalizeDiceRollResult(null, faces, diceCount))
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
    // 取消任何正在进行的 dismiss 定时器
    clearTimeout(hideTimerRef.current)
    if (diceBoxInstance) { try { diceBoxInstance.clear() } catch {} }
    setVisible(true)
    setPhase('waiting')
    setRollResult(null)
  }, [dicePrompt])

  // ── 阶段3：显示结果覆盖层 ──
  useEffect(() => {
    if (!diceRoll) return
    const myId = ++animIdRef.current
    // 取消之前的 dismiss 定时器
    clearTimeout(hideTimerRef.current)
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
    if (phase !== 'waiting') return

    // 保存当前 prompt 数据（因为马上要清除状态）
    const currentPrompt = _pendingRollConfig || dicePrompt
    if (!currentPrompt) return

    setPhase('rolling')
    const { faces, count } = currentPrompt
    hideDicePrompt()  // 清除 prompt 状态

    const result = await _executeRoll(faces, count || 1)

    // 将结果传回给 rollDice3D 的调用方
    if (_pendingRollResolve) {
      const resolve = _pendingRollResolve
      _pendingRollResolve = null
      _pendingRollConfig = null
      resolve(result)
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
      <div
        id="dice-roller-persistent"
        className="dice-roller-persistent"
        data-visible={visible}
      />

      {/* 覆盖层 UI */}
      {visible && (
        <div
          className="dice-overlay-shell"
          data-phase={phase}
          data-combat={combatActive}
          onClick={phase === 'result' ? dismiss : undefined}
        >
          {/* 3D 区域 */}
          <div
            className="dice-surface"
            data-phase={phase}
            onClick={e => e.stopPropagation()}
          />

          {/* ── 等待点击投掷 ── */}
          {phase === 'waiting' && (
            <div className="dice-throw-panel">
              <button
                className="dice-throw-button"
                data-combat={combatActive}
                onClick={handleThrow}
              >
                🎲 投掷 {count > 1 ? `${count}` : ''}d{promptData.faces || 20}
              </button>
              <p className="dice-throw-helper" data-combat={combatActive}>
                点击按钮投出骰子
              </p>
            </div>
          )}

          {/* ── 正在投掷 ── */}
          {phase === 'rolling' && (
            <p className="dice-rolling-copy" data-combat={combatActive}>
              骰子飞出...
            </p>
          )}

          {/* ── 结果显示 ── */}
          {phase === 'result' && result > 0 && (
            <div
              className="dice-result-stack"
              style={{ '--dice-result-color': numColor }}
            >
              <p className="dice-result-number">{result}</p>
              {label && (
                <p className="dice-result-label" data-combat={combatActive}>
                  {label}
                </p>
              )}
              {(isCrit || isFumble) && (
                <div
                  className="dice-result-badge"
                  data-outcome={isCrit ? 'crit' : 'fumble'}
                >
                  <p className="dice-result-badge-text">
                    {isCrit ? '⚡ 大成功！' : '💀 大失败！'}
                  </p>
                </div>
              )}
              <p className="dice-result-dismiss-hint" data-combat={combatActive}>点击任意处关闭</p>
            </div>
          )}
        </div>
      )}
    </>
  )
}
