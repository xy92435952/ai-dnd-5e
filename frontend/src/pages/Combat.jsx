import { useState, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { gameApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { useUser } from '../hooks/useUser'
import { useCombatLog } from '../hooks/useCombatLog'
import { useCombatRoom } from '../hooks/useCombatRoom'
import { useCombatSkillBar } from '../hooks/useCombatSkillBar'
import { useCombatSpells } from '../hooks/useCombatSpells'
import { useCombatAttackFlow } from '../hooks/useCombatAttackFlow'
import { useCombatSpellFlow } from '../hooks/useCombatSpellFlow'
import { useCombatPlayerActions } from '../hooks/useCombatPlayerActions'
import { useCombatSpecialActions } from '../hooks/useCombatSpecialActions'
import { useCombatAiTurns } from '../hooks/useCombatAiTurns'
import { useCombatTurnControls } from '../hooks/useCombatTurnControls'
import { useCombatLoader } from '../hooks/useCombatLoader'
import { useCombatTargeting } from '../hooks/useCombatTargeting'
import { useCombatDerivedState } from '../hooks/useCombatDerivedState'
import { useCombatPrediction } from '../hooks/useCombatPrediction'
import { useCombatPageActions } from '../hooks/useCombatPageActions'
import DiceRollerOverlay from '../components/DiceRollerOverlay'
import { JuiceAudio } from '../juice'
import MultiplayerTurnBar from '../components/combat/MultiplayerTurnBar'
import TurnBanner from '../components/combat/TurnBanner'
import InitiativeRibbon from '../components/combat/InitiativeRibbon'
import CombatStage from '../components/combat/CombatStage'
import CombatHud from '../components/combat/CombatHud'
import CombatOverlays from '../components/combat/CombatOverlays'
import { isPlayerCombatTurn } from '../utils/combat'

const GRID_W_TOTAL = 20
const GRID_H_TOTAL = 12
const VIEW_W = 12
const VIEW_H = 8

function ignoreOptionalEffect(fn) {
  try {
    fn()
  } catch {
    // Optional audio / haptics may fail in tests or unsupported browsers.
  }
}

export default function Combat() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { showDice } = useGameStore()

  // ── 多人联机相关 ──
  const { userId: myUserId } = useUser()
  const { room, setRoom, myCharacterId } = useCombatRoom(sessionId, myUserId)

  const [combat, setCombat] = useState(null)
  const { logs, setLogs, addLog, logsEndRef } = useCombatLog()
  const [isProcessing, setIsProcessing] = useState(false)
  const [combatOver, setCombatOver] = useState(null) // null | 'victory' | 'defeat'
  const [error, setError] = useState('')

  // 瞄准 / 视觉模式集合（selectedTarget / moveMode / isRanged / showThreat / aoePreview / aoeHover / helpMode）
  // 互斥切换（如 toggleMoveMode）也封装在 hook 里，免得这里散落 3 行 setter
  const {
    selectedTarget, setSelectedTarget,
    moveMode, setMoveMode,
    isRanged, setIsRanged,
    showThreat, setShowThreat,
    aoePreview, setAoePreview,
    aoeHover,   setAoeHover,
    setHelpMode,
    clearAoePreview,
  } = useCombatTargeting()

  // 法术面板
  const [spellModalOpen, setSpellModalOpen] = useState(false)
  const spells = useCombatSpells(sessionId)
  const [playerSpellSlots, setPlayerSpellSlots] = useState({})
  const [playerKnownSpells, setPlayerKnownSpells] = useState([])
  const [playerCantrips, setPlayerCantrips] = useState([])
  const [playerId, setPlayerId] = useState(null)

  // 回合行动状态（从服务端同步）
  const [turnState, setTurnState] = useState(null)

  // P0/P1 职业特性状态
  const [smitePrompt, setSmitePrompt] = useState(null) // {show, lastAttackHit, targetId}
  const [playerClass, setPlayerClass] = useState('')
  const [playerLevel, setPlayerLevel] = useState(1)
  const [classResources, setClassResources] = useState({})
  const [playerSubclass, setPlayerSubclass] = useState('')
  const [playerSubclassEffects, setPlayerSubclassEffects] = useState({})
  const [maneuverModalOpen, setManeuverModalOpen] = useState(false)
  const [reactionPrompt, setReactionPrompt] = useState(null)

  // 先攻骰子动画标记（仅第一轮第一次显示）
  const [initiativeShown, setInitiativeShown] = useState(false)

  // v0.10 新增 — 完整 session 数据（供底部 HUD 展示）
  const [session, setSession] = useState(null)
  const skillBarV10 = useCombatSkillBar({
    sessionId,
    playerId,
    refreshKey: playerSpellSlots,
  })
  // v0.10 — 伤害飘字（保留 floats 占位，目前未使用）
  const floats = []

  const aiTimer = useRef(null)
  const processingRef = useRef(false)

  const prediction = useCombatPrediction({
    sessionId,
    playerId,
    selectedTarget,
    playerClass,
    isRanged,
  })

  const isPlayerTurn = useCallback((c) => {
    return isPlayerCombatTurn(c)
  }, [])

  const { triggerAiTurn } = useCombatAiTurns({
    sessionId,
    processingRef,
    setIsProcessing,
    setCombat,
    setTurnState,
    setReactionPrompt,
    setCombatOver,
    addLog,
    showDice,
  })

  const { loadCombat } = useCombatLoader({
    sessionId,
    initiativeShown,
    aiTimer,
    setCombat,
    setSession,
    setPlayerId,
    setPlayerSpellSlots,
    setPlayerKnownSpells,
    setPlayerCantrips,
    setPlayerClass,
    setPlayerLevel,
    setClassResources,
    setPlayerSubclass,
    setPlayerSubclassEffects,
    setTurnState,
    setLogs,
    setInitiativeShown,
    setError,
    showDice,
    triggerAiTurn,
    isPlayerTurn,
  })

  const { handleEndTurn } = useCombatTurnControls({
    sessionId,
    combat,
    isProcessing,
    isPlayerTurn,
    processingRef,
    aiTimer,
    setIsProcessing,
    setMoveMode,
    setHelpMode,
    setError,
    setCombat,
    setTurnState,
    setCombatOver,
    addLog,
    triggerAiTurn,
  })

  const handleAttack = useCombatAttackFlow({
    sessionId,
    playerId,
    selectedTarget,
    isRanged,
    combat,
    isProcessing,
    isPlayerTurn,
    processingRef,
    setIsProcessing,
    setError,
    showDice,
    addLog,
    setTurnState,
    setCombat,
    setSelectedTarget,
    setSmitePrompt,
    setCombatOver,
  })

  const handleCastSpell = useCombatSpellFlow({
    sessionId,
    playerId,
    selectedTarget,
    isProcessing,
    processingRef,
    setIsProcessing,
    setSpellModalOpen,
    setError,
    setTurnState,
    setCombat,
    setPlayerSpellSlots,
    addLog,
    setSelectedTarget,
    setCombatOver,
    showDice,
  })

  const {
    handleClassFeature,
    handleDodge,
    handleDash,
    handleDisengage,
  } = useCombatPlayerActions({
    sessionId,
    playerId,
    combat,
    isProcessing,
    isPlayerTurn,
    processingRef,
    setIsProcessing,
    setError,
    setTurnState,
    setClassResources,
    setCombat,
    showDice,
    addLog,
  })

  const {
    handleSmite,
    handleReaction,
    handleManeuver,
  } = useCombatSpecialActions({
    sessionId,
    selectedTarget,
    isProcessing,
    smitePrompt,
    playerSubclassEffects,
    processingRef,
    setIsProcessing,
    setError,
    setSmitePrompt,
    setPlayerSpellSlots,
    setTurnState,
    setClassResources,
    setCombat,
    setReactionPrompt,
    setCombatOver,
    triggerAiTurn,
    showDice,
    addLog,
  })

  const {
    entityPositions,
    entities,
    playerPos,
    cam,
    currentTurnEntry,
    isPlayerTurn: isPlayerTurnV10,
    isMyTurnMP,
    currentTurnLabel,
    walls,
    hazards,
    selectedTargetEntity,
    initiativeChips,
    skillBar,
    playerAvailableSpells,
    threatCells,
    aoeCells,
  } = useCombatDerivedState({
    combat,
    room,
    myCharacterId,
    playerId,
    selectedTarget,
    showThreat,
    aoePreview,
    aoeHover,
    spells,
    playerKnownSpells,
    playerCantrips,
    playerClass,
    skillBarV10,
    gridWidth: GRID_W_TOTAL,
    gridHeight: GRID_H_TOTAL,
    viewWidth: VIEW_W,
    viewHeight: VIEW_H,
  })

  const { onWsEvent, onSkillClick, handleMoveTo, handleSpellHover } = useCombatPageActions({
    sessionId,
    setRoom,
    myCharacterId,
    moveMode,
    isProcessing,
    isPlayerTurn: isPlayerTurnV10,
    selectedTarget,
    entityPositions,
    playerPos,
    setError,
    setCombat,
    setTurnState,
    setSpellModalOpen,
    setHelpMode,
    handleAttack,
    handleDash,
    handleDisengage,
    handleDodge,
    handleClassFeature,
    setMoveMode,
    setAoePreview,
    setAoeHover,
    clearAoePreview,
    onLoadCombat: loadCombat,
  })

  useWebSocket(room ? sessionId : null, onWsEvent)

  // ── 渲染 ───────────────────────────────────────────────
  if (!combat) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
        {error
          ? <p style={{ color: 'var(--red-light)' }}>{error}</p>
          : <p className="animate-pulse" style={{ color: 'var(--gold)' }}>加载战斗...</p>}
      </div>
    )
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden',
      background: 'linear-gradient(180deg, #06040a 0%, #0a0604 100%)',
      position: 'relative', zIndex: 1,
    }}>
      <DiceRollerOverlay />

      <MultiplayerTurnBar
        room={room}
        currentTurnLabel={currentTurnLabel}
        isMyTurnMP={isMyTurnMP}
      />

      <TurnBanner
        roundNumber={combat?.round_number || 1}
        currentTurnName={currentTurnEntry?.name}
        combatOver={combatOver}
        showThreat={showThreat}
        onToggleThreat={() => { setShowThreat(v => !v); ignoreOptionalEffect(() => JuiceAudio.click()) }}
      />

      <InitiativeRibbon
        initiativeChips={initiativeChips}
        onSelectTarget={setSelectedTarget}
      />

      <CombatStage
        viewWidth={VIEW_W}
        viewHeight={VIEW_H}
        cam={cam}
        walls={walls}
        hazards={hazards}
        entityPositions={entityPositions}
        entities={entities}
        selectedTarget={selectedTarget}
        selectedTargetEntity={selectedTargetEntity}
        currentTurnCharacterId={currentTurnEntry?.character_id}
        threatCells={threatCells}
        aoeCells={aoeCells}
        moveMode={moveMode}
        aoePreview={aoePreview}
        aoeHover={aoeHover}
        playerId={playerId}
        prediction={prediction}
        floats={floats}
        combatOver={combatOver}
        onSelectTarget={setSelectedTarget}
        onMoveTo={handleMoveTo}
        onAoeHover={setAoeHover}
        onReturn={async () => { await gameApi.endCombat?.(sessionId); navigate(`/adventure/${sessionId}`) }}
      />

      <CombatHud
        session={session}
        playerClass={playerClass}
        playerSubclass={playerSubclass}
        playerLevel={playerLevel}
        turnState={turnState}
        skillBar={skillBar}
        selectedTarget={selectedTarget}
        entities={entities}
        logs={logs}
        logsEndRef={logsEndRef}
        playerSpellSlots={playerSpellSlots}
        isProcessing={isProcessing}
        isPlayerTurn={isPlayerTurnV10}
        moveMode={moveMode}
        isRanged={isRanged}
        onSkillClick={onSkillClick}
        onEndTurn={handleEndTurn}
        onToggleMove={() => setMoveMode(m => !m)}
        onToggleRanged={() => setIsRanged(r => !r)}
        onReturnAdventure={() => navigate(`/adventure/${sessionId}`)}
        onForceEndCombat={async () => { if (confirm('强制结束战斗？')) { await gameApi.endCombat?.(sessionId); navigate(`/adventure/${sessionId}`) } }}
      />

      <CombatOverlays
        smitePrompt={smitePrompt}
        playerSpellSlots={playerSpellSlots}
        onSmite={handleSmite}
        onCancelSmite={() => setSmitePrompt(null)}
        spellModalOpen={spellModalOpen}
        playerAvailableSpells={playerAvailableSpells}
        playerCantrips={playerCantrips}
        onCastSpell={handleCastSpell}
        onCloseSpell={() => { setSpellModalOpen(false); clearAoePreview() }}
        onSpellHover={handleSpellHover}
        maneuverModalOpen={maneuverModalOpen}
        playerSubclassEffects={playerSubclassEffects}
        classResources={classResources}
        onUseManeuver={handleManeuver}
        onCloseManeuver={() => setManeuverModalOpen(false)}
        reactionPrompt={reactionPrompt}
        onReact={handleReaction}
        onCancelReaction={() => setReactionPrompt(null)}
        error={error}
      />
    </div>
  )
}
