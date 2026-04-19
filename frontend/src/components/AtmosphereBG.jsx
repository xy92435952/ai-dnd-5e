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

      {/* ═══ 旋转符文外圈 · 卢恩咒文环 + 十二宫 + 日月 ═══ */}
      <svg className="rune-circle rune-outer" viewBox="0 0 800 800" preserveAspectRatio="xMidYMid meet">
        <defs>
          <filter id="atmosGlowA" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          {/* 卢恩咒文跑道（外圈用 textPath 绕圆） */}
          <path id="atmosRunePath"
            d="M 400 400 m -355 0 a 355 355 0 1 1 710 0 a 355 355 0 1 1 -710 0" />
          {/* 内环反向咒文路径 */}
          <path id="atmosRunePathInner"
            d="M 400 400 m -275 0 a 275 275 0 1 0 550 0 a 275 275 0 1 0 -550 0" />
          {/* ═══ 蛇形符文带路径（n=12 波，基准 r=350，振幅 8） ═══
              用 Catmull-Rom 样条近似，72 个点 → 贝塞尔 */}
          <path id="atmosSerpentPath"
            d={(() => {
              const cx = 400, cy = 400, baseR = 345, amp = 10, N = 144
              const pts = []
              for (let i = 0; i < N; i++) {
                const t = (i / N) * Math.PI * 2
                const r = baseR + amp * Math.sin(12 * t)
                pts.push([cx + r * Math.cos(t), cy + r * Math.sin(t)])
              }
              // 闭合路径：M + L...L + Z（简化，不用曲线；因为 n=144 点密度已经足够看平滑）
              const parts = [`M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`]
              for (let i = 1; i < N; i++) parts.push(`L ${pts[i][0].toFixed(2)} ${pts[i][1].toFixed(2)}`)
              parts.push('Z')
              return parts.join(' ')
            })()} />
          {/* 蛇形内描边路径（稍小 8px，形成双线蛇身） */}
          <path id="atmosSerpentInnerPath"
            d={(() => {
              const cx = 400, cy = 400, baseR = 335, amp = 10, N = 144
              const pts = []
              for (let i = 0; i < N; i++) {
                const t = (i / N) * Math.PI * 2
                const r = baseR + amp * Math.sin(12 * t)
                pts.push([cx + r * Math.cos(t), cy + r * Math.sin(t)])
              }
              const parts = [`M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`]
              for (let i = 1; i < N; i++) parts.push(`L ${pts[i][0].toFixed(2)} ${pts[i][1].toFixed(2)}`)
              parts.push('Z')
              return parts.join(' ')
            })()} />
        </defs>

        <g filter="url(#atmosGlowA)" fill="none">
          {/* ── 最外双圈 ── */}
          <circle cx="400" cy="400" r="380" strokeWidth="1"  stroke="rgba(240,208,96,.55)" />
          <circle cx="400" cy="400" r="370" strokeWidth=".4" stroke="rgba(240,208,96,.3)" strokeDasharray="2 10" />

          {/* ═══ 蛇形符文带 — 双波浪描边 + 沿蛇身走的符文 ═══ */}
          {/* 外蛇身 */}
          <use href="#atmosSerpentPath"
               stroke="rgba(240,208,96,.5)" strokeWidth=".8" fill="none" />
          {/* 内蛇身（错位双线效果） */}
          <use href="#atmosSerpentInnerPath"
               stroke="rgba(240,208,96,.35)" strokeWidth=".5" fill="none" />

          {/* 蛇身之间的点状装饰（每波峰一颗星） */}
          <g fill="rgba(240,208,96,.7)" stroke="none">
            {Array.from({ length: 12 }).map((_, i) => {
              // 波峰出现在每个 30° 角度，对应 sin(12θ)=1 即 θ = (π/2 + 2kπ) / 12
              // 所以波峰角度 = 7.5° + k·30°
              const a = ((7.5 + i * 30) - 90) * Math.PI / 180
              const r = 350   // baseR + amp
              const x = 400 + r * Math.cos(a)
              const y = 400 + r * Math.sin(a)
              return <circle key={`wave-${i}`} cx={x} cy={y} r="1.6" />
            })}
          </g>

          {/* 沿蛇身路径放符文（较外圈更密更小，营造"咒文蛇"感觉） */}
          <text fontFamily="UnifrakturCook, Cinzel Decorative, serif"
                fontSize="12"
                fill="rgba(240,208,96,.65)"
                letterSpacing="3">
            <textPath href="#atmosSerpentPath" startOffset="0">
              ᚨᚾᛊᚢᛉ·ᛟᚦᚨᛚᚨ·ᛃᛖᚱᚨ·ᛇᚹᚨᛉ·ᛈᛖᚱᚦᚱᛟ·ᛊᛟᚹᛁᛚᛟ·ᛏᛁᚹᚨᛉ·ᛒᛖᚱᚲᚨᚾᚨ·ᛖᚺᚹᚨᛉ·ᛗᚨᚾᚾᚨᛉ·ᛚᚨᚷᚢᛉ·ᛟᚦᚨᛚᚨ
            </textPath>
          </text>

          {/* ── 原外圈卢恩咒文环（r=355） ── */}
          <text fontFamily="UnifrakturCook, Cinzel Decorative, serif"
                fontSize="22"
                fill="rgba(240,208,96,.7)"
                letterSpacing="8">
            <textPath href="#atmosRunePath" startOffset="0">
              ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛟᛞ · ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛟᛞ
            </textPath>
          </text>

          {/* ── 十二宫分隔刻度 ── */}
          <g stroke="rgba(240,208,96,.55)">
            <circle cx="400" cy="400" r="340" strokeWidth=".6" strokeDasharray="18 6 2 6" />
            {Array.from({ length: 12 }).map((_, i) => {
              const a = (i * 30 - 90) * Math.PI / 180
              const x1 = 400 + 340 * Math.cos(a)
              const y1 = 400 + 340 * Math.sin(a)
              const x2 = 400 + 360 * Math.cos(a)
              const y2 = 400 + 360 * Math.sin(a)
              return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} strokeWidth=".8" />
            })}
          </g>

          {/* ── 十二星座 · 点线图（天文相对位置简化版） ── */}
          {/* 每个星座占据一个 30°×30px 的槽位，中心放在 r=320 处
              星点坐标 [x, y] 为相对槽位中心的局部偏移（-15..+15）
              最后一个数组是星点间的连线对（索引对） */}
          <g>
            {(() => {
              const zodiacs = [
                // ♈ 白羊：三点折线（简化）
                { stars: [[-8,-4],[0,-8],[8,4]],         lines: [[0,1],[1,2]] },
                // ♉ 金牛：V 形 + 顶点
                { stars: [[-10,6],[0,-4],[10,6],[0,10]], lines: [[0,1],[1,2],[1,3]] },
                // ♊ 双子：平行双线
                { stars: [[-6,-8],[-6,8],[6,-8],[6,8]],  lines: [[0,1],[2,3]] },
                // ♋ 巨蟹：Y 字
                { stars: [[-8,-6],[0,0],[8,-6],[0,8]],   lines: [[0,1],[2,1],[1,3]] },
                // ♌ 狮子：镰刀型
                { stars: [[-8,6],[-4,-4],[4,-6],[8,0],[6,8]], lines: [[0,1],[1,2],[2,3],[3,4]] },
                // ♍ 处女：折线
                { stars: [[-10,-6],[-4,4],[4,-4],[10,6]], lines: [[0,1],[1,2],[2,3]] },
                // ♎ 天秤：三角 + 下垂
                { stars: [[-8,-2],[0,-8],[8,-2],[0,6]],  lines: [[0,1],[1,2],[0,3],[2,3]] },
                // ♏ 天蝎：S 曲线
                { stars: [[-10,-6],[-2,-4],[0,2],[6,4],[10,-2]], lines: [[0,1],[1,2],[2,3],[3,4]] },
                // ♐ 射手：弓箭
                { stars: [[-10,4],[-2,-2],[6,0],[10,-6]], lines: [[0,1],[1,2],[2,3]] },
                // ♑ 摩羯：三角
                { stars: [[-8,-4],[8,-4],[0,8]],          lines: [[0,1],[1,2],[0,2]] },
                // ♒ 水瓶：波浪
                { stars: [[-10,-4],[-4,4],[2,-4],[8,4]], lines: [[0,1],[1,2],[2,3]] },
                // ♓ 双鱼：V 字双线
                { stars: [[-10,-6],[-2,0],[-10,6],[10,-6],[2,0],[10,6]],
                  lines: [[0,1],[1,2],[3,4],[4,5],[1,4]] },
              ]
              return zodiacs.map((z, i) => {
                const a = (i * 30 - 90) * Math.PI / 180
                const cx = 400 + 320 * Math.cos(a)
                const cy = 400 + 320 * Math.sin(a)
                return (
                  <g key={i} stroke="rgba(240,208,96,.6)" strokeWidth=".7"
                     fill="rgba(240,208,96,.85)">
                    {z.lines.map(([a, b], li) => (
                      <line key={`L${li}`}
                        x1={cx + z.stars[a][0]} y1={cy + z.stars[a][1]}
                        x2={cx + z.stars[b][0]} y2={cy + z.stars[b][1]} />
                    ))}
                    {z.stars.map(([sx, sy], si) => (
                      <circle key={`S${si}`}
                        cx={cx + sx} cy={cy + sy} r="1.6" stroke="none" />
                    ))}
                  </g>
                )
              })
            })()}
          </g>

          {/* ── 中圈（连接星座与核心） ── */}
          <circle cx="400" cy="400" r="300" strokeWidth=".8" stroke="rgba(240,208,96,.45)" />
          <circle cx="400" cy="400" r="280" strokeWidth=".4" stroke="rgba(240,208,96,.25)" strokeDasharray="4 6" />

          {/* ── 日 / 月 / 星 · 四象装饰 ── */}
          <g fill="rgba(240,208,96,.75)" stroke="none"
             fontFamily="Cinzel Decorative, serif" fontSize="30" textAnchor="middle">
            <text x="400" y="108">☉</text>{/* 太阳（上） */}
            <text x="400" y="705">☽</text>{/* 月亮（下） */}
            <text x="95" y="408">✶</text>{/* 星（左） */}
            <text x="705" y="408">✶</text>{/* 星（右） */}
          </g>

          {/* ── 内环反向卢恩文字（制造层次感） ── */}
          <text fontFamily="UnifrakturCook, Cinzel Decorative, serif"
                fontSize="14"
                fill="rgba(240,208,96,.45)"
                letterSpacing="4">
            <textPath href="#atmosRunePathInner" startOffset="0">
              ᛞᛟᛜᛚᛗᛖᛒᛏᛊᛉᛈᛇᛃᛁᚾᚺᚹᚷᚲᚱᚨᚦᚢᚠ · ᛞᛟᛜᛚᛗᛖᛒᛏᛊᛉᛈᛇᛃᛁᚾᚺᚹᚷᚲᚱᚨᚦᚢᚠ
            </textPath>
          </text>
        </g>
      </svg>

      {/* ═══ 旋转符文内圈 · 六芒星法阵 + 内环星点 ═══ */}
      <svg className="rune-circle rune-inner" viewBox="0 0 600 600" preserveAspectRatio="xMidYMid meet">
        <g fill="none" filter="url(#atmosGlowA)">
          {/* 外层连接圈 */}
          <circle cx="300" cy="300" r="260" strokeWidth=".6" stroke="rgba(127,232,248,.35)" strokeDasharray="4 6" />

          {/* 六芒星所在的大圆（顶点圆） */}
          <circle cx="300" cy="300" r="240" strokeWidth=".5" stroke="rgba(127,232,248,.3)" />

          {/* 六芒星（大卫之星）
              上三角 90°/210°/330°：(300,60) (507.85,420) (92.15,420)
              下三角 270°/30°/150°：(300,540) (507.85,180) (92.15,180)
          */}
          <polygon points="300,60 507.85,420 92.15,420"
                   strokeWidth=".9" stroke="rgba(127,232,248,.55)" opacity=".8" />
          <polygon points="300,540 507.85,180 92.15,180"
                   strokeWidth=".9" stroke="rgba(127,232,248,.55)" opacity=".8" />

          {/* 六个顶点处的小五角星装饰（标记六芒星顶点） */}
          <g fill="rgba(127,232,248,.8)" stroke="none"
             fontFamily="Cinzel Decorative, serif" fontSize="14" textAnchor="middle">
            <text x="300" y="66">✦</text>
            <text x="507.85" y="426">✦</text>
            <text x="92.15" y="426">✦</text>
            <text x="300" y="546">✦</text>
            <text x="507.85" y="186">✦</text>
            <text x="92.15" y="186">✦</text>
          </g>

          {/* 六边形内环（连接六芒星内部 6 个交点，半径 = 外顶点 / √3 ≈ 138.56）
              顶点在 90° / 30° / 330° / 270° / 210° / 150°：
                90°  (上) : (300, 161.44)
                30°  (右上): (420, 230.72)
                330° (右下): (420, 369.28)
                270° (下) : (300, 438.56)
                210° (左下): (180, 369.28)
                150° (左上): (180, 230.72)
          */}
          <polygon points="300,161.44 420,230.72 420,369.28 300,438.56 180,369.28 180,230.72"
                   strokeWidth=".6" stroke="rgba(127,232,248,.45)" opacity=".7" />

          {/* ═══ 内核区域（r=0 ~ r=80）— 多层次光环 ═══ */}

          {/* 光晕渐变（从中心向外的柔光） */}
          <defs>
            <radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(255,240,180,.5)" />
              <stop offset="40%" stopColor="rgba(127,232,248,.25)" />
              <stop offset="80%" stopColor="rgba(127,232,248,.08)" />
              <stop offset="100%" stopColor="rgba(127,232,248,0)" />
            </radialGradient>
          </defs>
          <circle cx="300" cy="300" r="80" fill="url(#coreGlow)" stroke="none">
            <animate attributeName="r" values="70;82;70" dur="4s" repeatCount="indefinite" />
          </circle>

          {/* 外壳圆 + 刻度圆（保留视觉边界） */}
          <circle cx="300" cy="300" r="80" strokeWidth=".6" stroke="rgba(127,232,248,.4)" />
          <circle cx="300" cy="300" r="60" strokeWidth=".4" stroke="rgba(127,232,248,.3)" strokeDasharray="2 4" />

          {/* ── 八方放射光束（从 r=18 到 r=70） ── */}
          <g stroke="rgba(127,232,248,.55)" strokeWidth="1" strokeLinecap="round">
            {Array.from({ length: 8 }).map((_, i) => {
              const a = (i * 45) * Math.PI / 180
              const x1 = 300 + 18 * Math.cos(a)
              const y1 = 300 + 18 * Math.sin(a)
              const x2 = 300 + 70 * Math.cos(a)
              const y2 = 300 + 70 * Math.sin(a)
              return (
                <line key={`ray-${i}`} x1={x1} y1={y1} x2={x2} y2={y2}>
                  <animate attributeName="opacity" values="0.3;0.9;0.3" dur="3s"
                           begin={`${i * 0.15}s`} repeatCount="indefinite" />
                </line>
              )
            })}
          </g>

          {/* ── 卢恩咒文小圆环（r=45 处绕一圈） ── */}
          <defs>
            <path id="atmosCoreRunePath"
              d="M 300 300 m -45 0 a 45 45 0 1 1 90 0 a 45 45 0 1 1 -90 0" />
          </defs>
          <text fontFamily="UnifrakturCook, Cinzel Decorative, serif"
                fontSize="10"
                fill="rgba(127,232,248,.7)"
                letterSpacing="2">
            <textPath href="#atmosCoreRunePath" startOffset="0">
              ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛟᛞ
            </textPath>
          </text>

          {/* ── 小五芒星内核装饰（r=25 圆上 5 个点） ── */}
          <g fill="rgba(127,232,248,.7)" stroke="none">
            {Array.from({ length: 5 }).map((_, i) => {
              const a = (i * 72 - 90) * Math.PI / 180
              const x = 300 + 25 * Math.cos(a)
              const y = 300 + 25 * Math.sin(a)
              return <circle key={`pent-${i}`} cx={x} cy={y} r="1.2" />
            })}
          </g>
          {/* 五芒星连线（第 i 连 i+2 形成星形） */}
          <g stroke="rgba(127,232,248,.3)" strokeWidth=".4" fill="none">
            {(() => {
              const pts = Array.from({ length: 5 }).map((_, i) => {
                const a = (i * 72 - 90) * Math.PI / 180
                return [300 + 25 * Math.cos(a), 300 + 25 * Math.sin(a)]
              })
              const lines = []
              for (let i = 0; i < 5; i++) {
                const [x1, y1] = pts[i]
                const [x2, y2] = pts[(i + 2) % 5]
                lines.push(<line key={`pl-${i}`} x1={x1} y1={y1} x2={x2} y2={y2} />)
              }
              return lines
            })()}
          </g>

          {/* ── 脉动光环（扩散波纹） ── */}
          <circle cx="300" cy="300" r="10" fill="none"
                  stroke="rgba(127,232,248,.8)" strokeWidth="1">
            <animate attributeName="r" values="10;70;10" dur="4s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="1;0;1" dur="4s" repeatCount="indefinite" />
          </circle>
          <circle cx="300" cy="300" r="10" fill="none"
                  stroke="rgba(127,232,248,.6)" strokeWidth=".8">
            <animate attributeName="r" values="10;70;10" dur="4s" begin="2s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="1;0;1" dur="4s" begin="2s" repeatCount="indefinite" />
          </circle>

          {/* ── 中心能量脉动点 + 白光核 ── */}
          <circle cx="300" cy="300" r="6" fill="rgba(127,232,248,.85)" stroke="none">
            <animate attributeName="r" values="4;8;4" dur="3s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" repeatCount="indefinite" />
          </circle>
          <circle cx="300" cy="300" r="2" fill="rgba(255,255,255,.95)" stroke="none">
            <animate attributeName="r" values="1.5;3;1.5" dur="3s" repeatCount="indefinite" />
          </circle>
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
