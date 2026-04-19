/**
 * 战斗工具函数（纯前端计算）
 * - 切比雪夫距离
 * - 可达格集合（BFS + 墙体限制）
 * - 简单 A* 路径（用于路径预览）
 */

export function chebyshev(a, b) {
  return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y))
}

export function keyOf(x, y) { return `${x}_${y}` }

/**
 * 计算从 pos 出发在 movementLeft 步内可达的所有格子（不含起点）。
 * gridData: {x_y: "wall"|"hazard"|"difficult"}
 * 墙体不可进入，危险地形可进入但花 2 步。
 */
export function reachableCells(pos, movementLeft, gridData, gridW, gridH, blockedUnits = new Set()) {
  if (!pos || movementLeft <= 0) return new Set()
  const walls = new Set()
  const difficult = new Set()
  for (const [k, v] of Object.entries(gridData || {})) {
    if (v === 'wall') walls.add(k)
    else if (v === 'difficult' || v === 'hazard') difficult.add(k)
  }

  const dist = new Map()
  const startKey = keyOf(pos.x, pos.y)
  dist.set(startKey, 0)
  const queue = [{ x: pos.x, y: pos.y, cost: 0 }]

  while (queue.length) {
    const cur = queue.shift()
    const dirs = [
      [-1,-1],[0,-1],[1,-1],
      [-1, 0],       [1, 0],
      [-1, 1],[0, 1],[1, 1],
    ]
    for (const [dx, dy] of dirs) {
      const nx = cur.x + dx, ny = cur.y + dy
      if (nx < 0 || ny < 0 || nx >= gridW || ny >= gridH) continue
      const k = keyOf(nx, ny)
      if (walls.has(k)) continue
      if (blockedUnits.has(k)) continue
      const step = difficult.has(k) ? 2 : 1
      const newCost = cur.cost + step
      if (newCost > movementLeft) continue
      if (dist.has(k) && dist.get(k) <= newCost) continue
      dist.set(k, newCost)
      queue.push({ x: nx, y: ny, cost: newCost })
    }
  }

  dist.delete(startKey)
  return new Set(dist.keys())
}

/**
 * 简单 A* 寻路（八方向 Chebyshev）
 * 返回路径（含起点和终点），到达不了返回 []
 */
export function findPath(start, goal, gridData, gridW, gridH, blockedUnits = new Set()) {
  const walls = new Set()
  const difficult = new Set()
  for (const [k, v] of Object.entries(gridData || {})) {
    if (v === 'wall') walls.add(k)
    else if (v === 'difficult' || v === 'hazard') difficult.add(k)
  }

  const startKey = keyOf(start.x, start.y)
  const goalKey = keyOf(goal.x, goal.y)
  if (walls.has(goalKey)) return []

  const h = (a, b) => Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y))
  const open = new Map()
  const closed = new Set()
  const cameFrom = new Map()
  open.set(startKey, { x: start.x, y: start.y, g: 0, f: h(start, goal) })

  while (open.size) {
    // 取 f 最小
    let curKey = null, curNode = null
    for (const [k, n] of open) {
      if (!curNode || n.f < curNode.f) { curKey = k; curNode = n }
    }
    if (curKey === goalKey) {
      const path = []
      let k = curKey
      while (k) {
        const [x, y] = k.split('_').map(Number)
        path.unshift({ x, y })
        k = cameFrom.get(k)
      }
      return path
    }
    open.delete(curKey)
    closed.add(curKey)

    const dirs = [
      [-1,-1],[0,-1],[1,-1],
      [-1, 0],       [1, 0],
      [-1, 1],[0, 1],[1, 1],
    ]
    for (const [dx, dy] of dirs) {
      const nx = curNode.x + dx, ny = curNode.y + dy
      if (nx < 0 || ny < 0 || nx >= gridW || ny >= gridH) continue
      const nk = keyOf(nx, ny)
      if (walls.has(nk) || closed.has(nk)) continue
      if (blockedUnits.has(nk) && nk !== goalKey) continue
      const step = difficult.has(nk) ? 2 : 1
      const tentative = curNode.g + step
      const existing = open.get(nk)
      if (existing && existing.g <= tentative) continue
      cameFrom.set(nk, curKey)
      open.set(nk, { x: nx, y: ny, g: tentative, f: tentative + h({x:nx,y:ny}, goal) })
    }
  }
  return []
}

/**
 * 相机窗口：基于锚点角色居中，返回可渲染的格子范围（超出边界时夹紧）
 */
export function cameraWindow(anchor, viewW, viewH, gridW, gridH) {
  let x0 = Math.floor((anchor?.x ?? gridW / 2) - viewW / 2)
  let y0 = Math.floor((anchor?.y ?? gridH / 2) - viewH / 2)
  x0 = Math.max(0, Math.min(gridW - viewW, x0))
  y0 = Math.max(0, Math.min(gridH - viewH, y0))
  return { x0, y0, x1: x0 + viewW, y1: y0 + viewH }
}
