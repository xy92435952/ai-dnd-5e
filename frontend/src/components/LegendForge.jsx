/**
 * LegendForge — 角色铸造仪式
 * ================================
 * 源自 design bundle (legend-forge.jsx)，移植为 React 组件。
 * 角色创建完成并点击"开始冒险"时全屏触发：
 *   - 旋转符文环 + 24 道火花迸射
 *   - 职业色彩圆盘 + 职业符号浮现
 *   - 姓名镀金文字 + 副标题淡入
 *   - 配合 JuiceAudio.unlock() / crit() / turn() 三段式音效
 *   - 持续 ~4.2s 后自动消散
 *
 * 用法：
 *   <LegendForge open={showForge} name={char.name} cls="paladin"
 *                classZh="圣武士" raceZh="半精灵"
 *                onDone={() => { setShowForge(false); navigate(...) }} />
 */

import { useEffect } from 'react'
import { JuiceAudio } from '../juice'

const CREST_GLYPH = {
  paladin: '✦', fighter: '⚔', wizard: '✧', rogue: '❋', cleric: '☩',
  druid: '❦',   bard:    '♪', warlock: '◈', sorcerer: '⚡',
  barbarian: '⚒', monk: '◎', ranger: '➹',
}

const CLASS_COLOR = {
  paladin: '#f0d060', fighter: '#c46a48', wizard:  '#a070e8',
  rogue:   '#8a94aa', cleric:  '#f8e890', druid:   '#60a868',
  bard:    '#f090c8', warlock: '#7a4fc4', sorcerer:'#ff8a4c',
  barbarian:'#d66030', monk:   '#80e8c0', ranger:  '#58c070',
}

export default function LegendForge({
  open,
  name = '无名英雄',
  cls = 'paladin',
  classZh = '',
  raceZh = '',
  onDone,
  duration = 4200,
}) {
  useEffect(() => {
    if (!open) return

    // 三段音效：unlock（展开）→ crit（纹章绽放）→ turn（收束）
    try { JuiceAudio.unlock() } catch (e) {}
    const t1 = setTimeout(() => { try { JuiceAudio.crit() } catch (e) {} }, 600)
    const t2 = setTimeout(() => { try { JuiceAudio.turn() } catch (e) {} }, 1400)
    const t3 = setTimeout(() => { if (onDone) onDone() }, duration)

    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
      clearTimeout(t3)
    }
  }, [open, duration, onDone])

  if (!open) return null

  const glyph = CREST_GLYPH[cls] || '✦'
  const color = CLASS_COLOR[cls] || '#f0d060'

  // 24 道火花
  const sparks = Array.from({ length: 24 }).map((_, i) => ({
    a: i * 15,
    d: 160 + Math.random() * 80,
    delay: Math.random() * 0.4,
  }))

  return (
    <div className="legend-forge">
      <div className="inner">
        {/* 符文光环 */}
        <div className="rune-halo">
          <svg viewBox="0 0 400 400" width="380" height="380">
            <g fill="none" stroke="rgba(240,208,96,.6)" strokeWidth="1">
              <circle cx="200" cy="200" r="180" />
              <circle cx="200" cy="200" r="160" strokeDasharray="4 8" />
              <circle cx="200" cy="200" r="140" strokeDasharray="1 6" />
            </g>
            <g fill="rgba(240,208,96,.75)" fontFamily="serif" fontSize="16" textAnchor="middle">
              <text x="200" y="30">✦</text>
              <text x="200" y="376">✦</text>
              <text x="28" y="206">❖</text>
              <text x="372" y="206">❖</text>
            </g>
          </svg>
        </div>

        {/* 实心/虚线双环 */}
        <div className="sigil-ring" />
        <div className="sigil-ring inner-ring" />

        {/* 24 道火花 */}
        <div className="sparks">
          {sparks.map((s, i) => (
            <span
              key={i}
              style={{
                '--a': `${s.a}deg`,
                '--d': `${s.d}px`,
                animationDelay: `${s.delay}s`,
              }}
            />
          ))}
        </div>

        {/* 纹章圆盘 */}
        <div className="crest-slot">
          <div style={{
            width: 180,
            height: 180,
            borderRadius: '50%',
            display: 'grid',
            placeItems: 'center',
            background: `radial-gradient(circle at 35% 30%, ${color}, #1a0a02 75%)`,
            boxShadow: `0 0 40px ${color}, inset 0 0 30px rgba(0,0,0,.5), 0 0 0 3px rgba(240,208,96,.6), 0 0 0 6px rgba(26,14,4,.9), 0 0 0 8px rgba(240,208,96,.3)`,
          }}>
            <span style={{
              fontFamily: 'serif',
              fontSize: 96,
              color: '#fff8dd',
              textShadow: `0 0 20px ${color}, 0 4px 8px #000`,
              fontWeight: 900,
            }}>{glyph}</span>
          </div>
        </div>

        {/* 姓名 + 副标题 */}
        <div className="title">{name}</div>
        <div className="subtitle">
          {[raceZh, classZh, '传奇已诞生'].filter(Boolean).join(' · ')}
        </div>
      </div>
    </div>
  )
}
