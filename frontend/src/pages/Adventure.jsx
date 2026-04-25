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
import { useUser } from '../hooks/useUser'
import { useSkillCheck } from '../hooks/useSkillCheck'
import { useDialogueFlow } from '../hooks/useDialogueFlow'
import { useAdventureSession } from '../hooks/useAdventureSession'
import RestModal from '../components/adventure/RestModal'
import JournalModal from '../components/adventure/JournalModal'
import PrepareSpellsModal from '../components/adventure/PrepareSpellsModal'
import LogLine from '../components/adventure/LogLine'
import StageBubble from '../components/adventure/StageBubble'
import StageLeftFigure from '../components/adventure/StageLeftFigure'
import { splitDmNarrative, splitCompanionReactions } from '../utils/dialogue'
import { computeChoicePreview } from '../utils/skillCheck'

export default function Adventure() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { isLoading, setIsLoading, showDice } = useGameStore()

  // session / player / companions + loadSession 都在 useAdventureSession 里
  // logs 留给 Adventure 自己（因为 addLog 在太多地方被调用，state 留在这里最简单）
  // onLoaded 回调在 hook 解构后定义，通过 ref 传递（见 hook 内部）
  const [logs, setLogs] = useState([])
  const [input, setInput] = useState('')
  const [choices, setChoices] = useState([])         // 当前回合的对话选项
  const [error, setError] = useState('')
  const [restOpen, setRestOpen] = useState(false)
  const [prepareOpen, setPrepareOpen] = useState(false)
  const [journalOpen, setJournalOpen] = useState(false)
  const [journalText, setJournalText] = useState('')
  const [journalLoading, setJournalLoading] = useState(false)

  // 对话流系统（v0.10.1）— 状态机 + 打字机 + 空格推进都在 useDialogueFlow 里
  // Adventure 只需要：enterStage(queue) 启动剧场；advance() 推进；读 dialogueMode/typingText 渲染

  const logsEndRef = useRef(null)
  const inputRef = useRef(null)

  // ── 多人联机 ──
  const [room, setRoom] = useState(null)
  const { userId: myUserId } = useUser()

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

  // ════════════════════════════════════════════════════════
  // hooks 顺序约定（必须严格按依赖链声明，否则 useCallback / useEffect
  // 的 deps 数组会触发 TDZ ReferenceError，整页白屏）：
  //   1. addLog                        基础 log 操作
  //   2. useDialogueFlow               对话流（依赖 addLog）
  //   3. handleSessionLoaded 函数      闭包内引用下面的 hook 返回值，函数本身定义无副作用
  //   4. useAdventureSession           暴露 session / player / companions / loadSession
  //   5. useSkillCheck                 依赖 player.id（player 来自步骤 4）
  //   6. buildDialogueQueue            依赖 splitDmNarrative / splitCompanionReactions（纯函数）
  //   7. onWsEvent + useWebSocket      依赖 companions / buildDialogueQueue / loadSession 等
  //   8. 各种 useEffect                依赖 pendingCheck / dialogue 等
  // ════════════════════════════════════════════════════════

  // 1. addLog
  const addLog = useCallback((role, content, logType = 'narrative', extra = {}) => {
    setLogs(prev => [...prev, {
      id: `${role}-${Date.now()}-${Math.random()}`,
      role, content, log_type: logType,
      created_at: new Date().toISOString(), ...extra
    }])
  }, [])

  // 2. 剧场模式
  const {
    dialogueMode, dialogueQueue, dialogueIdx, typingText, typingDone,
    showHistory, setShowHistory,
    enterStage: enterDialogueStage,
    advance: advanceDialogue,
  } = useDialogueFlow({ addLog })

  // 防止同一 session 在客户端反复触发"开场剧场"（loadSession 会在 mount /
  // WS 重连 / dm_responded 多次调用，没有这个 ref 每次都 enterDialogueStage 一遍）
  const openingTriggeredRef = useRef(new Set())

  // 3. handleSessionLoaded —— 函数定义不触发 body 内部 TDZ；body 中引用的 setPendingCheck /
  //    setChoices 在调用时（loadSession async 完成）必然已初始化
  const handleSessionLoaded = (data) => {
    // ── 恢复 last_turn：页面刷新 / WS 重连后能看到之前的选项和检定 ──
    const lt = data.game_state?.last_turn
    if (lt) {
      const isMine = !data.is_multiplayer || !lt.last_actor_user_id || lt.last_actor_user_id === myUserId
      if (isMine) {
        if (Array.isArray(lt.player_choices) && lt.player_choices.length) {
          setChoices(lt.player_choices)
        }
        if (lt.needs_check?.required) {
          setPendingCheck(lt.needs_check)
        }
      } else {
        setChoices([])
        setPendingCheck(null)
      }
    }

    // ── 首次进入检测：恰好 1 条开场叙事 + 对话队列空 → 自动启动剧场模式 ──
    // 注意要先决定要不要剧场，再决定 setLogs，因为如果触发剧场，得**剔除**那条 [开场] log，
    // 否则剧场播完 advance 会再写一条 DM log，logs 里就会有两条同样内容的 DM 气泡。
    let displayLogs = data.logs || []
    const sid = data.session_id || sessionId

    if (
      !openingTriggeredRef.current.has(sid) &&
      dialogueQueue.length === 0
    ) {
      const dmNarratives = displayLogs.filter(l =>
        (l.role === 'dm' || l.role === 'system') &&
        (l.log_type === 'narrative' || !l.log_type) &&
        l.content
      )
      if (dmNarratives.length === 1) {
        const opening = dmNarratives[0]
        const text = String(opening.content || '').replace(/^\[开场\]\s*/, '')
        if (text) {
          openingTriggeredRef.current.add(sid)
          // 把 [开场] 这条从展示 logs 里抹掉 —— 剧场播完 advance 会自然加回（不带前缀）
          displayLogs = displayLogs.filter(l => l.id !== opening.id)
          enterDialogueStage([{ speaker: 'DM', role: 'dm', text, color: 'gold' }])
        }
      }
    }

    setLogs(displayLogs)
  }

  // 4. session 加载（onLoaded 通过 ref 转发）
  const {
    session, setSession,
    player, setPlayer,
    companions, setCompanions,
    loadSession,
  } = useAdventureSession({
    sessionId,
    onLoaded: handleSessionLoaded,
    onError: (e) => setError(e.message),
  })

  // 5. 技能检定（依赖 player.id）
  const { pendingCheck, setPendingCheck, checkRolling, rollPending } = useSkillCheck({
    sessionId,
    playerId: player?.id,
    addLog,
  })

  // 6. 把 DM 响应拼成剧场队列（HTTP 响应和 WS dm_responded 都用这个）
  const buildDialogueQueue = useCallback((narrative, companionReactions, companionList) => {
    const queue = []
    if (narrative) {
      splitDmNarrative(narrative).forEach(seg => {
        queue.push({
          speaker: seg.speaker || 'DM',
          role: seg.role || 'dm',
          text: seg.text,
          color: seg.color,
        })
      })
    }
    if (companionReactions) {
      splitCompanionReactions(companionReactions, companionList || []).forEach(seg => {
        queue.push({ speaker: seg.speaker, role: 'companion', text: seg.text, color: seg.color })
      })
    }
    return queue
  }, [])

  // 7. WS 事件处理（依赖前面所有 hook 的产物）
  const onWsEvent = useCallback((event) => {
    switch (event.type) {
      case 'dm_thinking_start':
        if (event.by_user_id && event.by_user_id !== myUserId) {
          setIsLoading(true)
        }
        break
      case 'dm_responded': {
        const isMe = event.by_user_id && event.by_user_id === myUserId
        if (!isMe) {
          setIsLoading(false)
          const queue = buildDialogueQueue(event.narrative, event.companion_reactions, companions)
          if (queue.length > 0) enterDialogueStage(queue)
        }
        loadSession()
        break
      }
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
  }, [sessionId, myUserId, companions, buildDialogueQueue, enterDialogueStage, loadSession, setIsLoading])

  const { connected: wsConnected, send: wsSend } = useWebSocket(room ? sessionId : null, onWsEvent)

  // WS 重连补漏（断线期间错过的广播不会 replay）
  const prevWsConnectedRef = useRef(false)
  useEffect(() => {
    if (!room) return
    const wasDisconnected = !prevWsConnectedRef.current
    if (wsConnected && wasDisconnected && session) {
      loadSession()
    }
    prevWsConnectedRef.current = wsConnected
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsConnected, room])

  const currentSpeakerUid = room?._currentSpeaker
  const isMySpeakTurn = !room || !currentSpeakerUid || currentSpeakerUid === myUserId
  const currentSpeakerName = (room?.members || []).find(m => m.user_id === currentSpeakerUid)?.display_name

  // 轮到自己时：音效提示 + 标题栏闪烁（仅多人）
  const prevSpeakerRef = useRef(null)
  useEffect(() => {
    if (!room) { prevSpeakerRef.current = null; return }
    const prev = prevSpeakerRef.current
    prevSpeakerRef.current = currentSpeakerUid
    if (prev && prev !== myUserId && currentSpeakerUid === myUserId) {
      try { JuiceAudio.turn() } catch (e) {}
      const original = document.title
      let flipCount = 0
      const timer = setInterval(() => {
        document.title = flipCount % 2 === 0 ? '⚔ 轮到你了 · 说点什么' : original
        flipCount++
        if (flipCount >= 8) {
          clearInterval(timer)
          document.title = original
        }
      }, 600)
      return () => { clearInterval(timer); document.title = original }
    }
  }, [currentSpeakerUid, myUserId, room])

  // 8. UI 副作用 effect
  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [logs, pendingCheck])

  // refresh helper（必须在 useAdventureSession 之后，因为它用 setSession/setPlayer/setCompanions）
  const refreshCharacters = async () => {
    try {
      const data = await gameApi.getSession(sessionId)
      setSession(data); setPlayer(data.player); setCompanions(data.companions || [])
    } catch {}
  }

  // ── 主行动 ──
  const handleAction = async (overrideText) => {
    const text = (overrideText ?? input).trim()
    if (!text || isLoading) return
    setInput(''); setError(''); setPendingCheck(null); setChoices([]); setIsLoading(true)
    addLog('player', text, 'narrative')
    try {
      const resp = await gameApi.action({ session_id: sessionId, action_text: text })

      // 构建对话队列（DM 叙述拆段 + 队友反应按"[名字]:"拆开）
      const queue = buildDialogueQueue(resp.narrative, resp.companion_reactions, companions)

      if (resp.dice_display?.length) {
        for (const d of resp.dice_display) {
          addLog('dice',
            `${d.label || '骰子'}：${d.raw}${d.modifier ? ` + ${d.modifier}` : ''} = ${d.total}${d.against ? ` vs ${d.against}` : ''} ${d.outcome ? `→ ${d.outcome}` : ''}`,
            'dice', { dice_result: d })
        }
      }
      // checkRolling 由 useSkillCheck 内部管理；这里只设 pendingCheck 触发 UI
      if (resp.needs_check?.required) setPendingCheck(resp.needs_check)
      if (resp.player_choices?.length) setChoices(resp.player_choices)

      // 启动剧场模式播放队列
      if (queue.length > 0) {
        enterDialogueStage(queue)
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

  // 打字机效果 + 空格推进 + advanceDialogue 全部抽到 useDialogueFlow

  // ── 检定流（核心逻辑已抽到 useSkillCheck） ──
  const handleDiceRoll = async () => {
    const autoMsg = await rollPending()
    if (autoMsg) {
      // 延迟 800ms 让玩家看清骰子结果再进入 DM 叙事
      setTimeout(() => handleAction(autoMsg), 800)
    }
    inputRef.current?.focus()
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
          <span>{isMySpeakTurn ? '✦ 轮到你了 · 说一句你的行动，DM 会回应并自动轮到下一位' : `等待 ${currentSpeakerName || '其他玩家'} 发言…`}</span>
          <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {isMySpeakTurn && currentSpeakerUid && (
              <button onClick={() => wsSend({ type: 'speak_done' })}
                title="跳过本轮，不说话也不发起行动"
                style={{ padding: '3px 10px', fontSize: 11, background: 'transparent', color: 'var(--amber)', border: '1px solid var(--amber)', borderRadius: 3, cursor: 'pointer' }}>
                跳过本轮 ↷
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
