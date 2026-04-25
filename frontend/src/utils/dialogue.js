/**
 * utils/dialogue.js — DM 叙事 / 队友反应文本拆段工具。
 *
 * 三个纯函数都从 Adventure.jsx 抽出来，方便单测、复用、不污染主组件。
 *
 * 设计要点：
 *   - splitDmNarrative：默认整段作 DM 旁白，仅在首行有明显 NPC 头格式时才拆出 NPC 段
 *   - splitCompanionReactions：speaker 识别用方括号 `[名字]` 严格匹配，
 *     裸名字必须在 companions 白名单里 —— 防止 "低声从牙缝里挤出一句："
 *     整段被当 speaker
 *   - extractNarrative：兼容旧版 LLM 把 JSON 整块塞 log 的情况，回退抽 narrative 字段
 */

/**
 * DM 叙述：整段作为一条气泡（不做句级切分）。
 * 若首行明显是 NPC 开场白，则抽出作为独立 NPC 气泡；其余归 DM 旁白。
 *
 * @param {string} narrative
 * @returns {Array<{role: 'dm'|'npc', speaker: string, text: string}>}
 */
export function splitDmNarrative(narrative) {
  if (!narrative) return []
  const text = String(narrative).trim()
  if (!text) return []

  const firstLine = text.split(/\n/)[0].trim()
  const npcHeadMatch =
    firstLine.match(/^[「"]([一-鿿·A-Za-z]{2,16})[」"][说曰道][:：]/) ||
    firstLine.match(/^\[([^\]]{1,16})\][:：]/) ||
    firstLine.match(/^([一-鿿·A-Za-z]{2,16})(?:说|道|云|回答|笑道|冷冷道|低声说)[：:]/)

  if (npcHeadMatch) {
    const speaker = npcHeadMatch[1].trim()
    const splitIdx = text.indexOf('\n')
    if (splitIdx > 0) {
      const npcLine = text.slice(0, splitIdx).trim()
      const rest = text.slice(splitIdx + 1).trim()
      const segs = [{ role: 'npc', speaker, text: npcLine }]
      if (rest) segs.push({ role: 'dm', speaker: 'DM', text: rest })
      return segs
    }
  }

  // 默认：整段一条 DM 气泡
  return [{ role: 'dm', speaker: 'DM', text }]
}

/**
 * companion_reactions 文本拆段：按人分组合并，同一人的话合成一条气泡。
 * 兼容格式："[名字]: 台词" / "名字: 台词"（裸名字必须在 companionList 白名单）/ 换行分隔。
 *
 * @param {string} content
 * @param {Array<{name?: string}>} companionList
 * @returns {Array<{role: 'companion', speaker: string, text: string}>}
 */
export function splitCompanionReactions(content, companionList = []) {
  if (!content) return []
  const text = String(content).trim()
  if (!text) return []

  // ——— speaker 识别 ———
  // 原正则 `([一-鿿·A-Za-z]{2,16})[:：]` 太宽松：
  //   "低声从牙缝里挤出一句：" 整坨被当 speaker（后面有冒号就能匹配）
  // 修法：无方括号的 candidate 必须在 companions 白名单里才接受；
  //      方括号 [名字] 保持宽松（玩家/模组显式标注）
  const namePattern = /(?:\[([^\]]{1,16})\]|([一-鿿·A-Za-z]{2,16}))[:：]\s*/g
  const companionNames = (companionList || []).map(c => c?.name).filter(Boolean)
  const isKnownCompanion = (candidate) => companionNames.some(n =>
    n === candidate || n.includes(candidate) || candidate.includes(n))

  const matches = []
  let m
  while ((m = namePattern.exec(text)) !== null) {
    const candidate = (m[1] || m[2]).trim()
    // 方括号捕获：直接采用（模组/玩家显式标注）
    // 无方括号：必须命中队友白名单，否则跳过
    if (m[1] || isKnownCompanion(candidate)) {
      matches.push({ idx: m.index, nameEnd: m.index + m[0].length, speaker: candidate })
    }
  }

  const raw = []
  if (matches.length > 0) {
    for (let i = 0; i < matches.length; i++) {
      const cur = matches[i]
      const nextStart = i + 1 < matches.length ? matches[i + 1].idx : text.length
      const say = text.slice(cur.nameEnd, nextStart).trim()
      if (say) raw.push({ speaker: cur.speaker, text: say })
    }
  } else {
    // 没匹配到任何名字 → 用队伍里第一个队友兜底（至少显示真实名字而不是动作第一字）
    const fallbackSpeaker = companionNames[0] || '队友'
    text.split(/\n+/).filter(Boolean).forEach(line => {
      raw.push({ speaker: fallbackSpeaker, text: line.trim() })
    })
  }

  // 按人分组合并（保持首次出现顺序）
  const order = []
  const group = new Map()
  for (const r of raw) {
    if (!group.has(r.speaker)) {
      order.push(r.speaker)
      group.set(r.speaker, [])
    }
    group.get(r.speaker).push(r.text)
  }

  return order.map(sp => ({
    speaker: sp,
    text: group.get(sp).join('  '),
    role: 'companion',
  }))
}

/**
 * 从 GameLog.content 中抽出真正的叙事文本。
 * 历史版本里偶尔会有整块 JSON / Markdown 代码块塞进来，这里做兼容兜底。
 *
 * @param {string} content
 * @returns {string}
 */
export function extractNarrative(content) {
  if (!content) return ''
  const trimmed = String(content).trim()
  if (trimmed.startsWith('```') || trimmed.startsWith('{')) {
    try {
      const jsonStr = trimmed
        .replace(/^```(?:json)?\s*\n?/m, '')
        .replace(/\n?\s*```\s*$/m, '')
        .trim()
      const parsed = JSON.parse(jsonStr)
      if (parsed.narrative) return parsed.narrative
      if (parsed.content) return parsed.content
    } catch {
      const m = trimmed.match(/"narrative"\s*:\s*"((?:[^"\\]|\\.)*)"/s)
      if (m) return m[1].replace(/\\n/g, '\n').replace(/\\"/g, '"')
    }
  }
  return trimmed
}
