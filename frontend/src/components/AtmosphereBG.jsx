/**
 * AtmosphereBG — BG3 风格大气背景层
 *
 * 包含：
 * - 5 道神圣光束 (god-rays)
 * - 双圈反向旋转符文阵 (rune circles)
 * - 60 颗漂浮尘埃 (dust)
 * - 余烬粒子 (embers，可关闭)
 * - 暗角 (vignette)
 *
 * 用法：在 App.jsx 顶层放一个 <AtmosphereBG />（fixed inset:0，不影响布局）
 *
 * 来源：design v0.10 prototype（BG3 风格）。
 */
import { useEffect, useRef } from 'react'

export default function AtmosphereBG({ embers = true }) {
  const dustRef = useRef(null)
  const embersRef = useRef(null)

  useEffect(() => {
    // 漂浮尘埃
    const dustEl = dustRef.current
    if (dustEl) {
      dustEl.innerHTML = ''
      for (let i = 0; i < 60; i++) {
        const d = document.createElement('span')
        d.style.left = (Math.random() * 100) + '%'
        d.style.top = (Math.random() * 100) + '%'
        d.style.animationDuration = (12 + Math.random() * 18) + 's'
        d.style.animationDelay = (-Math.random() * 30) + 's'
        d.style.opacity = (0.4 + Math.random() * 0.5)
        d.style.transform = `scale(${0.5 + Math.random() * 1.8})`
        dustEl.appendChild(d)
      }
    }
  }, [])

  useEffect(() => {
    const embersEl = embersRef.current
    if (!embersEl) return
    if (!embers) {
      embersEl.innerHTML = ''
      embersEl.style.display = 'none'
      return
    }
    embersEl.style.display = 'block'
    embersEl.innerHTML = ''
    for (let i = 0; i < 40; i++) {
      const e = document.createElement('div')
      e.className = 'ember'
      e.style.left = (Math.random() * 100) + '%'
      e.style.animationDuration = (8 + Math.random() * 12) + 's'
      e.style.animationDelay = (-Math.random() * 20) + 's'
      e.style.opacity = (0.3 + Math.random() * 0.7)
      e.style.transform = `scale(${0.6 + Math.random() * 1.4})`
      embersEl.appendChild(e)
    }
  }, [embers])

  return (
    <div className="bg-atmosphere" aria-hidden="true">
      {/* 神圣光束 */}
      <div className="god-rays">
        <span style={{ '--r': '-14deg', '--l': '18%', '--d': 0.28 }} />
        <span style={{ '--r': '-6deg',  '--l': '32%', '--d': 0.20 }} />
        <span style={{ '--r': '4deg',   '--l': '52%', '--d': 0.34 }} />
        <span style={{ '--r': '12deg',  '--l': '70%', '--d': 0.22 }} />
        <span style={{ '--r': '20deg',  '--l': '84%', '--d': 0.18 }} />
      </div>

      {/* 旋转符文外圈 */}
      <svg className="rune-circle rune-outer" viewBox="0 0 800 800" preserveAspectRatio="xMidYMid meet">
        <defs>
          <filter id="atmosGlowA" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <g filter="url(#atmosGlowA)" stroke="rgba(240,208,96,.55)" fill="none">
          <circle cx="400" cy="400" r="380" strokeWidth="1" />
          <circle cx="400" cy="400" r="360" strokeWidth=".6" strokeDasharray="2 10" />
          <circle cx="400" cy="400" r="300" strokeWidth="1" />
          <circle cx="400" cy="400" r="290" strokeWidth=".6" strokeDasharray="18 6 2 6" />
          <g strokeWidth=".8" opacity=".7">
            <line x1="400" y1="20" x2="400" y2="60" />
            <line x1="400" y1="740" x2="400" y2="780" />
            <line x1="20" y1="400" x2="60" y2="400" />
            <line x1="740" y1="400" x2="780" y2="400" />
            <line x1="130" y1="130" x2="158" y2="158" />
            <line x1="670" y1="130" x2="642" y2="158" />
            <line x1="130" y1="670" x2="158" y2="642" />
            <line x1="670" y1="670" x2="642" y2="642" />
          </g>
          <g fontFamily="Cinzel Decorative, serif" fontSize="18" fill="rgba(240,208,96,.7)" stroke="none" textAnchor="middle">
            <text x="400" y="50">✦</text><text x="400" y="760">✦</text>
            <text x="50" y="408">✦</text><text x="750" y="408">✦</text>
            <text x="145" y="155">❖</text><text x="655" y="155">❖</text>
            <text x="145" y="655">❖</text><text x="655" y="655">❖</text>
          </g>
        </g>
      </svg>

      {/* 旋转符文内圈 */}
      <svg className="rune-circle rune-inner" viewBox="0 0 600 600" preserveAspectRatio="xMidYMid meet">
        <g stroke="rgba(127,232,248,.45)" fill="none" filter="url(#atmosGlowA)">
          <circle cx="300" cy="300" r="260" strokeWidth=".8" strokeDasharray="4 6" />
          <circle cx="300" cy="300" r="220" strokeWidth=".5" />
          <polygon points="300,60 538,456 115,216 485,216 62,456" strokeWidth=".6" opacity=".55" />
        </g>
      </svg>

      {/* 漂浮尘埃 */}
      <div className="dust" ref={dustRef} />
      {/* 余烬 */}
      <div className="embers" ref={embersRef} />
      {/* 暗角 */}
      <div className="vignette" />
    </div>
  )
}
