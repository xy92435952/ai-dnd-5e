/**
 * juice.js — 游戏感反馈工具库
 * =================================
 * 源自 design bundle (chat1.md 最后阶段)，移植到当前 React 项目。
 * 故意不包含 3D 骰子组件（我们已有 DiceRollerOverlay / FantasticDice），
 * 但保留骰子音效 JuiceAudio.dice() 可供现有骰子系统调用。
 *
 * 功能：
 *   1) JuiceAudio — WebAudio 程序化合成音效（12 种）
 *   2) shake(el, intensity, duration) — 震屏
 *   3) flash(el, color, duration) — 闪白
 *   4) useCountUp(target, duration) — 数字滚动 hook
 *   5) useFloaters() — 浮字列表 hook
 *
 * 使用方式：
 *   import { JuiceAudio, shake, flash, useCountUp, useFloaters } from '@/juice'
 *   JuiceAudio.crit()
 *   shake(document.querySelector('.combat-grid'))
 *   const hp = useCountUp(character.hp_current)
 */

import { useEffect, useRef, useState } from 'react'

// ── 1. 程序化音效（WebAudio） ─────────────────────────────
const JuiceAudio = (() => {
  let ctx = null
  let muted = false

  const getCtx = () => {
    if (!ctx) {
      try {
        const Ctor = window.AudioContext || window.webkitAudioContext
        if (Ctor) ctx = new Ctor()
      } catch (e) { /* 浏览器不支持 WebAudio */ }
    }
    if (ctx && ctx.state === 'suspended') ctx.resume()
    return ctx
  }

  const env = (g, t0, a, d, peak, sus) => {
    g.gain.setValueAtTime(0, t0)
    g.gain.linearRampToValueAtTime(peak, t0 + a)
    g.gain.exponentialRampToValueAtTime(Math.max(sus, 0.0001), t0 + a + d)
  }

  const tone = (freq, dur, type = 'sine', vol = 0.15, bend = 0) => {
    if (muted) return
    const c = getCtx(); if (!c) return
    const t0 = c.currentTime
    const osc = c.createOscillator()
    const g = c.createGain()
    osc.type = type
    osc.frequency.setValueAtTime(freq, t0)
    if (bend) osc.frequency.exponentialRampToValueAtTime(Math.max(freq + bend, 40), t0 + dur)
    env(g, t0, 0.004, dur * 0.95, vol, 0.0001)
    osc.connect(g).connect(c.destination)
    osc.start(t0); osc.stop(t0 + dur + 0.05)
  }

  const noise = (dur, vol = 0.15, filterFreq = 2000) => {
    if (muted) return
    const c = getCtx(); if (!c) return
    const t0 = c.currentTime
    const len = Math.floor(c.sampleRate * dur)
    const buf = c.createBuffer(1, len, c.sampleRate)
    const data = buf.getChannelData(0)
    for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len)
    const src = c.createBufferSource(); src.buffer = buf
    const filt = c.createBiquadFilter(); filt.type = 'bandpass'
    filt.frequency.value = filterFreq; filt.Q.value = 1.5
    const g = c.createGain()
    env(g, t0, 0.002, dur * 0.9, vol, 0.0001)
    src.connect(filt).connect(g).connect(c.destination)
    src.start(t0)
  }

  return {
    mute: (val = true) => { muted = val },
    isMuted: () => muted,
    hover:  () => tone(1600, 0.04, 'sine', 0.04),
    click:  () => { tone(800, 0.05, 'triangle', 0.08, -200) },
    select: () => {
      tone(660, 0.06, 'sine', 0.09)
      setTimeout(() => tone(990, 0.08, 'sine', 0.08), 40)
    },
    // 骰子音效 —— 从 design bundle 学过来，供 DiceRollerOverlay 复用
    dice: () => {
      for (let i = 0; i < 6; i++) {
        setTimeout(() => noise(0.04, 0.12, 3500 + Math.random() * 1500), i * 45)
      }
    },
    crit: () => {
      tone(880, 0.08, 'square', 0.1, 200)
      setTimeout(() => tone(1320, 0.12, 'triangle', 0.12, 400), 70)
      setTimeout(() => tone(1760, 0.2, 'sine', 0.1, -800), 160)
    },
    hit: () => {
      noise(0.08, 0.2, 800)
      tone(220, 0.1, 'sawtooth', 0.08, -80)
    },
    miss: () => { tone(420, 0.09, 'triangle', 0.06, -260) },
    heal: () => {
      tone(523, 0.1, 'sine', 0.08)
      setTimeout(() => tone(784, 0.18, 'sine', 0.1), 60)
      setTimeout(() => tone(1046, 0.22, 'sine', 0.08), 160)
    },
    turn: () => {
      tone(392, 0.15, 'sine', 0.08)
      setTimeout(() => tone(523, 0.2, 'sine', 0.08), 100)
    },
    page:   () => { noise(0.12, 0.09, 4500) },
    unlock: () => {
      tone(440, 0.08, 'triangle', 0.08)
      setTimeout(() => tone(554, 0.08, 'triangle', 0.08), 80)
      setTimeout(() => tone(659, 0.08, 'triangle', 0.08), 160)
      setTimeout(() => tone(880, 0.35, 'sine', 0.12, 0), 240)
    },
  }
})()

// 挂到 window 方便在非 React 场景（如 DiceRollerOverlay 内部）直接调用
if (typeof window !== 'undefined') {
  window.JuiceAudio = JuiceAudio
}

// ── 2. 震屏 & 闪白 ────────────────────────────────────────
function shake(el, intensity = 8, duration = 380) {
  if (!el) return
  el.style.setProperty('--shake-x', intensity + 'px')
  el.classList.remove('jc-shake')
  // force reflow
  void el.offsetWidth
  el.classList.add('jc-shake')
  setTimeout(() => el.classList.remove('jc-shake'), duration)
}

function flash(el, color = 'rgba(255,240,200,.6)', duration = 260) {
  if (!el) return
  const f = document.createElement('div')
  f.style.cssText = [
    'position:absolute', 'inset:0',
    `background:${color}`,
    'pointer-events:none', 'z-index:9999',
    `animation:jcFlash ${duration}ms ease-out forwards`,
    'mix-blend-mode:screen',
  ].join(';')
  const prev = getComputedStyle(el).position
  if (prev === 'static') el.style.position = 'relative'
  el.appendChild(f)
  setTimeout(() => f.remove(), duration + 20)
}

// 也挂 window 方便 imperative 调用
if (typeof window !== 'undefined') {
  window.JuiceShake = shake
  window.JuiceFlash = flash
}

// ── 3. useCountUp — 数字滚动 hook ─────────────────────────
function useCountUp(target, duration = 600) {
  const [val, setVal] = useState(target)
  const prevTarget = useRef(target)
  useEffect(() => {
    if (prevTarget.current === target) return
    const from = prevTarget.current
    const to = target
    prevTarget.current = target
    const start = performance.now()
    let raf
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic
      setVal(Math.round(from + (to - from) * eased))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return val
}

// ── 4. 浮字管理 hook ──────────────────────────────────────
// 使用方式：
//   const [floaters, spawnFloater] = useFloaters()
//   spawnFloater({ text: '-12', kind: 'dmg', x: 140, y: 80 })
//   return <>{floaters.map(f => <div key={f.id} className={`jc-floater ${f.kind}`}
//                                        style={{left: f.x, top: f.y}}>{f.text}</div>)}</>
function useFloaters() {
  const [items, setItems] = useState([])
  const spawn = (opts) => {
    const id = Math.random().toString(36).slice(2)
    const dur = opts.kind === 'crit' ? 1600 : 1400
    setItems(prev => [...prev, { id, ...opts }])
    setTimeout(() => setItems(prev => prev.filter(x => x.id !== id)), dur)
  }
  return [items, spawn]
}

export { JuiceAudio, shake, flash, useCountUp, useFloaters }
