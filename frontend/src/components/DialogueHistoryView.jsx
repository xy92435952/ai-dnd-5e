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

/**
 * 把后端 GameLog 转成史册条目。
 * role: dm/player/companion_{name}/system/dice
 * log_type: narrative/combat/dice/companion/system
 */
function logsToHistoryEntries(logs = [], player) {
  const entries = []
  for (const l of logs) {
    if (!l) continue
    const role = l.role || ''
    const logType = l.log_type || ''
    const content = String(l.content || '').trim()
    if (!content) continue

    // 检定 / 骰子结果
    if (role === 'dice' || logType === 'dice') {
      const d = l.dice_result || {}
      entries.push({
        kind: 'roll',
        label: d.label || d.skill || d.check_type || '检定',
        dc: d.dc ?? d.against ?? null,
        roll: d.d20 ?? d.raw ?? d.roll ?? null,
        mod: d.modifier ?? 0,
        total: d.total ?? (d.d20 != null && d.modifier != null ? d.d20 + d.modifier : null),
        result: (d.success === true || d.outcome === '成功' || /成功|通过/.test(d.outcome || '')) ? 'success' :
                (d.success === false || d.outcome === '失败' || /失败|未通过/.test(d.outcome || '')) ? 'failure' :
                'neutral',
        rawText: content,
      })
      continue
    }

    // DM 旁白 / 场景
    if (role === 'dm') {
      // 清理可能的 JSON 包装
      const clean = stripJsonWrapper(content)
      entries.push({ kind: 'narration', txt: clean })
      continue
    }

    // 玩家
    if (role === 'player') {
      entries.push({
        kind: 'player',
        speaker: player?.name || '我',
        letter: (player?.name || '我').slice(0, 1),
        txt: content,
      })
      continue
    }

    // 队友（companion 或 companion_{name}）
    if (role === 'companion' || role.startsWith('companion_')) {
      const maybeName = role.startsWith('companion_') ? role.slice('companion_'.length) : '队友'
      entries.push({
        kind: 'companion',
        speaker: maybeName,
        letter: maybeName.slice(0, 1),
        txt: content,
      })
      continue
    }

    // system 显示为分隔符
    if (role === 'system' || logType === 'system') {
      entries.push({ kind: 'system', txt: content })
      continue
    }

    // 兜底：作为旁白
    entries.push({ kind: 'narration', txt: content })
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

  return (
    <div style={{
      height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden',
      background: 'linear-gradient(180deg, #0a0604 0%, #06040a 100%)',
    }}>
      {/* 顶部返回条 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '12px 20px',
        background: 'linear-gradient(180deg, rgba(16,10,4,.95), rgba(10,6,2,.85))',
        borderBottom: '1px solid rgba(138,90,24,.5)',
        boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15), 0 4px 10px -4px rgba(0,0,0,.8)',
        zIndex: 5, flexShrink: 0,
      }}>
        <button
          className="btn-ghost"
          style={{ padding: '6px 14px', fontSize: 11, borderColor: 'rgba(127,232,248,.6)', color: 'var(--arcane-light)' }}
          onClick={onBack}
        >
          ◀ 返回对话
        </button>
        <div style={{ flex: 1, textAlign: 'center', minWidth: 0 }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 9,
            color: 'var(--amber)', letterSpacing: '.35em', opacity: .7,
          }}>DIALOGUE LOG</div>
          <div className="display-title" style={{
            fontSize: 18, letterSpacing: '.12em', color: 'var(--parchment)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            对话史册 · {session?.module_name || '冒险'}
          </div>
        </div>
        <div style={{ width: 80 }} />
      </div>

      {/* 章节目录 + 内容 */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '180px 1fr', overflow: 'hidden' }}>

        {/* 左 · 章节目录 + 筛选 */}
        <div style={{
          borderRight: '1px solid rgba(138,90,24,.35)',
          background: 'rgba(10,6,2,.5)',
          padding: '16px 10px',
          overflow: 'auto',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 9,
            color: 'var(--parchment-dark)', letterSpacing: '.25em',
            textTransform: 'uppercase', marginBottom: 10, padding: '0 6px',
          }}>章节目录</div>

          {chapters.map((ch, i) => (
            <div key={i} className={`chapter-nav ${ch.cur ? 'current' : ''}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{
                  fontFamily: 'var(--font-display)', fontSize: 12,
                  color: ch.cur ? 'var(--amber)' : 'var(--parchment-dark)',
                  letterSpacing: '.15em',
                }}>{ch.i}</span>
              </div>
              <div style={{
                fontSize: 12,
                color: ch.cur ? 'var(--parchment)' : 'rgba(232,200,160,.6)',
                marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{ch.title}</div>
            </div>
          ))}

          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 9,
            color: 'var(--parchment-dark)', letterSpacing: '.25em',
            textTransform: 'uppercase', marginTop: 24, marginBottom: 10, padding: '0 6px',
          }}>筛选</div>

          {[
            { k: 'all',    n: '全部',       c: counts.all },
            { k: 'npc',    n: '仅 NPC 对话', c: counts.npc },
            { k: 'player', n: '仅玩家发言',   c: counts.player },
            { k: 'roll',   n: '仅检定结果',   c: counts.roll },
            { k: 'narr',   n: '仅旁白',      c: counts.narr },
          ].map(f => (
            <div
              key={f.k}
              className={`filter-pill ${filter === f.k ? 'active' : ''}`}
              onClick={() => setFilter(f.k)}
            >
              <span>{f.n}</span>
              <span className="count">{f.c}</span>
            </div>
          ))}
        </div>

        {/* 右 · 滚动流 */}
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="adv-history-scroll"
          style={{ overflow: 'auto', position: 'relative' }}
        >
          <div className="dialogue-history" style={{
            padding: '20px 40px 80px', maxWidth: 900, margin: '0 auto', width: '100%',
          }}>
            {/* 首章分隔 */}
            <div className="hist-divider">
              <span className="ornament">❦</span>
              <span className="title">{session?.save_name || '冒险日志'}</span>
              <span className="time">{session?.module_name || '—'}</span>
            </div>

            {filteredEntries.length === 0 && (
              <p style={{
                fontFamily: 'var(--font-script)', fontStyle: 'italic',
                color: 'var(--parchment-dark)', textAlign: 'center',
                padding: '40px 0',
              }}>
                {filter === 'all' ? '还没有任何对话记录' : '当前筛选下没有匹配的记录'}
              </p>
            )}

            {filteredEntries.map((h, i) => {
              if (h.kind === 'narration' || h.kind === 'system') {
                return (
                  <p key={i} className="hist-narration">
                    {h.kind === 'system' ? `· ${h.txt} ·` : h.txt}
                  </p>
                )
              }
              if (h.kind === 'npc' || h.kind === 'companion') {
                return (
                  <div key={i} className="hist-bubble npc">
                    <div className="hist-avatar npc" data-cls={h.cls || 'commoner'}>{h.letter}</div>
                    <div className="hist-body">
                      <div className="hist-name">❖ {h.speaker}</div>
                      <p className={`hist-line ${h.emphasis ? 'emphasis' : ''}`}>{h.txt}</p>
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
                      <p className="hist-line">{h.txt}</p>
                    </div>
                    <div className="hist-avatar player">{h.letter}</div>
                  </div>
                )
              }
              if (h.kind === 'roll') {
                return (
                  <div key={i} className={`hist-roll ${h.result}`}>
                    <span className="die">🎲</span>
                    <span className="check">{h.label}{h.dc != null ? ` · DC ${h.dc}` : ''}</span>
                    {h.roll != null && (
                      <span className="calc">
                        {h.roll}{h.mod >= 0 ? '+' : ''}{h.mod} = <b>{h.total}</b>
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
                <div className="hist-current-divider" style={{ marginTop: 24 }}>
                  <span className="dot" />
                  <span className="label">当前 · 对话进行中</span>
                  <span className="dot" />
                </div>
                <div style={{
                  padding: '14px 18px',
                  background: 'linear-gradient(180deg, rgba(40,26,14,.6), rgba(26,18,8,.4))',
                  border: '1px dashed rgba(138,90,24,.5)',
                  fontFamily: 'var(--font-script)', fontStyle: 'italic',
                  color: 'var(--parchment-dark)', fontSize: 13, lineHeight: 1.7,
                  textAlign: 'center',
                }}>
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
