/**
 * Adventure — CRPG 剧场式对话冒险（design v0.10）
 *
 * 布局：
 *   顶部章节条（自动存档 / 章节名 / 快捷按钮）
 *   中部舞台（背景 + 两侧大 silhouette + 中央粒子）
 *   对话气泡（旁白 + NPC 发言 + 编号选项 + 自由输入）
 *   底部 HUD（队伍头像 + 目标与线索 + 密语/卷宗）
 *
 * 保留原有业务逻辑：
 *   - gameApi.action / skillCheck / rest / saveCheckpoint / generateJournal
 *   - charactersApi.prepareSpells
 *   - useWebSocket 多人联机事件
 *   - 3D 骰子（rollDice3D / DiceRollerOverlay）
 *   - pendingCheck 检定流
 *   - PrepareSpellsModal / JournalModal / RestModal（保留定义）
 */
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { gameApi, charactersApi, roomsApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import { useWebSocket } from '../hooks/useWebSocket'
import DiceRollerOverlay, { rollDice3D } from '../components/DiceRollerOverlay'
import Portrait from '../components/Portrait'
import { classKey } from '../components/Crests'
import { BookIcon, RestIcon, JournalIcon } from '../components/Icons'
import DialogueHistoryView from '../components/DialogueHistoryView'
import DMThinkingOverlay from '../components/DMThinkingOverlay'
import { JuiceAudio, shake as JuiceShake } from '../juice'

export default function Adventure() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { isLoading, setIsLoading, showDice, setCombatActive } = useGameStore()

  const [session, setSession] = useState(null)
  const [logs, setLogs] = useState([])
  const [player, setPlayer] = useState(null)
  const [companions, setCompanions] = useState([])
  const [input, setInput] = useState('')
  const [choices, setChoices] = useState([])         // 当前回合的对话选项
  const [pendingCheck, setPendingCheck] = useState(null)
  const [checkRolling, setCheckRolling] = useState(false)
  const [error, setError] = useState('')
  const [restOpen, setRestOpen] = useState(false)
  const [prepareOpen, setPrepareOpen] = useState(false)
  const [journalOpen, setJournalOpen] = useState(false)
  const [journalText, setJournalText] = useState('')
  const [journalLoading, setJournalLoading] = useState(false)

  // ── 对话流系统（v0.10.1）──
  // mode='chat' 聊天日志视图；mode='stage' 剧场对话视图（逐条气泡+打字机）
  const [dialogueMode, setDialogueMode] = useState('chat')
  const [showHistory, setShowHistory] = useState(false)       // 对话史册视图（v0.10.2）
  const [dialogueQueue, setDialogueQueue] = useState([])      // {speaker, role, text, color, logType}[]
  const [dialogueIdx, setDialogueIdx] = useState(0)
  const [typingText, setTypingText] = useState('')
  const [typingDone, setTypingDone] = useState(true)
  const typingTimerRef = useRef(null)

  const logsEndRef = useRef(null)
  const inputRef = useRef(null)

  // ── 多人联机 ──
  const [room, setRoom] = useState(null)
  const myUserId = useMemo(() => {
    const u = JSON.parse(localStorage.getItem('user') || 'null')
    return u?.user_id || u?.id || null
  }, [])

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const r = await roomsApi.get(sessionId)
        if (mounted && r?.is_multiplayer) {
          setRoom({ ...r, _currentSpeaker: r.current_speaker_user_id })
        }
      } catch (_) {}
    })()
    return () => { mounted = false }
  }, [sessionId])

  const onWsEvent = useCallback((event) => {
    switch (event.type) {
      case 'dm_responded':
        loadSession(); break
      case 'dm_speak_turn':
        setRoom(prev => prev ? { ...prev, _currentSpeaker: event.user_id } : prev)
        break
      case 'member_online':
      case 'member_offline':
      case 'member_joined':
      case 'member_left':
      case 'character_claimed':
        roomsApi.get(sessionId)
          .then(r => r?.is_multiplayer && setRoom({ ...r, _currentSpeaker: r.current_speaker_user_id }))
          .catch(() => {})
        break
      default: break
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const { send: wsSend } = useWebSocket(room ? sessionId : null, onWsEvent)

  const currentSpeakerUid = room?._currentSpeaker
  const isMySpeakTurn = !room || !currentSpeakerUid || currentSpeakerUid === myUserId
  const currentSpeakerName = (room?.members || []).find(m => m.user_id === currentSpeakerUid)?.display_name

  // ── 数据加载 ──
  useEffect(() => { loadSession() }, [sessionId])
  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [logs, pendingCheck])

  const loadSession = async () => {
    try {
      const data = await gameApi.getSession(sessionId)
      setSession(data)
      setLogs(data.logs || [])
      setPlayer(data.player)
      setCompanions(data.companions || [])
      setCombatActive(false)
      if (data.combat_active) navigate(`/combat/${sessionId}`)
    } catch (e) { setError(e.message) }
  }

  const refreshCharacters = async () => {
    try {
      const data = await gameApi.getSession(sessionId)
      setSession(data); setPlayer(data.player); setCompanions(data.companions || [])
    } catch {}
  }

  const addLog = useCallback((role, content, logType = 'narrative', extra = {}) => {
    setLogs(prev => [...prev, {
      id: `${role}-${Date.now()}-${Math.random()}`,
      role, content, log_type: logType,
      created_at: new Date().toISOString(), ...extra
    }])
  }, [])

  // ── 主行动 ──
  const handleAction = async (overrideText) => {
    const text = (overrideText ?? input).trim()
    if (!text || isLoading) return
    setInput(''); setError(''); setPendingCheck(null); setChoices([]); setIsLoading(true)
    addLog('player', text, 'narrative')
    try {
      const resp = await gameApi.action({ session_id: sessionId, action_text: text })

      // 构建对话队列（DM 叙述拆段 + 队友反应按"[名字]:"拆开）
      const queue = []
      if (resp.narrative) {
        splitDmNarrative(resp.narrative).forEach(seg => {
          queue.push({
            speaker: seg.speaker || 'DM',
            role: seg.role || 'dm',
            text: seg.text,
            color: seg.color,
          })
        })
      }
      if (resp.companion_reactions) {
        splitCompanionReactions(resp.companion_reactions, companions).forEach(seg => {
          queue.push({ speaker: seg.speaker, role: 'companion', text: seg.text, color: seg.color })
        })
      }

      if (resp.dice_display?.length) {
        for (const d of resp.dice_display) {
          addLog('dice',
            `${d.label || '骰子'}：${d.raw}${d.modifier ? ` + ${d.modifier}` : ''} = ${d.total}${d.against ? ` vs ${d.against}` : ''} ${d.outcome ? `→ ${d.outcome}` : ''}`,
            'dice', { dice_result: d })
        }
      }
      if (resp.needs_check?.required) { setPendingCheck(resp.needs_check); setCheckRolling(false) }
      if (resp.player_choices?.length) setChoices(resp.player_choices)

      // 启动剧场模式播放队列
      if (queue.length > 0) {
        setDialogueQueue(queue)
        setDialogueIdx(0)
        setDialogueMode('stage')
      }

      if (resp.combat_triggered) {
        addLog('system', '⚔ 战斗开始！', 'system')
        await refreshCharacters()
        setTimeout(() => navigate(`/combat/${sessionId}`), 1800)
        return
      }
      if (resp.combat_ended) {
        addLog('system', resp.combat_end_result === 'victory' ? '🏆 战斗胜利！' : '💀 全灭...', 'system')
      }
      if (resp.type !== 'parse_error') await refreshCharacters()
    } catch (e) {
      setError(e.message)
      addLog('system', `⚠ AI响应失败: ${e.message}`, 'system')
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }

  // ── 打字机效果：每当 dialogueIdx 变化，逐字显示当前段 ──
  useEffect(() => {
    if (dialogueMode !== 'stage') return
    if (dialogueIdx >= dialogueQueue.length) return
    const seg = dialogueQueue[dialogueIdx]
    if (!seg) return
    setTypingText('')
    setTypingDone(false)
    const full = seg.text || ''
    let i = 0
    const step = () => {
      i += 1
      setTypingText(full.slice(0, i))
      if (i >= full.length) {
        setTypingDone(true)
        return
      }
      typingTimerRef.current = setTimeout(step, 30)
    }
    typingTimerRef.current = setTimeout(step, 60)
    return () => { if (typingTimerRef.current) clearTimeout(typingTimerRef.current) }
  }, [dialogueMode, dialogueIdx, dialogueQueue])

  // 推进对话：点击气泡 / 按空格
  const advanceDialogue = useCallback(() => {
    if (dialogueMode !== 'stage') return
    // 如果还没打完字，立即打完
    if (!typingDone) {
      if (typingTimerRef.current) clearTimeout(typingTimerRef.current)
      const seg = dialogueQueue[dialogueIdx]
      setTypingText(seg?.text || '')
      setTypingDone(true)
      return
    }
    // 已打完 → 把当前段入 log，推进下一段
    const seg = dialogueQueue[dialogueIdx]
    if (seg) addLog(seg.role, seg.text, seg.role === 'dm' ? 'narrative' : seg.role)
    const next = dialogueIdx + 1
    if (next >= dialogueQueue.length) {
      // 播放完毕：回到聊天模式
      setDialogueMode('chat')
      setDialogueQueue([])
      setDialogueIdx(0)
      setTypingText('')
      setTypingDone(true)
    } else {
      setDialogueIdx(next)
    }
  }, [dialogueMode, dialogueIdx, dialogueQueue, typingDone, addLog])

  // 空格推进
  useEffect(() => {
    if (dialogueMode !== 'stage') return
    const onKey = (e) => {
      if (e.code === 'Space' || e.code === 'Enter') {
        e.preventDefault()
        advanceDialogue()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dialogueMode, advanceDialogue])

  // ── 检定流 ──
  const handleDiceRoll = async () => {
    if (!pendingCheck || checkRolling) return
    setCheckRolling(true)
    try {
      const { total: d20 } = await rollDice3D(20)
      showDice({ faces: 20, result: d20, label: `${pendingCheck.check_type}检定` })
      const result = await gameApi.skillCheck({
        session_id: sessionId,
        character_id: pendingCheck.character_id || player?.id,
        skill: pendingCheck.check_type,
        dc: pendingCheck.dc,
        d20_value: d20
      })
      const checkSummary = `${pendingCheck.check_type}检定 (DC ${pendingCheck.dc})：d20=${result.d20} ${result.modifier >= 0 ? '+' : ''}${result.modifier}${result.proficient ? ' [熟练]' : ''} = ${result.total} → ${result.success ? '✅ 成功' : '❌ 失败'}`
      addLog('dice', checkSummary, 'dice', { dice_result: result })
      // Juice：检定结果音效 + 关键成功/失败震屏
      try {
        if (result.d20 === 20)      { JuiceAudio.crit() }
        else if (result.d20 === 1)  { JuiceAudio.miss(); JuiceShake(document.body, 6, 340) }
        else if (result.success)    { JuiceAudio.unlock() }
        else                        { JuiceAudio.miss() }
      } catch (e) {}
      // 带 context（原选项文本）一起送给 DM，避免丢失行动上下文
      const ctxPart = pendingCheck.context ? ` 我的行动："${pendingCheck.context}"` : ''
      setPendingCheck(null)
      const autoMsg = `[${pendingCheck.check_type}检定 ${result.success ? '成功' : '失败'}: ${result.total} vs DC${pendingCheck.dc}]${ctxPart}`
      setTimeout(() => handleAction(autoMsg), 800)
    } catch (e) {
      addLog('system', `检定失败: ${e.message}`, 'system'); setPendingCheck(null)
    } finally {
      setCheckRolling(false)
      inputRef.current?.focus()
    }
  }

  const handleRest = async (restType) => {
    setRestOpen(false); setIsLoading(true)
    try {
      const result = await gameApi.rest(sessionId, restType)
      const summary = result.characters?.map(c => `${c.name} HP+${c.hp_recovered} → ${c.hp_current}`).join(' | ')
      addLog('system', `🌙 完成${restType === 'long' ? '长休' : '短休'}。${summary}`, 'system')
      await refreshCharacters()
    } catch (e) { setError(e.message) }
    finally { setIsLoading(false) }
  }

  const handleGenerateJournal = async () => {
    setJournalLoading(true); setJournalText('')
    try { setJournalText((await gameApi.generateJournal(sessionId)).journal || '（生成失败）') }
    catch (e) { setJournalText(`失败：${e.message}`) }
    finally { setJournalLoading(false) }
  }

  const handlePrepareSpells = async (prepared) => {
    try {
      await charactersApi.prepareSpells(player.id, prepared)
      setPlayer(prev => ({ ...prev, prepared_spells: prepared }))
      addLog('system', `📖 已备法术更新（${prepared.length} 个）`, 'system')
      setPrepareOpen(false)
    } catch (e) { addLog('system', `备法失败：${e.message}`, 'system') }
  }

  const handleCheckpoint = async () => {
    try { await gameApi.saveCheckpoint(sessionId); addLog('system', '💾 战役进度已保存', 'system') }
    catch (e) { addLog('system', `保存失败：${e.message}`, 'system') }
  }

  // ── 准备法术权限 ──
  const canPrepareSpells = useMemo(() => {
    if (!player?.char_class) return false
    const cls = player.char_class.toLowerCase()
    return cls.includes('wizard') || cls.includes('cleric') || cls.includes('druid') ||
           cls.includes('法师') || cls.includes('牧师') || cls.includes('德鲁伊')
  }, [player])

  // ── 派生数据 ──
  const sceneVibe = session?.game_state?.scene_vibe || {}
  const clues = (session?.campaign_state?.clues || []).slice(-4)
  const questLine = session?.campaign_state?.quest_log?.find(q => q.status === 'active')
  const allMembers = useMemo(() => {
    const list = player ? [{ ...player, isPlayer: true }] : []
    ;(companions || []).forEach(c => list.push({ ...c, isPlayer: false }))
    return list
  }, [player, companions])

  // ── 最近 DM 对话提取（供舞台展示）──
  const latestDmLine = useMemo(() => {
    for (let i = logs.length - 1; i >= 0; i--) {
      const l = logs[i]
      if (l.role === 'dm' && l.log_type === 'narrative') return l
    }
    return null
  }, [logs])

  // 早期 loading 状态
  if (!session) return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', position: 'relative', zIndex: 1 }}>
      <div className="panel-ornate" style={{ padding: 28, fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)' }}>
        ✦ 召唤冒险中… ✦
      </div>
    </div>
  )

  // 对话史册视图（全屏覆盖）
  if (showHistory) {
    return (
      <div style={{ minHeight: '100vh', height: '100vh', position: 'relative', zIndex: 1 }}>
        <DialogueHistoryView
          session={session}
          player={player}
          onBack={() => setShowHistory(false)}
        />
      </div>
    )
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#06040a', position: 'relative', zIndex: 1 }}>
      <DiceRollerOverlay />
      {prepareOpen && player && <PrepareSpellsModal player={player} onSave={handlePrepareSpells} onClose={() => setPrepareOpen(false)} />}
      {journalOpen && <JournalModal text={journalText} loading={journalLoading} onGenerate={handleGenerateJournal} onClose={() => setJournalOpen(false)} />}
      {restOpen && <RestModal onRest={handleRest} onClose={() => setRestOpen(false)} />}

      {/* 多人发言权条 */}
      {room && (
        <div style={{
          background: isMySpeakTurn
            ? 'linear-gradient(90deg, rgba(74,138,74,0.4), rgba(74,138,74,0.15))'
            : 'linear-gradient(90deg, rgba(58,122,170,0.3), rgba(58,122,170,0.1))',
          borderBottom: '1px solid var(--amber)',
          padding: '5px 16px', color: 'var(--amber)',
          fontSize: 12, fontWeight: 'bold',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          zIndex: 5,
        }}>
          <span>{isMySpeakTurn ? '✓ 你的发言时机' : `等待 ${currentSpeakerName || '其他玩家'} 发言…`}</span>
          <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {isMySpeakTurn && currentSpeakerUid && (
              <button onClick={() => wsSend({ type: 'speak_done' })}
                style={{ padding: '3px 10px', fontSize: 11, background: 'var(--amber)', color: '#1a120b', border: 'none', borderRadius: 3, cursor: 'pointer', fontWeight: 'bold' }}>
                我说完了 →
              </button>
            )}
            <span style={{ fontSize: 11, opacity: 0.8 }}>房间码 {room.room_code}</span>
          </span>
        </div>
      )}

      {/* 顶部章节条 */}
      <div style={{
        position: 'relative',
        padding: '10px 20px',
        display: 'grid',
        gridTemplateColumns: '1fr auto 1fr',
        alignItems: 'center',
        background: 'linear-gradient(180deg, rgba(16,10,4,.95), rgba(10,6,2,.7))',
        borderBottom: '1px solid rgba(138,90,24,.4)',
        boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
        zIndex: 4,
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={() => navigate('/')}>◄ 主页</button>
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={handleCheckpoint} disabled={isLoading}>● 存档</button>
        </div>
        <div style={{ textAlign: 'center', minWidth: 0, maxWidth: '60vw' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.3em', opacity: .7 }}>
            {session.save_name || '我的冒险'}
          </div>
          <div className="display-title" style={{
            fontSize: 18, letterSpacing: '.12em',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {session.module_name || '未知模组'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
          <button
            className="btn-ghost"
            style={{ padding: '4px 10px', fontSize: 10, borderColor: 'rgba(127,232,248,.5)', color: 'var(--arcane-light)' }}
            onClick={() => setShowHistory(true)}
          >☰ 对话历史</button>
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={() => { setJournalOpen(true); if (!journalText) handleGenerateJournal() }}>✎ 日志</button>
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={() => setRestOpen(true)}>☾ 休息</button>
          {canPrepareSpells && (
            <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={() => setPrepareOpen(true)}>✧ 备法</button>
          )}
          {player && (
            <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={() => navigate(`/character/${player.id}`)}>⚜ 角色</button>
          )}
        </div>
      </div>

      {/* ═══ 主舞台区 ═══ */}
      <div style={{ flex: 1, display: 'grid', gridTemplateRows: '1fr auto auto', overflow: 'hidden', minHeight: 0 }}>

        {/* 剧场舞台 */}
        <div className="dialogue-stage" style={{ position: 'relative' }}>
          <div className="stage-letterbox top" />

          {/* 左侧 silhouette — 剧场模式跟随当前说话者 */}
          <StageLeftFigure
            dialogueMode={dialogueMode}
            currentSeg={dialogueQueue[dialogueIdx]}
            companions={companions}
            player={player}
            hasDmContent={!!latestDmLine}
          />


          {/* 玩家侧（右）*/}
          {player && (
            <div className="stage-figure right">
              <div className="silhouette" style={{ background: 'radial-gradient(circle at 40% 30%, #e8d070, #6a5020 75%)' }}>
                <div style={{
                  position: 'absolute', inset: 0,
                  display: 'grid', placeItems: 'center',
                  fontFamily: 'var(--font-display)', fontSize: 72,
                  color: '#fff8dd', textShadow: '0 4px 12px #000',
                }}>{(player.name || '我').slice(0, 1)}</div>
              </div>
              <div className="nameplate" style={{ background: 'linear-gradient(180deg, #3ec8d8, #14444e)', color: '#04181c', boxShadow: '0 0 0 1px rgba(127,232,248,.6), 0 0 12px -2px var(--arcane-light)' }}>
                ◈ {player.name}
              </div>
            </div>
          )}

          {/* 中央粒子 */}
          <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', pointerEvents: 'none' }}>
            <div style={{
              width: 54, height: 54, borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(127,232,248,.8), transparent 70%)',
              filter: 'blur(6px)', animation: 'breathe 2s ease-in-out infinite',
            }} />
          </div>

          {/* 场景信息角标 */}
          <div style={{
            position: 'absolute', top: 12, left: 16, display: 'flex', gap: 10,
            fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--parchment-dark)',
            letterSpacing: '.15em', zIndex: 4,
          }}>
            {sceneVibe.location && <span>🜂 {sceneVibe.location}</span>}
            {sceneVibe.time_of_day && <><span style={{ opacity: .5 }}>|</span><span>☀ {sceneVibe.time_of_day}</span></>}
            {sceneVibe.tension && (<><span style={{ opacity: .5 }}>|</span>
              <span style={{ color: sceneVibe.tension === '平静' ? 'var(--emerald-light)' : sceneVibe.tension === '危险' || sceneVibe.tension === '致命' ? 'var(--blood-light)' : 'var(--amber)' }}>
                ⚠ {sceneVibe.tension}
              </span></>)}
          </div>

          <div className="stage-letterbox bottom" />

          {/* DM 正在思考覆盖层（沉浸式等待状态） */}
          <DMThinkingOverlay visible={isLoading} />
        </div>

        {/* 对话气泡 + 选项 */}
        <div style={{ overflow: 'auto', maxHeight: '40vh' }}>
          {/* 剧场模式：当前正在播放的单条气泡（打字机）*/}
          {dialogueMode === 'stage' && dialogueQueue[dialogueIdx] && (
            <div
              onClick={advanceDialogue}
              style={{
                padding: '20px 28px 10px', maxWidth: 900, margin: '0 auto',
                cursor: 'pointer', userSelect: 'none',
              }}
            >
              <StageBubble seg={dialogueQueue[dialogueIdx]} typingText={typingText} typingDone={typingDone} />
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                marginTop: 6, fontFamily: 'var(--font-mono)', fontSize: 10,
                color: 'var(--parchment-dark)', letterSpacing: '.15em',
              }}>
                <span>{dialogueIdx + 1} / {dialogueQueue.length}</span>
                <span style={{ color: typingDone ? 'var(--arcane-light)' : 'var(--parchment-dark)' }}>
                  {typingDone ? '▸ 点击继续（空格/回车）' : '… 打字中（点击跳过）'}
                </span>
              </div>
            </div>
          )}

          {/* 聊天模式：完整历史日志，最下方自动滚动 */}
          {dialogueMode === 'chat' && (
            <div style={{
              padding: '10px 28px 0',
              maxWidth: 900,
              margin: '0 auto',
              minHeight: 0,
            }}>
              {logs.map(l => <LogLine key={l.id} entry={l} />)}
              <div ref={logsEndRef} />
            </div>
          )}

          {/* 编号选项列表 + 自由输入（仅 chat 模式可见）*/}
          <div className="crpg-dialogue" style={{ margin: '10px 24px 0', display: dialogueMode === 'stage' ? 'none' : 'block' }}>
            {pendingCheck ? (
              <div style={{ padding: 16, textAlign: 'center' }}>
                <div className="eyebrow" style={{ color: 'var(--arcane-light)' }}>🎲 {pendingCheck.check_type}检定 · DC {pendingCheck.dc}</div>
                <p style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)', fontSize: 13, marginTop: 6 }}>
                  {pendingCheck.context || '请投骰决定结果'}
                </p>
                <button className="btn-gold" onClick={handleDiceRoll} disabled={checkRolling} style={{ marginTop: 10, padding: '10px 24px', letterSpacing: '.2em' }}>
                  {checkRolling ? '✦ 骰子翻滚中… ✦' : '✦ 投掷 d20 ✦'}
                </button>
              </div>
            ) : (
              <>
                <div style={{ borderTop: '1px solid rgba(138,90,24,.35)', paddingTop: 12 }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 10,
                    color: 'var(--arcane-light)', letterSpacing: '.25em',
                    textTransform: 'uppercase', marginBottom: 8,
                    display: 'flex', alignItems: 'center', gap: 10,
                  }}>
                    <span style={{ flex: 0, color: 'var(--parchment-dark)' }}>▼</span>
                    <span>你的回应</span>
                    <span style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(127,232,248,.4), transparent)' }} />
                    {choices.length > 0 && (
                      <span style={{ color: 'var(--parchment-dark)' }}>1–{Math.min(choices.length, 9)} 快捷键</span>
                    )}
                  </div>

                  {choices.length > 0 && (
                    <div className="choice-list">
                      {choices.slice(0, 9).map((c, i) => {
                        const obj = typeof c === 'string' ? { text: c, tags: [] } : c
                        const preview = computeChoicePreview(obj, player)
                        return (
                          <button
                            key={i}
                            className={`choice ${obj.action ? 'action' : ''} ${obj.ended ? 'ended' : ''}`}
                            onMouseEnter={() => { try { JuiceAudio.hover() } catch (e) {} }}
                            onClick={() => {
                              try { JuiceAudio.select() } catch (e) {}
                              // 带 skill_check 标记的选项：前端直接进入掷骰流程
                              // （不要先把文本送给 DM，否则检定可能被跳过）
                              const checkTag = obj.skill_check
                                ? (obj.tags || []).find(t => t.dc != null)
                                : null
                              if (checkTag && checkTag.dc != null) {
                                const kind = (checkTag.kind || 'check').toLowerCase()
                                const skillZh = KIND_TO_SKILL_ZH[kind] || checkTag.label || '检定'
                                setPendingCheck({
                                  check_type: skillZh,
                                  dc: Number(checkTag.dc),
                                  character_id: player?.id,
                                  context: obj.text,  // 原选项文本，UI 会显示 + 检定后带给 DM
                                })
                                return
                              }
                              handleAction(obj.text)
                            }}
                            disabled={isLoading || (room && !isMySpeakTurn)}
                          >
                            <span className="idx">{i + 1}</span>
                            <span className="body">
                              {obj.tags?.length > 0 && (
                                <span className="tags">
                                  {obj.tags.map((t, ti) => (
                                    <span key={ti} className={`tag-mini tm-${t.kind || 'check'}`}>
                                      [{t.label}{t.dc ? ` · DC${t.dc}` : ''}]
                                    </span>
                                  ))}
                                </span>
                              )}
                              <span>{obj.text}</span>
                              {obj.skill_check && (
                                <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--parchment-dark)' }}>🎲</span>
                              )}
                            </span>
                            {preview && (
                              <div className="choice-preview">
                                <div className="pv-title">⚖ 结果预告</div>
                                {preview.rows.map((r, ri) => (
                                  <div key={ri} className="pv-row">
                                    <span>{r.label}</span>
                                    <b>{r.value}</b>
                                  </div>
                                ))}
                                {preview.hint && (
                                  <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px dashed rgba(138,90,24,.4)',
                                                fontSize: 10, color: 'rgba(232,200,160,.7)', fontStyle: 'italic' }}>
                                    {preview.hint}
                                  </div>
                                )}
                              </div>
                            )}
                          </button>
                        )
                      })}
                    </div>
                  )}

                  {/* 自由输入 */}
                  <div className="free-speak">
                    <span className="label">✎ 自由行动</span>
                    <input
                      ref={inputRef}
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAction() } }}
                      placeholder={isLoading ? '✦ 地下城主正在编织命运… ✦' : (room && !isMySpeakTurn ? '等待发言权…' : '描述你的行动，或按上方编号快捷回应')}
                      disabled={isLoading || (room && !isMySpeakTurn)}
                    />
                    <button
                      className="skill-chip"
                      onClick={() => handleAction()}
                      disabled={isLoading || !input.trim() || (room && !isMySpeakTurn)}
                      style={{
                        padding: '4px 12px', fontSize: 10,
                        background: 'linear-gradient(180deg, #3ec8d8, #14444e)',
                        color: '#04181c', borderColor: '#2a7a88',
                      }}
                    >➤ 发送</button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* ═══ 底部 HUD：队伍 + 目标 + 线索 ═══ */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr auto',
          gap: 12,
          padding: '10px 20px 12px',
          background: 'linear-gradient(180deg, transparent, rgba(10,6,4,.95) 40%, rgba(10,6,4,1) 100%)',
          borderTop: '1px solid rgba(138,90,24,.5)',
          boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
          flexShrink: 0,
        }}>
          {/* 队伍条 */}
          <div className="party-hud">
            {allMembers.map((p, idx) => {
              const derived = p.derived || {}
              const hpMax = derived.hp_max || p.hp_current || 1
              const pct = Math.max(0, Math.min(100, (p.hp_current / hpMax) * 100))
              const tone = pct < 34 ? 'low' : pct < 67 ? 'mid' : ''
              const active = p.isPlayer
              const ck = classKey(p.char_class)
              return (
                <div key={p.id || idx} className={`party-slot ${active ? 'active' : ''} ${tone}`}
                  title={`${p.name} HP ${p.hp_current}/${hpMax}`}
                  onClick={() => p.id && navigate(`/character/${p.id}`)}
                  style={{ cursor: p.id ? 'pointer' : 'default' }}>
                  <div className="frame" />
                  <div style={{ position: 'absolute', inset: 3, borderRadius: '50%', overflow: 'hidden' }}>
                    <Portrait cls={ck} size="sm" style={{ width: '100%', height: '100%' }} />
                    {pct > 0 && pct <= 25 && <span className="avatar-crack" />}
                  </div>
                  <div className="hp-micro"><div className="fill" style={{ width: `${pct}%` }} /></div>
                </div>
              )
            })}
          </div>

          {/* 目标 + 线索 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '6px 12px',
            background: 'linear-gradient(180deg, rgba(26,18,8,.8), rgba(10,6,4,.6))',
            border: '1px solid rgba(138,90,24,.4)',
            boxShadow: 'inset 0 1px 0 rgba(240,208,96,.12)',
            overflow: 'hidden',
          }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>◆ 目标</span>
            <span style={{ color: questLine ? 'var(--blood-light)' : 'var(--parchment-dark)', fontSize: 12, fontFamily: 'var(--font-body)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {questLine?.quest || '继续冒险'}
            </span>
            <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--arcane-light)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>❖ 线索 {clues.length}</span>
            <div style={{ display: 'flex', gap: 6, overflow: 'hidden' }}>
              {clues.map((c, i) => (
                <span key={i} style={{
                  fontSize: 11,
                  color: c.is_new ? 'var(--amber)' : 'var(--parchment-dark)',
                  fontStyle: 'italic', whiteSpace: 'nowrap',
                }}>
                  {i > 0 ? '· ' : ''}{c.text}
                  {c.is_new && (
                    <span style={{ fontSize: 8, color: 'var(--amber)', border: '1px solid var(--amber)', padding: '0 5px', letterSpacing: '.15em', fontFamily: 'var(--font-mono)', marginLeft: 4 }}>
                      NEW
                    </span>
                  )}
                </span>
              ))}
            </div>
          </div>

          {/* 快捷 */}
          <div style={{ display: 'flex', gap: 4 }}>
            <button className="skill-chip" style={{ padding: '6px 12px', fontSize: 10 }} onClick={() => setJournalOpen(true)}>☰ 卷宗</button>
          </div>
        </div>
      </div>

      {error && (
        <div style={{
          position: 'fixed', bottom: 16, left: '50%', transform: 'translateX(-50%)',
          padding: '8px 16px', background: 'rgba(139,32,32,.9)', color: '#fff',
          border: '1px solid var(--blood)', borderRadius: 4, zIndex: 999, fontSize: 12,
        }}>
          ⚠ {error}
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// LogLine — 单条日志渲染
// ═══════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════
// StageLeftFigure — 舞台左侧 silhouette，按当前说话者切换
// ═══════════════════════════════════════════════════════════

// ── 选项预告（choice-preview）────────────────────────────
// 根据 choice.tags 中的 kind+dc 估算玩家的成功率与修正值。
// 返回 null 时不渲染浮层；否则返回 {rows: [{label,value}], hint}
const KIND_TO_ABILITY = {
  insight: 'wis', perception: 'wis', wisdom: 'wis',
  persuade: 'cha', intim: 'cha', deception: 'cha', performance: 'cha', charisma: 'cha',
  athletic: 'str', strength: 'str',
  acrobat: 'dex', stealth: 'dex', sleight: 'dex', dex: 'dex',
  arcana: 'int', investigate: 'int', history: 'int', nature: 'int', religion: 'int',
  check: 'wis',  // 兜底
}
const KIND_TO_SKILL_ZH = {
  insight: '洞察', persuade: '劝说', intim: '威吓',
  perception: '察觉', athletic: '运动', acrobat: '特技',
  stealth: '隐匿', arcana: '奥秘', investigate: '调查',
  history: '历史', nature: '自然', religion: '宗教',
  deception: '欺瞒', performance: '表演', sleight: '巧手',
}
function computeChoicePreview(choice, player) {
  // 没有检定需求就不预告（纯角色扮演选项）
  const tag = (choice.tags || []).find(t => t.dc != null) || null
  if (!tag || !choice.skill_check || !player) return null

  const dc = Number(tag.dc)
  if (!Number.isFinite(dc)) return null

  const kind = (tag.kind || 'check').toLowerCase()
  const ability = KIND_TO_ABILITY[kind] || 'wis'
  const skillZh = KIND_TO_SKILL_ZH[kind] || tag.label || '检定'

  const mods = player.derived?.ability_modifiers || {}
  const abilMod = mods[ability] ?? 0
  const profBonus = player.derived?.proficiency_bonus ?? 2
  const proficient = (player.proficient_skills || []).includes(skillZh)
  const totalMod = abilMod + (proficient ? profBonus : 0)

  // 成功率 = P(d20 >= dc - totalMod)，d20 均匀，结果取值 [5%, 95%]
  const needed = dc - totalMod
  let successPct
  if (needed <= 1)       successPct = 95
  else if (needed >= 20) successPct = 5
  else                   successPct = Math.max(5, Math.min(95, (21 - needed) * 5))

  const sign = totalMod >= 0 ? '+' : ''
  const rows = [
    { label: '目标难度', value: `DC ${dc}` },
    { label: `${skillZh}修正`, value: `${sign}${totalMod}${proficient ? ' (熟)' : ''}` },
    { label: '成功率', value: `${successPct}%` },
  ]

  let hint = null
  if (choice.ended)      hint = '⚠ 此选项将结束当前场景'
  else if (choice.action) hint = '⚔ 攻击性行动 —— 可能触发战斗'
  else if (successPct >= 80) hint = '胜券在握'
  else if (successPct <= 30) hint = '九死一生'

  return { rows, hint }
}

function StageLeftFigure({ dialogueMode, currentSeg, companions, player, hasDmContent }) {
  // 决定当前左侧应展示的身份
  let role = 'dm'
  let speaker = '地下城主'
  let companionChar = null

  if (dialogueMode === 'stage' && currentSeg) {
    role = currentSeg.role
    speaker = currentSeg.speaker || '旁白'
    if (role === 'companion') {
      // 匹配队友
      companionChar = (companions || []).find(c =>
        c.name === speaker || c.name?.includes(speaker) || speaker?.includes(c.name)
      )
    }
  } else if (!hasDmContent) {
    return null  // chat 模式且没有 DM 内容时隐藏
  }

  // 配色
  const palette = {
    dm: { light: '#7a4fc4', dark: '#1a0a3a', txtColor: '#d8c8ff', plate: 'default', glow: 'rgba(168,144,232,.6)' },
    npc: { light: '#c44848', dark: '#3a0a0a', txtColor: '#ffcaca', plate: 'default', glow: 'rgba(240,80,80,.55)' },
    companion: { light: '#3ec8d8', dark: '#14444e', txtColor: '#d8eeff', plate: 'companion', glow: 'rgba(127,200,248,.55)' },
    dm_narration: { light: '#e8c070', dark: '#5a4018', txtColor: '#fff6d8', plate: 'gold', glow: 'rgba(240,208,96,.5)' },
  }
  // DM 旁白用金色，而不是紫色（紫色更适合 NPC）
  const effectiveRole = (role === 'dm') ? 'dm_narration' : role
  const p = palette[effectiveRole] || palette.dm
  const bg = `radial-gradient(circle at 40% 30%, ${p.light}, ${p.dark} 75%)`

  return (
    <div className="stage-figure left" style={{ '--c-light': p.light }}>
      <div className="silhouette" style={{ background: bg }}>
        {companionChar && window.Portrait ? null : (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'grid', placeItems: 'center',
            fontFamily: 'var(--font-display)', fontSize: 72,
            color: p.txtColor, textShadow: '0 4px 12px #000',
            filter: `drop-shadow(0 0 12px ${p.glow})`,
          }}>
            {companionChar
              ? (companionChar.name || '队').slice(0, 1)
              : role === 'dm' ? 'DM'
              : role === 'npc' ? (speaker || 'NPC').slice(0, 1)
              : (speaker || '?').slice(0, 1)}
          </div>
        )}
      </div>
      <div className="nameplate" style={p.plate === 'companion' ? {
        background: 'linear-gradient(180deg, #3ec8d8, #14444e)',
        color: '#04181c',
        boxShadow: '0 0 0 1px rgba(127,232,248,.6), 0 0 12px -2px var(--arcane-light)',
      } : p.plate === 'gold' ? {
        background: 'linear-gradient(180deg, #e8c070, #5a4018)',
        color: '#1a0a04',
        boxShadow: '0 0 0 1px rgba(240,208,96,.6), 0 0 12px -2px var(--amber)',
      } : undefined}>
        {role === 'dm' ? '❖ 旁白' :
         role === 'npc' ? `❖ ${speaker}` :
         role === 'companion' ? `◈ ${speaker}` :
         speaker}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// StageBubble — 剧场模式单条气泡（打字机）
// ═══════════════════════════════════════════════════════════

function StageBubble({ seg, typingText, typingDone }) {
  const role = seg.role || 'dm'
  const palette = {
    dm: { border: 'rgba(240,208,96,.45)', bg: 'linear-gradient(180deg, rgba(46,31,14,.65), rgba(26,18,8,.85))',
          accent: 'var(--amber)', textColor: 'var(--parchment)' },
    npc: { border: 'rgba(168,144,232,.55)', bg: 'linear-gradient(180deg, rgba(58,36,90,.45), rgba(26,16,44,.8))',
           accent: 'var(--amethyst-light)', textColor: '#d8c8ff' },
    companion: { border: 'rgba(127,200,248,.55)', bg: 'linear-gradient(180deg, rgba(20,40,62,.55), rgba(10,22,36,.85))',
                 accent: 'var(--arcane-light)', textColor: '#d8eeff' },
  }
  const p = palette[role] || palette.dm
  const isDm = role === 'dm'
  return (
    <div style={{
      position: 'relative',
      padding: '14px 18px 14px 22px',
      border: `1px solid ${p.border}`,
      borderLeft: `4px solid ${p.accent}`,
      background: p.bg,
      borderRadius: 6,
      boxShadow: 'inset 0 1px 0 rgba(255,255,255,.05), 0 4px 20px -6px rgba(0,0,0,.8)',
      minHeight: 64,
    }}>
      {!isDm && (
        <div style={{
          position: 'absolute', top: -11, left: 14,
          padding: '2px 10px',
          background: p.accent, color: '#0a0604',
          fontFamily: 'var(--font-display)', fontSize: 11,
          letterSpacing: '.15em', fontWeight: 700,
          borderRadius: 2,
          boxShadow: '0 2px 6px rgba(0,0,0,.6)',
        }}>
          ❖ {seg.speaker || 'NPC'}
        </div>
      )}
      <p style={{
        fontFamily: isDm ? 'var(--font-script)' : 'var(--font-body)',
        fontStyle: isDm ? 'italic' : 'normal',
        color: p.textColor,
        fontSize: isDm ? 15 : 14,
        lineHeight: 1.85,
        margin: 0,
        letterSpacing: '.03em',
        whiteSpace: 'pre-wrap',
      }}>
        {typingText}
        {!typingDone && (
          <span style={{
            display: 'inline-block',
            width: 6, height: 14,
            background: p.accent,
            marginLeft: 2,
            verticalAlign: 'text-bottom',
            animation: 'breathe 0.8s ease-in-out infinite',
          }} />
        )}
      </p>
    </div>
  )
}

function LogLine({ entry }) {
  const role = entry.role
  const txt = extractNarrative(entry.content)

  if (role === 'dm') {
    return (
      <p style={{
        fontFamily: 'var(--font-script)', fontStyle: 'italic',
        color: 'var(--parchment)', fontSize: 14, lineHeight: 1.7,
        margin: '8px 0', padding: '0 0 0 14px',
        borderLeft: '2px solid rgba(240,208,96,.45)',
      }}>{txt}</p>
    )
  }
  if (role === 'player') {
    return (
      <p style={{
        color: '#7fe8f8', fontSize: 13, fontFamily: 'var(--font-body)',
        margin: '6px 0', padding: '0 0 0 14px',
        borderLeft: '2px solid rgba(127,232,248,.5)',
      }}>► {txt}</p>
    )
  }
  if (role === 'companion') {
    return (
      <p style={{
        color: 'var(--emerald-light)', fontSize: 12,
        margin: '4px 0', padding: '0 0 0 14px', fontStyle: 'italic',
        borderLeft: '2px solid rgba(90,168,120,.5)',
      }}>❖ {txt}</p>
    )
  }
  if (role === 'dice') {
    return (
      <p style={{
        color: 'var(--amber)', fontSize: 12, fontFamily: 'var(--font-mono)',
        margin: '3px 0', padding: '2px 10px',
        background: 'rgba(10,6,4,.45)', borderRadius: 3,
        display: 'inline-block',
      }}>🎲 {txt}</p>
    )
  }
  // system / other
  return (
    <p style={{ color: 'var(--parchment-dark)', fontSize: 11, margin: '3px 0', fontStyle: 'italic', opacity: 0.7 }}>
      {txt}
    </p>
  )
}

// ── 对话拆段工具 ─────────────────────────────────────

/**
 * DM 叙述：整段作为一条气泡（不做句级切分）。
 * 若首行明显是 NPC 开场白，则抽出作为独立 NPC 气泡；其余归 DM 旁白。
 * 返回 [{role, speaker, text}]
 */
function splitDmNarrative(narrative) {
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
 * companion_reactions：按人分组合并，同一人的话合成一条气泡。
 * 兼容格式："[名字]: 台词" / "名字: 台词" / 换行分隔。
 */
function splitCompanionReactions(content, companionList = []) {
  if (!content) return []
  const text = String(content).trim()
  if (!text) return []

  // ——— speaker 识别 ———
  // 原正则 `([一-鿿·A-Za-z]{2,16})[:：]` 太宽松：
  //   "低声从牙缝里挤出一句：" 整坨被当 speaker（后面有冒号就能匹配）
  // 修法：无方括号的 candidate 必须在 companions 白名单里才接受；
  //      方括号 [名字] 保持宽松（玩家/模组显式标注）
  const namePattern = /(?:\[([^\]]{1,16})\]|([一-鿿·A-Za-z]{2,16}))[:：]\s*/g
  const companionNames = (companionList || [])
    .map(c => c?.name).filter(Boolean)
  const isKnownCompanion = (candidate) => companionNames.some(n =>
    n === candidate || n.includes(candidate) || candidate.includes(n))
  const matches = []
  let m
  while ((m = namePattern.exec(text)) !== null) {
    const candidate = (m[1] || m[2]).trim()
    // 方括号捕获：直接采用（模组/玩家显式标注）
    // 无方括号：必须命中队友白名单，否则跳过（避免"低声从牙缝里挤出一句"这种动作描述被误识别）
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

function extractNarrative(content) {
  if (!content) return ''
  const trimmed = String(content).trim()
  if (trimmed.startsWith('```') || trimmed.startsWith('{')) {
    try {
      const jsonStr = trimmed.replace(/^```(?:json)?\s*\n?/m, '').replace(/\n?\s*```\s*$/m, '').trim()
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

// ═══════════════════════════════════════════════════════════
// Modals —— 保留原版（Overlay / RestModal / JournalModal / PrepareSpellsModal）
// ═══════════════════════════════════════════════════════════

function Overlay({ children, onClose }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 500, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{ padding: 24, width: 500, maxWidth: '90vw', maxHeight: '85vh', display: 'flex', flexDirection: 'column', gap: 16, borderColor: 'var(--bark-light)' }}>
        {children}
      </div>
    </div>
  )
}

function RestModal({ onRest, onClose }) {
  return (
    <Overlay onClose={onClose}>
      <h3 style={{ color: 'var(--amber)', margin: 0, fontSize: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
        <RestIcon size={18} color="var(--amber)" /> 休息
      </h3>
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
        <h3 style={{ color: 'var(--amber)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <JournalIcon size={18} color="var(--amber)" /> 冒险日志
        </h3>
        <button onClick={onClose} style={{ color: 'var(--parchment-dark)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 200, maxHeight: '55vh', background: '#0a0604', borderRadius: 8, padding: 16, border: '1px solid var(--bark)' }}>
        {loading ? <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--amber)' }}>DM 正在撰写日志...</div>
         : text ? <p style={{ color: 'var(--parchment)', lineHeight: 1.9, fontSize: 14, whiteSpace: 'pre-wrap', margin: 0 }}>{text}</p>
         : <p style={{ color: 'var(--parchment-dark)', textAlign: 'center', marginTop: 32, fontSize: 13 }}>点击下方按钮生成本次冒险的叙述日志</p>}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onGenerate} disabled={loading}>{loading ? '生成中...' : '🔄 重新生成'}</button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>关闭</button>
      </div>
    </Overlay>
  )
}

function PrepareSpellsModal({ player, onSave, onClose }) {
  const derived = player.derived || {}
  const mods = derived.ability_modifiers || {}
  const spellMod = derived.spell_ability ? (mods[derived.spell_ability] || 0) : 0
  const maxPrepared = Math.max(1, player.level + spellMod)
  const [selected, setSelected] = useState(new Set(player.prepared_spells || []))
  const toggle = (s) => setSelected(prev => {
    const n = new Set(prev)
    if (n.has(s)) n.delete(s)
    else if (n.size < maxPrepared) n.add(s)
    return n
  })

  return (
    <Overlay onClose={onClose}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ color: 'var(--amethyst-light)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
            <BookIcon size={18} color="var(--amethyst-light)" /> 准备法术
          </h3>
          <p style={{ color: 'var(--parchment-dark)', fontSize: 12, margin: '4px 0 0' }}>上限：{selected.size}/{maxPrepared}</p>
        </div>
        <button onClick={onClose} style={{ color: 'var(--parchment-dark)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
        {(player.known_spells || []).map(spell => {
          const sel = selected.has(spell), can = sel || selected.size < maxPrepared
          return (
            <button
              key={spell}
              onClick={() => toggle(spell)}
              className="btn-fantasy"
              style={{
                textAlign: 'left', opacity: can ? 1 : 0.4,
                borderColor: sel ? 'var(--amethyst)' : undefined,
                background: sel ? 'rgba(138,79,212,0.15)' : undefined,
                color: sel ? 'var(--amethyst-light)' : undefined,
              }}
            >{sel ? '✓ ' : ''}{spell}</button>
          )
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-gold" style={{ padding: '8px 16px', fontSize: 13 }} onClick={() => onSave([...selected])}>确认（{selected.size}/{maxPrepared}）</button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>取消</button>
      </div>
    </Overlay>
  )
}
