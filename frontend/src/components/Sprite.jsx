/**
 * Sprite — 像素 token 查表组件（v0.10.3 生产版）
 *
 * 工作流程：
 *   1. 读 public/sprites/_INDEX.json 获取 kind → {size, fallback} 映射
 *   2. 尝试 <img src="/sprites/{kind}.png" />（v0.10.3 已为 39 个 kind 生成 PNG）
 *   3. img onerror 或 kind 未在索引 → 回落到 <PixelSprite> 内联 SVG
 *
 * 体型缩放（D&D 5e）：
 *   S(Small) = 0.75x / M(Medium默认) = 1.0x / L(Large) = 1.5x / H(Huge) = 2x / G(Gargantuan) = 3x
 *
 * Props:
 *   kind     - sprite key（如 'paladin' / 'goblin' / 'young_dragon_red'）
 *   size     - 基准像素（未考虑体型缩放时的宽度），默认 44
 *   dead     - true 显示灰度
 *   dim      - true 显示暗化（对非当前回合角色）
 *   overrideSize - 显式覆盖体型（S/M/L/H/G）
 */
import { useEffect, useState } from 'react'
import PixelSprite from './PixelSprite'

let CACHED_INDEX = null
let INDEX_PROMISE = null

async function loadIndex() {
  if (CACHED_INDEX) return CACHED_INDEX
  if (INDEX_PROMISE) return INDEX_PROMISE
  INDEX_PROMISE = fetch('/sprites/_INDEX.json')
    .then((r) => r.ok ? r.json() : null)
    .then((data) => {
      CACHED_INDEX = data || { sprites: {}, fallbacks: {}, sizes: { S: 0.75, M: 1, L: 1.5, H: 2 } }
      return CACHED_INDEX
    })
    .catch(() => {
      CACHED_INDEX = { sprites: {}, fallbacks: {}, sizes: { S: 0.75, M: 1, L: 1.5, H: 2 } }
      return CACHED_INDEX
    })
  return INDEX_PROMISE
}

export default function Sprite({ kind = 'paladin', size = 44, dead = false, dim = false, overrideSize }) {
  const [index, setIndex] = useState(CACHED_INDEX)
  const [imgFailed, setImgFailed] = useState(false)

  useEffect(() => {
    if (!CACHED_INDEX) loadIndex().then(setIndex)
  }, [])

  useEffect(() => { setImgFailed(false) }, [kind])

  const entry = index?.sprites?.[kind]
  const fallbackKind = entry?.fallback || index?.fallbacks?.[entry?.kind] || index?.fallbacks?.default || 'paladin'

  // 体型缩放：优先 prop 覆盖，其次 entry.size，最后默认 M(1.0)
  const sizeCode = overrideSize || entry?.size || 'M'
  const sizes = index?.sizes || { S: 0.75, M: 1, L: 1.5, H: 2, G: 3 }
  const scale = sizes[sizeCode] || 1

  const finalWidth = Math.round(size * scale)
  const finalHeight = Math.round(size * 1.5 * scale)

  // 优先尝试 PNG（当索引加载完成且未失败时）
  if (index && !imgFailed) {
    return (
      <img
        src={`/sprites/${kind}.png`}
        width={finalWidth}
        height={finalHeight}
        alt=""
        style={{
          imageRendering: 'pixelated',
          filter: dead ? 'grayscale(1) brightness(.4)'
                : dim  ? 'saturate(.6) brightness(.8)'
                : 'drop-shadow(0 2px 0 rgba(0,0,0,.8))',
          pointerEvents: 'none',
          display: 'block',
        }}
        onError={() => setImgFailed(true)}
      />
    )
  }

  // 回落到内联 SVG（按 finalWidth 渲染以保持缩放一致）
  return <PixelSprite kind={fallbackKind} size={finalWidth} dead={dead} dim={dim} />
}
