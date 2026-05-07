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
 *   - 3D 骰子（DiceRollerOverlay）
 *   - pendingCheck 检定流
 *   - PrepareSpellsModal / JournalModal / RestModal（保留定义）
 */
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { gameApi, roomsApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import { useWebSocket } from '../hooks/useWebSocket'
import DiceRollerOverlay from '../components/DiceRollerOverlay'
import DialogueHistoryView from '../components/DialogueHistoryView'
import { useUser } from '../hooks/useUser'
import { useSkillCheck } from '../hooks/useSkillCheck'
import { useDialogueFlow } from '../hooks/useDialogueFlow'
import { useAdventureSession } from '../hooks/useAdventureSession'
import { useAdventureActions } from '../hooks/useAdventureActions'
import { useAdventureMultiplayer } from '../hooks/useAdventureMultiplayer'
import { useDialogueWsSync } from '../hooks/useDialogueWsSync'
import RestModal from '../components/adventure/RestModal'
import JournalModal from '../components/adventure/JournalModal'
import PrepareSpellsModal from '../components/adventure/PrepareSpellsModal'
import MultiplayerSpeakBar from '../components/adventure/MultiplayerSpeakBar'
import AdventureTopBar from '../components/adventure/AdventureTopBar'
import AdventureStage from '../components/adventure/AdventureStage'
import DialoguePanel from '../components/adventure/DialoguePanel'
import AdventureBottomHud from '../components/adventure/AdventureBottomHud'
import { splitDmNarrative, splitCompanionReactions } from '../utils/dialogue'

export default function Adventure() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { isLoading, setIsLoading } = useGameStore()

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

  const { userId: myUserId } = useUser()
  const [room, setRoom] = useState(null)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const r = await roomsApi.get(sessionId)
        if (mounted && r?.is_multiplayer) {
          setRoom({ ...r, _currentSpeaker: r.current_speaker_user_id })
        }
      } catch {
        // Room lookup is best-effort; single-player sessions do not need it.
      }
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

  // 7. WS 事件处理 —— 整段 switch 抽到 useDialogueWsSync 里
  const onWsEvent = useDialogueWsSync({
    sessionId, myUserId, companions,
    buildDialogueQueue, enterDialogueStage, loadSession,
    setIsLoading, setRoom,
  })

  const { connected: wsConnected, send: wsSend } = useWebSocket(room ? sessionId : null, onWsEvent)
  const {
    currentSpeakerUid,
    isMySpeakTurn,
    currentSpeakerName,
  } = useAdventureMultiplayer({
    room,
    sessionId,
    myUserId,
    wsConnected,
    session,
    loadSession,
  })

  // 8. UI 副作用 effect
  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [logs, pendingCheck])

  const {
    handleAction,
    handleDiceRoll,
    handleRest,
    handleGenerateJournal,
    handlePrepareSpells,
    handleCheckpoint,
  } = useAdventureActions({
    sessionId,
    playerId: player?.id,
    isLoading,
    input,
    inputRef,
    companions,
    navigate,
    addLog,
    setChoices,
    setError,
    setInput,
    setIsLoading,
    setJournalLoading,
    setJournalText,
    setPendingCheck,
    setPlayer,
    setPrepareOpen,
    setRestOpen,
    setSession,
    setCompanions,
    buildDialogueQueue,
    enterDialogueStage,
    rollPending,
  })

  // 打字机效果 + 空格推进 + advanceDialogue 全部抽到 useDialogueFlow

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

      <MultiplayerSpeakBar
        room={room}
        isMySpeakTurn={isMySpeakTurn}
        currentSpeakerUid={currentSpeakerUid}
        currentSpeakerName={currentSpeakerName}
        onSkipTurn={() => wsSend({ type: 'speak_done' })}
        onAiTakeover={async () => {
          try {
            await gameApi.aiTakeover(sessionId)
          } catch (e) {
            setError(e.message || '无法触发 AI 代演')
          }
        }}
      />

      <AdventureTopBar
        session={session}
        player={player}
        isLoading={isLoading}
        canPrepareSpells={canPrepareSpells}
        onHome={() => navigate('/')}
        onCheckpoint={handleCheckpoint}
        onShowHistory={() => setShowHistory(true)}
        onOpenJournal={() => { setJournalOpen(true); if (!journalText) handleGenerateJournal() }}
        onOpenRest={() => setRestOpen(true)}
        onOpenPrepare={() => setPrepareOpen(true)}
        onOpenCharacter={() => navigate(`/character/${player.id}`)}
      />

      {/* ═══ 主舞台区 ═══ */}
      <div style={{ flex: 1, display: 'grid', gridTemplateRows: '1fr auto auto', overflow: 'hidden', minHeight: 0 }}>

        <AdventureStage
          dialogueMode={dialogueMode}
          currentSeg={dialogueQueue[dialogueIdx]}
          companions={companions}
          player={player}
          hasDmContent={!!latestDmLine}
          sceneVibe={sceneVibe}
          isLoading={isLoading}
        />

        <DialoguePanel
          dialogueMode={dialogueMode}
          dialogueQueue={dialogueQueue}
          dialogueIdx={dialogueIdx}
          typingText={typingText}
          typingDone={typingDone}
          onAdvanceDialogue={advanceDialogue}
          logs={logs}
          logsEndRef={logsEndRef}
          pendingCheck={pendingCheck}
          checkRolling={checkRolling}
          onDiceRoll={handleDiceRoll}
          choices={choices}
          player={player}
          setPendingCheck={setPendingCheck}
          onAction={handleAction}
          input={input}
          setInput={setInput}
          inputRef={inputRef}
          isLoading={isLoading}
          room={room}
          isMySpeakTurn={isMySpeakTurn}
        />

        <AdventureBottomHud
          allMembers={allMembers}
          questLine={questLine}
          clues={clues}
          onOpenCharacter={(id) => navigate(`/character/${id}`)}
          onOpenJournal={() => setJournalOpen(true)}
        />
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
