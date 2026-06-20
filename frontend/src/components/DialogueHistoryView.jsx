/**
 * DialogueHistoryView — 对话史册（历史视图）
 * 设计来源：design v3 scene-adventure.jsx 的 DialogueHistoryView
 *
 * 功能：
 * - 左侧章节目录（基于 campaign_state.completed_scenes + current_scene）
 * - 左侧筛选器（全部 / 仅 NPC / 仅玩家 / 仅检定 / 仅旁白）
 * - 右侧滚动对话流（自动滚到底部，离底时显示"跳至最新"按钮）
 * - 末尾"当前 · 对话进行中"分隔符
 *
 * 输入：session（含 logs + campaign_state + current_scene + module_name）
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { renderLightMarkdown } from '../utils/markdown'
import { formatAdventureDiceLog } from '../utils/adventureDiceLog'

/**
 * 把后端 GameLog 转成史册条目。
 * role: dm/player/companion_{name}/system/dice
 * log_type: narrative/combat/dice/companion/system
 */
function hasDiceResult(log) {
  return log?.dice_result !== null && log?.dice_result !== undefined
}

function diceRows(diceResult) {
  if (Array.isArray(diceResult)) {
    return diceResult.filter(row => row && typeof row === 'object' && !Array.isArray(row))
  }
  if (diceResult && typeof diceResult === 'object') return [diceResult]
  return []
}

function diceRowToHistoryEntry(dice, fallbackContent = '') {
  if (!dice || typeof dice !== 'object' || Array.isArray(dice)) {
    return {
      kind: 'roll',
      label: '检定',
      dc: null,
      against: null,
      roll: null,
      mod: null,
      total: null,
      result: 'neutral',
      rawText: fallbackContent || '骰子结果',
    }
  }

  const reactionText = (dice.kind === 'reaction' || dice.reaction_type)
    ? formatAdventureDiceLog(dice)
    : null
  const outcome = String(dice.outcome || '')
  const roll = dice.d20 ?? dice.raw ?? dice.roll ?? null
  const modifier = dice.modifier === null || dice.modifier === undefined ? null : Number(dice.modifier)

  return {
    kind: 'roll',
    label: dice.label || dice.skill || dice.check_type || dice.spell_name || (reactionText ? 'Reaction' : '检定'),
    dc: dice.dc ?? null,
    against: dice.against ?? (dice.target_ac != null ? `AC ${dice.target_ac}` : null),
    roll,
    mod: Number.isFinite(modifier) ? modifier : null,
    total: dice.total ?? (dice.d20 != null && dice.modifier != null ? dice.d20 + dice.modifier : null),
    result: (dice.success === true || dice.hit === true || outcome === '成功' || /成功|通过/.test(outcome)) ? 'success' :
            (dice.success === false || dice.hit === false || outcome === '失败' || /失败|未通过/.test(outcome)) ? 'failure' :
            'neutral',
    rawText: reactionText || (!roll && fallbackContent ? fallbackContent : null),
  }
}

function appendDiceEntries(entries, diceResult, fallbackContent = '') {
  const rows = diceRows(diceResult)
  if (!rows.length) {
    if (fallbackContent) entries.push(diceRowToHistoryEntry(null, fallbackContent))
    return
  }
  rows.forEach(row => entries.push(diceRowToHistoryEntry(row)))
}

export function logsToHistoryEntries(logs = [], player) {
  const entries = []
  for (const l of logs) {
    if (!l) continue
    const role = l.role || ''
    const logType = l.log_type || ''
    const content = String(l.content || '').trim()
    const dicePayload = hasDiceResult(l)
    if (!content && !dicePayload) continue

    // 检定 / 骰子结果
    if (role === 'dice' || logType === 'dice') {
      appendDiceEntries(entries, l.dice_result, content)
      continue
    }

    if (content) {
      // DM 旁白 / 场景
      if (role === 'dm') {
        // 清理可能的 JSON 包装
        const clean = stripJsonWrapper(content)
        entries.push({ kind: 'narration', txt: clean })
      } else if (role === 'player') {
        // 玩家
        entries.push({
          kind: 'player',
          speaker: player?.name || '我',
          letter: (player?.name || '我').slice(0, 1),
          txt: content,
        })
      } else if (role === 'companion' || role.startsWith('companion_')) {
        // 队友（companion 或 companion_{name}）
        const maybeName = role.startsWith('companion_')
          ? role.slice('companion_'.length)
          : l.speaker || l.companion_speaker || '队友'
        entries.push({
          kind: 'companion',
          speaker: maybeName,
          letter: maybeName.slice(0, 1),
          txt: content,
        })
      } else if (role === 'system' || logType === 'system') {
        // system 显示为分隔符
        entries.push({ kind: 'system', txt: content })
      } else {
        // 兜底：作为旁白
        entries.push({ kind: 'narration', txt: content })
      }
    }

    if (dicePayload) appendDiceEntries(entries, l.dice_result)
  }
  return entries
}

function stripJsonWrapper(text) {
  const t = text.trim()
  if (t.startsWith('```') || t.startsWith('{')) {
    try {
      const s = t.replace(/^```(?:json)?\s*\n?/m, '').replace(/\n?\s*```\s*$/m, '').trim()
      const obj = JSON.parse(s)
      return obj.narrative || obj.content || t
    } catch {
      const m = t.match(/"narrative"\s*:\s*"((?:[^"\\]|\\.)*)"/s)
      if (m) return m[1].replace(/\\n/g, '\n').replace(/\\"/g, '"')
    }
  }
  return text
}

export default function DialogueHistoryView({ session, player, onBack }) {
  const scrollRef = useRef(null)
  const [atBottom, setAtBottom] = useState(true)
  const [filter, setFilter] = useState('all')     // all / npc / player / roll / narr

  // 转换 logs → 条目
  const allEntries = useMemo(() => logsToHistoryEntries(session?.logs || [], player), [session, player])

  // 章节：campaign_state.completed_scenes + current_scene（最后一个）
  const chapters = useMemo(() => {
    const completed = session?.campaign_state?.completed_scenes || []
    const result = completed.map((title, i) => ({
      i: toRoman(i + 1), title, cur: false, turns: null,
    }))
    if (session?.current_scene) {
      // 取 current_scene 首行作章节名（避免整段开场白作标题）
      const curName = String(session.current_scene).split(/[\n。]/)[0].slice(0, 20) || '当前'
      result.push({ i: toRoman(result.length + 1), title: curName, cur: true, turns: null })
    }
    return result.length ? result : [{ i: 'I', title: '当前', cur: true }]
  }, [session])

  // 筛选
  const filteredEntries = useMemo(() => {
    if (filter === 'all') return allEntries
    const keepKinds = {
      npc: ['companion', 'npc'],
      player: ['player'],
      roll: ['roll'],
      narr: ['narration', 'system'],
    }[filter] || []
    return allEntries.filter(e => keepKinds.includes(e.kind))
  }, [allEntries, filter])

  // 筛选计数
  const counts = useMemo(() => {
    const c = { all: allEntries.length, npc: 0, player: 0, roll: 0, narr: 0 }
    for (const e of allEntries) {
      if (e.kind === 'companion' || e.kind === 'npc') c.npc++
      else if (e.kind === 'player') c.player++
      else if (e.kind === 'roll') c.roll++
      else if (e.kind === 'narration' || e.kind === 'system') c.narr++
    }
    return c
  }, [allEntries])

  // 打开时滚到底
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [filter])

  const handleScroll = (e) => {
    const el = e.target
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 60)
  }

  const scrollToLatest = () => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }
  const filterOptions = [
    { k: 'all',    n: '全部',       c: counts.all },
    { k: 'npc',    n: '仅 NPC 对话', c: counts.npc },
    { k: 'player', n: '仅玩家发言',   c: counts.player },
    { k: 'roll',   n: '仅检定结果',   c: counts.roll },
    { k: 'narr',   n: '仅旁白',      c: counts.narr },
  ]

  return (
    <div className="dialogue-history-view">
      {/* 顶部返回条 */}
      <div className="dialogue-history-topbar">
        <button
          className="btn-ghost dialogue-history-back"
          onClick={onBack}
          aria-label="返回对话"
        >
          ◀ 返回对话
        </button>
        <div className="dialogue-history-title">
          <div>DIALOGUE LOG</div>
          <h2 className="display-title">
            对话史册 · {session?.module_name || '冒险'}
          </h2>
        </div>
        <div className="dialogue-history-topbar-spacer" />
      </div>

      {/* 章节目录 + 内容 */}
      <div className="dialogue-history-layout">

        {/* 左 · 章节目录 + 筛选 */}
        <aside className="dialogue-history-sidebar" aria-label="对话史册导航">
          <div className="history-section-label">章节目录</div>

          {chapters.map((ch, i) => (
            <div key={i} className={`chapter-nav ${ch.cur ? 'current' : ''}`}>
              <div className="chapter-nav-index-row">
                <span>{ch.i}</span>
              </div>
              <div className="chapter-nav-title">{ch.title}</div>
            </div>
          ))}

          <div className="history-section-label filter">筛选</div>

          <div className="history-filter-list" role="group" aria-label="筛选对话记录">
            {filterOptions.map(f => (
              <button
              key={f.k}
              className={`filter-pill ${filter === f.k ? 'active' : ''}`}
              onClick={() => setFilter(f.k)}
              aria-pressed={filter === f.k}
            >
              <span>{f.n}</span>
              <span className="count">{f.c}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* 右 · 滚动流 */}
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="adv-history-scroll"
          aria-label="对话记录"
        >
          <div className="dialogue-history-status" role="status" aria-live="polite">
            <span>{filterOptions.find(item => item.k === filter)?.n || '全部'}</span>
            <strong>{filteredEntries.length}</strong>
            <b>条记录</b>
          </div>
          <div className="dialogue-history">
            {/* 首章分隔 */}
            <div className="hist-divider">
              <span className="ornament">❦</span>
              <span className="title">{session?.save_name || '冒险日志'}</span>
              <span className="time">{session?.module_name || '—'}</span>
            </div>

            {filteredEntries.length === 0 && (
              <p className="dialogue-history-empty">
                {filter === 'all' ? '还没有任何对话记录' : '当前筛选下没有匹配的记录'}
              </p>
            )}

            {filteredEntries.map((h, i) => {
              if (h.kind === 'narration' || h.kind === 'system') {
                return (
                  <p key={i} className="hist-narration">
                    {h.kind === 'system'
                      ? `· ${h.txt} ·`
                      : renderLightMarkdown(h.txt, 'var(--amber)')}
                  </p>
                )
              }
              if (h.kind === 'npc' || h.kind === 'companion') {
                return (
                  <div key={i} className="hist-bubble npc">
                    <div className="hist-avatar npc" data-cls={h.cls || 'commoner'}>{h.letter}</div>
                    <div className="hist-body">
                      <div className="hist-name">❖ {h.speaker}</div>
                      <p className={`hist-line ${h.emphasis ? 'emphasis' : ''}`}>
                        {renderLightMarkdown(h.txt, 'var(--amber)')}
                      </p>
                    </div>
                  </div>
                )
              }
              if (h.kind === 'player') {
                return (
                  <div key={i} className="hist-bubble player">
                    <div className="hist-body">
                      <div className="hist-name">◈ {h.speaker}</div>
                      {h.choice && <div className="hist-choice-tag">{h.choice}</div>}
                      <p className="hist-line">{renderLightMarkdown(h.txt, '#fff8dd')}</p>
                    </div>
                    <div className="hist-avatar player">{h.letter}</div>
                  </div>
                )
              }
              if (h.kind === 'roll') {
                const checkText = h.rawText || `${h.label}${h.dc != null ? ` · DC ${h.dc}` : h.against ? ` · ${h.against}` : ''}`
                return (
                  <div key={i} className={`hist-roll ${h.result}`}>
                    <span className="die">🎲</span>
                    <span className={`check ${h.rawText ? 'raw' : ''}`}>{checkText}</span>
                    {h.roll != null && (
                      <span className="calc">
                        {h.roll}
                        {h.mod != null ? `${h.mod >= 0 ? '+' : ''}${h.mod}` : ''}
                        {h.total != null ? ` = ${h.total}` : ''}
                      </span>
                    )}
                    {h.result !== 'neutral' && (
                      <span className={`outcome ${h.result}`}>
                        {h.result === 'success' ? '✓ 通过' : '✗ 失败'}
                      </span>
                    )}
                  </div>
                )
              }
              return null
            })}

            {/* 当前 · 对话进行中 */}
            {filter === 'all' && (
              <>
                <div className="hist-current-divider hist-current-divider-spaced">
                  <span className="dot" />
                  <span className="label">当前 · 对话进行中</span>
                  <span className="dot" />
                </div>
                <div className="dialogue-history-current-note">
                  等待你的回应…… 点击"返回对话"继续。
                </div>
              </>
            )}
          </div>

          {/* 浮动"跳至最新" */}
          {!atBottom && (
            <button onClick={scrollToLatest} className="scroll-to-latest">
              ▼ 跳至最新
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function toRoman(n) {
  const map = [['M',1000],['CM',900],['D',500],['CD',400],['C',100],['XC',90],['L',50],['XL',40],['X',10],['IX',9],['V',5],['IV',4],['I',1]]
  let s = ''
  for (const [r, v] of map) { while (n >= v) { s += r; n -= v } }
  return s
}
