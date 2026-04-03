import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { gameApi, charactersApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import DiceRollerOverlay from '../components/DiceRollerOverlay'
import { BackIcon, SaveIcon, RestIcon, JournalIcon, BookIcon, DiceD20Icon, SwordIcon, ShieldIcon, HeartIcon, ScrollIcon, ClassIcon } from '../components/Icons'

// ── 常量 ──────────────────────────────────────────────────
const ABILITY_LABEL = { str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力' }
const QUICK_ACTIONS = ['四处张望', '搜索房间', '与NPC交谈', '检查周围', '小心前进', '原地等待']

export default function Adventure() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { isLoading, setIsLoading, showDice, setCombatActive } = useGameStore()

  const [session, setSession] = useState(null)
  const [logs, setLogs] = useState([])
  const [player, setPlayer] = useState(null)
  const [companions, setCompanions] = useState([])
  const [input, setInput] = useState('')
  const [quickActions, setQuickActions] = useState(QUICK_ACTIONS)
  const [error, setError] = useState('')
  const [pendingCheck, setPendingCheck] = useState(null)
  const [checkRolling, setCheckRolling] = useState(false)
  const [restOpen, setRestOpen] = useState(false)
  const [prepareOpen, setPrepareOpen] = useState(false)
  const [journalOpen, setJournalOpen] = useState(false)
  const [journalText, setJournalText] = useState('')
  const [journalLoading, setJournalLoading] = useState(false)

  const logsEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { loadSession() }, [sessionId])
  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [logs, pendingCheck])

  const loadSession = async () => {
    try {
      const data = await gameApi.getSession(sessionId)
      setSession(data); setLogs(data.logs || []); setPlayer(data.player)
      setCompanions(data.companions || []); setCombatActive(false)
      if (data.combat_active) navigate(`/combat/${sessionId}`)
    } catch (e) { setError(e.message) }
  }

  const refreshCharacters = async () => {
    try { const data = await gameApi.getSession(sessionId); setPlayer(data.player); setCompanions(data.companions || []) } catch {}
  }

  const addLog = useCallback((role, content, logType = 'narrative', extra = {}) => {
    setLogs(prev => [...prev, { id: `${role}-${Date.now()}-${Math.random()}`, role, content, log_type: logType, created_at: new Date().toISOString(), ...extra }])
  }, [])

  // ── 主行动 ──────────────────────────────────────────────
  const handleAction = async (overrideText) => {
    const text = (overrideText ?? input).trim()
    if (!text || isLoading) return
    setInput(''); setError(''); setPendingCheck(null); setQuickActions([]); setIsLoading(true)
    addLog('player', text, 'narrative')
    try {
      const resp = await gameApi.action({ session_id: sessionId, action_text: text })
      if (resp.narrative) addLog('dm', resp.narrative, 'narrative')
      if (resp.companion_reactions) addLog('companion', resp.companion_reactions, 'companion')
      if (resp.dice_display?.length) {
        for (const d of resp.dice_display) {
          addLog('dice', `${d.label || '骰子'}：${d.raw}${d.modifier ? ` + ${d.modifier}` : ''} = ${d.total}${d.against ? ` vs ${d.against}` : ''} ${d.outcome ? `→ ${d.outcome}` : ''}`, 'dice', { dice_result: d })
        }
      }
      if (resp.needs_check?.required) { setPendingCheck(resp.needs_check); setCheckRolling(false) }
      if (resp.player_choices?.length) setQuickActions(resp.player_choices)
      if (resp.combat_triggered) { addLog('system', '⚔ 战斗开始！', 'system'); await refreshCharacters(); setTimeout(() => navigate(`/combat/${sessionId}`), 1800); return }
      if (resp.combat_ended) addLog('system', resp.combat_end_result === 'victory' ? '🏆 战斗胜利！' : '💀 全灭...', 'system')
      if (resp.type !== 'parse_error') await refreshCharacters()
    } catch (e) { setError(e.message); addLog('system', `⚠ AI响应失败: ${e.message}`, 'system') }
    finally { setIsLoading(false); inputRef.current?.focus() }
  }

  const handleDiceRoll = async () => {
    if (!pendingCheck || checkRolling) return
    setCheckRolling(true)
    try {
      const result = await gameApi.skillCheck({ session_id: sessionId, character_id: pendingCheck.character_id || player?.id, skill: pendingCheck.check_type, dc: pendingCheck.dc })
      showDice({ faces: 20, result: result.d20, label: `${pendingCheck.check_type}检定` })
      const checkSummary = `${pendingCheck.check_type}检定 (DC ${pendingCheck.dc})：d20=${result.d20} ${result.modifier >= 0 ? '+' : ''}${result.modifier}${result.proficient ? ' [熟练]' : ''} = ${result.total} → ${result.success ? '✅ 成功' : '❌ 失败'}`
      addLog('dice', checkSummary, 'dice', { dice_result: result })
      setPendingCheck(null)
      // 自动将检定结果发送给 DM（避免玩家篡改结果）
      const autoMsg = `[${pendingCheck.check_type}检定 ${result.success ? '成功' : '失败'}: ${result.total} vs DC${pendingCheck.dc}]`
      setTimeout(() => handleAction(autoMsg), 800)
    } catch (e) { addLog('system', `检定失败: ${e.message}`, 'system'); setPendingCheck(null) }
    finally { setCheckRolling(false); inputRef.current?.focus() }
  }

  const handleRest = async (restType) => {
    setRestOpen(false); setIsLoading(true)
    try {
      const result = await gameApi.rest(sessionId, restType)
      const summary = result.characters?.map(c => `${c.name} HP+${c.hp_recovered} → ${c.hp_current}`).join(' | ')
      addLog('system', `🌙 完成${restType === 'long' ? '长休' : '短休'}。${summary}`, 'system')
      await refreshCharacters()
    } catch (e) { setError(e.message) } finally { setIsLoading(false) }
  }

  const handleGenerateJournal = async () => {
    setJournalLoading(true); setJournalText('')
    try { setJournalText((await gameApi.generateJournal(sessionId)).journal || '（生成失败）') }
    catch (e) { setJournalText(`失败：${e.message}`) } finally { setJournalLoading(false) }
  }

  const handlePrepareSpells = async (prepared) => {
    try { await charactersApi.prepareSpells(player.id, prepared); setPlayer(prev => ({ ...prev, prepared_spells: prepared })); addLog('system', `📖 已备法术更新（${prepared.length} 个）`, 'system'); setPrepareOpen(false) }
    catch (e) { addLog('system', `备法失败：${e.message}`, 'system') }
  }

  const handleCheckpoint = async () => {
    setIsLoading(true)
    try { await gameApi.saveCheckpoint(sessionId); addLog('system', '💾 战役进度已保存', 'system') }
    catch (e) { addLog('system', `存档失败：${e.message}`, 'system') } finally { setIsLoading(false) }
  }

  const canPrepareSpells = player && (player.known_spells?.length > 0) && ['Wizard','Cleric','Druid','Paladin','Ranger','法师','牧师','德鲁伊','圣武士','游侠'].includes(player.char_class)
  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAction() } }

  if (!session) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center', color: 'var(--gold)' }}>
        <SwordIcon size={36} color="var(--gold)" style={{ margin: '0 auto 12px' }} />
        <p style={{ animation: 'pulse 1.5s infinite' }}>加载冒险中...</p>
      </div>
    </div>
  )

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
      <DiceRollerOverlay />
      {prepareOpen && player && <PrepareSpellsModal player={player} onSave={handlePrepareSpells} onClose={() => setPrepareOpen(false)} />}
      {journalOpen && <JournalModal text={journalText} loading={journalLoading} onGenerate={handleGenerateJournal} onClose={() => setJournalOpen(false)} />}
      {restOpen && <RestModal onRest={handleRest} onClose={() => setRestOpen(false)} />}

      {/* ── 顶栏 ── */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid var(--wood-light)', background: 'var(--bg2)', flexShrink: 0 }}>
        <button className="btn-fantasy" style={{ fontSize: 12, padding: '4px 12px', display: 'flex', alignItems: 'center', gap: 4 }} onClick={() => navigate('/')}>
          <BackIcon size={14} /> 主页
        </button>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ color: 'var(--gold)', fontSize: 14, fontWeight: 700, margin: 0 }}>{session.save_name}</h2>
          {session.current_scene && <p style={{ color: 'var(--text-dim)', fontSize: 11, margin: 0, maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>📍 {session.current_scene}</p>}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {player && <HeaderBtn icon={<ShieldIcon size={13} />} label="角色" onClick={() => navigate(`/character/${player.id}`)} />}
          {canPrepareSpells && <HeaderBtn icon={<BookIcon size={13} />} label="备法" onClick={() => setPrepareOpen(true)} accent />}
          <HeaderBtn icon={<SaveIcon size={13} />} label="存档" onClick={handleCheckpoint} disabled={isLoading} />
          <HeaderBtn icon={<RestIcon size={13} />} label="休息" onClick={() => setRestOpen(true)} />
          <HeaderBtn icon={<JournalIcon size={13} />} label="日志" onClick={() => { setJournalOpen(true); if (!journalText) handleGenerateJournal() }} />
        </div>
      </header>

      {/* ── 主体 ── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* 左栏：队伍面板 */}
        <aside style={{ width: 190, flexShrink: 0, borderRight: '1px solid var(--wood-light)', background: 'var(--bg)', overflowY: 'auto', padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <p style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 4px' }}>队伍状态</p>
          {player && <CharCard char={player} isPlayer />}
          {companions.map(c => <CharCard key={c.id} char={c} />)}
        </aside>

        {/* 中栏：对话 + 输入 */}
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* 对话区 — 酒馆桌面 */}
          <div className="tavern-table" style={{ flex: 1, overflowY: 'auto', margin: 0, borderRadius: 0, border: 'none', borderBottom: '1px solid var(--wood-light)', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {logs.map(log => <LogEntry key={log.id} log={log} />)}
            {isLoading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, opacity: 0.7 }}>
                <div className="portrait portrait-dm" style={{ width: 28, height: 28, fontSize: 12 }}><ScrollIcon size={14} color="var(--gold-dim)" /></div>
                <span style={{ color: 'var(--parchment-dark)', fontSize: 13, animation: 'pulse 1.5s infinite' }}>地下城主正在思考...</span>
              </div>
            )}
            {pendingCheck && <CheckPromptCard check={pendingCheck} rolling={checkRolling} onRoll={handleDiceRoll} />}
            <div ref={logsEndRef} />
          </div>

          {/* 快捷行动（检定待决时隐藏，避免预设结果） */}
          {quickActions.length > 0 && !pendingCheck && (
            <div style={{ borderTop: '1px solid var(--wood-light)', padding: '8px 16px', background: 'var(--bg)', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {quickActions.map((a, i) => (
                <button key={i} className="skill-btn" disabled={isLoading} onClick={() => { setInput(a); inputRef.current?.focus() }}>{a}</button>
              ))}
            </div>
          )}

          {/* 输入区 */}
          <div style={{ borderTop: '1px solid var(--wood-light)', padding: '10px 16px', background: 'var(--bg2)', flexShrink: 0 }}>
            {error && <p style={{ color: 'var(--red-light)', fontSize: 12, marginBottom: 8 }}>⚠ {error}</p>}
            <div className="scroll-input-bar">
              <textarea ref={inputRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown} disabled={isLoading} rows={1}
                placeholder="描述你的行动... (Enter 发送)"
                style={{ flex: 1, background: 'transparent', border: 'none', color: 'var(--parchment)', fontSize: 13, fontFamily: 'inherit', resize: 'none', outline: 'none', minHeight: '1.5rem', maxHeight: '4rem', lineHeight: 1.5 }} />
              <button onClick={() => handleAction()} disabled={!input.trim() || isLoading}
                style={{ width: 36, height: 36, borderRadius: '50%', flexShrink: 0, background: 'linear-gradient(135deg, var(--gold), var(--gold-dim))', border: 'none', cursor: 'pointer', fontSize: 16, color: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.2s', opacity: (!input.trim() || isLoading) ? 0.4 : 1 }}>
                {isLoading ? '⏳' : '➤'}
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════
// 子组件
// ══════════════════════════════════════════════════════════

function HeaderBtn({ icon, label, onClick, disabled, accent }) {
  return (
    <button className="btn-fantasy" onClick={onClick} disabled={disabled}
      style={{ fontSize: 11, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4, borderColor: accent ? '#7c3aed' : undefined }}>
      {icon} {label}
    </button>
  )
}

// ── 日志提取 ─────────────────────────────────────────────
function extractNarrative(content) {
  if (!content) return ''
  const trimmed = content.trim()
  if (trimmed.startsWith('```') || trimmed.startsWith('{')) {
    try {
      const jsonStr = trimmed.replace(/^```(?:json)?\s*\n?/m, '').replace(/\n?\s*```\s*$/m, '').trim()
      const parsed = JSON.parse(jsonStr)
      if (parsed.narrative) return parsed.narrative
      if (parsed.content) return parsed.content
    } catch {
      const m = trimmed.match(/"narrative"\s*:\s*"((?:[^"\\]|\\.)*)"/s)
      if (m) return m[1].replace(/\\"/g, '"').replace(/\\n/g, '\n')
    }
  }
  return content
}

function LogEntry({ log }) {
  const role = log.role || 'system'
  const isDM = role === 'dm', isPlayer = role === 'player'
  const isCompanion = role.startsWith('companion'), isDice = log.log_type === 'dice'

  if (isDM) return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <div className="portrait portrait-dm" style={{ width: 36, height: 36 }}><ScrollIcon size={16} color="var(--gold-dim)" /></div>
      <div style={{ flex: 1 }}>
        <span style={{ fontSize: 10, color: 'var(--gold-dim)', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 4, display: 'block' }}>地下城主</span>
        <div className="bubble-dm">{extractNarrative(log.content)}</div>
      </div>
    </div>
  )
  if (isPlayer) return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', justifyContent: 'flex-end' }}>
      <div style={{ maxWidth: '70%' }}><div className="bubble-player">{log.content}</div></div>
      <div className="portrait portrait-player" style={{ width: 36, height: 36 }}><ShieldIcon size={16} color="var(--blue-light)" /></div>
    </div>
  )
  if (isCompanion) return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <div className="portrait portrait-ally" style={{ width: 36, height: 36 }}><SwordIcon size={16} color="var(--green-light)" /></div>
      <div style={{ flex: 1 }}>
        <span style={{ fontSize: 10, color: 'var(--green-light)', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 4, display: 'block' }}>队友</span>
        <div className="bubble-ally" style={{ whiteSpace: 'pre-wrap' }}>{log.content}</div>
      </div>
    </div>
  )
  if (isDice) return (
    <div style={{ textAlign: 'center', padding: '4px 0' }}>
      <span className="dice-badge"><DiceD20Icon size={14} style={{ marginRight: 4 }} /> {log.content}</span>
    </div>
  )
  return <div style={{ textAlign: 'center' }}><span style={{ color: 'var(--text-dim)', fontSize: 12, fontStyle: 'italic' }}>{log.content}</span></div>
}

// ── 检定提示卡 ───────────────────────────────────────────
function CheckPromptCard({ check, rolling, onRoll }) {
  return (
    <div className="panel" style={{ padding: '14px 16px', borderColor: '#7c3aed', boxShadow: '0 0 20px rgba(124,58,237,0.2)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <DiceD20Icon size={20} color="#a78bfa" />
        <span style={{ color: '#c4b5fd', fontSize: 14, fontWeight: 700 }}>{check.check_type}检定</span>
        {ABILITY_LABEL[check.ability] && <span className="tag" style={{ color: '#a78bfa', borderColor: '#7c3aed', fontSize: 11 }}>{ABILITY_LABEL[check.ability]}</span>}
        <span style={{ color: 'var(--bg)', background: '#a78bfa', fontSize: 11, fontWeight: 700, borderRadius: 4, padding: '1px 8px' }}>DC {check.dc}</span>
      </div>
      {check.context && <p style={{ color: '#9f7adb', fontSize: 12, margin: '0 0 10px' }}>{check.context}</p>}
      <button onClick={onRoll} disabled={rolling} className="btn-gold" style={{ width: '100%', padding: '10px', fontSize: 14, background: rolling ? '#3b1a6a' : undefined, borderColor: '#a78bfa' }}>
        {rolling ? '掷骰中...' : '掷骰 🎲'}
      </button>
    </div>
  )
}

// ── 角色卡 ───────────────────────────────────────────────
function CharCard({ char, isPlayer }) {
  const hpMax = char.hp_max ?? char.derived?.hp_max ?? char.hp_current ?? 1
  const hpCur = char.hp_current ?? 0, ac = char.ac ?? char.derived?.ac ?? '?'
  const hpPct = Math.max(0, Math.min(100, Math.round((hpCur / hpMax) * 100)))
  const hpColor = hpPct > 60 ? 'var(--green-light)' : hpPct > 30 ? '#f59e0b' : 'var(--red-light)'
  const slots = char.spell_slots || {}, slotsMax = char.derived?.spell_slots_max || {}

  return (
    <div className="panel" style={{ padding: '10px', borderRadius: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <div className={isPlayer ? 'portrait portrait-player' : 'portrait portrait-ally'} style={{ width: 28, height: 28 }}>
          <ClassIcon className={char.char_class} size={14} color={isPlayer ? 'var(--blue-light)' : 'var(--green-light)'} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ color: 'var(--text-bright)', fontSize: 12, fontWeight: 700, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{char.name}</p>
          <p style={{ color: 'var(--text-dim)', fontSize: 10, margin: 0 }}>{char.char_class} Lv{char.level}</p>
        </div>
      </div>
      {/* HP */}
      <div style={{ marginBottom: 4 }}>
        <div style={{ height: 4, background: 'var(--wood)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ height: '100%', borderRadius: 2, background: hpColor, width: `${hpPct}%`, transition: 'width 0.4s' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
          <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>HP {hpCur}/{hpMax}</span>
          <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>AC {ac}</span>
        </div>
      </div>
      {/* 金币 */}
      {isPlayer && (char.equipment?.gold != null || char.gold != null) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
          <span style={{ fontSize: 11 }}>&#x1F4B0;</span>
          <span style={{ color: 'var(--gold)', fontSize: 11, fontWeight: 600 }}>{char.equipment?.gold ?? char.gold ?? 0} gp</span>
        </div>
      )}
      {/* 法术位 */}
      {Object.keys(slotsMax).length > 0 && (
        <div style={{ marginBottom: 4 }}>
          {Object.entries(slotsMax).slice(0, 4).map(([lvl, max]) => (
            <div key={lvl} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
              <span style={{ color: '#5a4a7a', fontSize: 9, width: 18 }}>{lvl[0]}环</span>
              <div style={{ display: 'flex', gap: 2 }}>
                {Array.from({ length: max }).map((_, i) => (
                  <div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: i < (slots[lvl] ?? max) ? '#7c3aed' : 'var(--wood)', border: '1px solid #4a2a7a' }} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {/* 条件 */}
      {char.conditions?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          {char.conditions.map(c => <span key={c} style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(139,32,32,0.3)', color: 'var(--red-light)' }}>{c}</span>)}
        </div>
      )}
      {hpCur === 0 && <p style={{ color: 'var(--red-light)', fontSize: 10, margin: '4px 0 0', fontWeight: 700 }}>💀 濒死</p>}
    </div>
  )
}

// ── 弹窗组件 ─────────────────────────────────────────────
function Overlay({ children, onClose }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 500, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{ padding: 24, width: 500, maxWidth: '90vw', maxHeight: '85vh', display: 'flex', flexDirection: 'column', gap: 16, borderColor: 'var(--wood-light)' }}>
        {children}
      </div>
    </div>
  )
}

function RestModal({ onRest, onClose }) {
  return (
    <Overlay onClose={onClose}>
      <h3 style={{ color: 'var(--gold)', margin: 0, fontSize: 16, display: 'flex', alignItems: 'center', gap: 6 }}><RestIcon size={18} color="var(--gold)" /> 休息</h3>
      <button className="btn-fantasy" style={{ padding: 14, textAlign: 'left' }} onClick={() => onRest('long')}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>🌙 长休（8小时）</div>
        <div style={{ fontSize: 12, opacity: 0.6 }}>HP 全满 · 法术位全恢复 · 清除大多数状态条件</div>
      </button>
      <button className="btn-fantasy" style={{ padding: 14, textAlign: 'left' }} onClick={() => onRest('short')}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>☕ 短休（1小时）</div>
        <div style={{ fontSize: 12, opacity: 0.6 }}>消耗一颗生命骰恢复 HP · 魔契者恢复法术位</div>
      </button>
      <button className="btn-fantasy" style={{ padding: 8, opacity: 0.6 }} onClick={onClose}>取消</button>
    </Overlay>
  )
}

function JournalModal({ text, loading, onGenerate, onClose }) {
  return (
    <Overlay onClose={onClose}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ color: 'var(--gold)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}><JournalIcon size={18} color="var(--gold)" /> 冒险日志</h3>
        <button onClick={onClose} style={{ color: 'var(--text-dim)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 200, maxHeight: '55vh', background: 'var(--bg)', borderRadius: 8, padding: 16, border: '1px solid var(--wood)' }}>
        {loading ? <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--gold)' }} className="animate-pulse">DM 正在撰写日志...</div>
         : text ? <p style={{ color: 'var(--parchment)', lineHeight: 1.9, fontSize: 14, whiteSpace: 'pre-wrap', margin: 0 }}>{text}</p>
         : <p style={{ color: 'var(--text-dim)', textAlign: 'center', marginTop: 32, fontSize: 13 }}>点击下方按钮生成本次冒险的叙述日志</p>}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onGenerate} disabled={loading}>{loading ? '生成中...' : '🔄 重新生成'}</button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>关闭</button>
      </div>
    </Overlay>
  )
}

function PrepareSpellsModal({ player, onSave, onClose }) {
  const derived = player.derived || {}, mods = derived.ability_modifiers || {}
  const spellMod = derived.spell_ability ? (mods[derived.spell_ability] || 0) : 0
  const maxPrepared = Math.max(1, player.level + spellMod)
  const [selected, setSelected] = useState(new Set(player.prepared_spells || []))
  const toggle = (s) => setSelected(prev => { const n = new Set(prev); n.has(s) ? n.delete(s) : n.size < maxPrepared && n.add(s); return n })

  return (
    <Overlay onClose={onClose}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ color: '#c4b5fd', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}><BookIcon size={18} color="#c4b5fd" /> 准备法术</h3>
          <p style={{ color: '#5a4a7a', fontSize: 12, margin: '4px 0 0' }}>上限：{selected.size}/{maxPrepared}</p>
        </div>
        <button onClick={onClose} style={{ color: 'var(--text-dim)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
        {(player.known_spells || []).map(spell => {
          const sel = selected.has(spell), can = sel || selected.size < maxPrepared
          return <button key={spell} onClick={() => toggle(spell)} className="btn-fantasy" style={{ textAlign: 'left', opacity: can ? 1 : 0.4, borderColor: sel ? '#7c3aed' : undefined, background: sel ? 'rgba(124,58,237,0.15)' : undefined, color: sel ? '#c4b5fd' : undefined }}>{sel ? '✓ ' : ''}{spell}</button>
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-gold" style={{ padding: '8px 16px', fontSize: 13 }} onClick={() => onSave([...selected])}>确认（{selected.size}/{maxPrepared}）</button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>取消</button>
      </div>
    </Overlay>
  )
}
