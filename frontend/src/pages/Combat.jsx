import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { gameApi, roomsApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { useUser } from '../hooks/useUser'
import { useCombatTargeting } from '../hooks/useCombatTargeting'
import DiceRollerOverlay, { rollDice3D } from '../components/DiceRollerOverlay'
import Sprite from '../components/Sprite'
import { JuiceAudio, shake as JuiceShake } from '../juice'
import {
  ShieldIcon, SwordIcon, SkullIcon, DiceD20Icon,
  AttackIcon, SpellIcon, MoveIcon, DefendIcon, DashIcon,
  DisengageIcon, HelpIcon, OffhandIcon, BackIcon, HeartIcon,
} from '../components/Icons'
import SpellModal from '../components/combat/SpellModal'
import ManeuverModal from '../components/combat/ManeuverModal'
import CombatLogEntry from '../components/combat/CombatLogEntry'
import { SKILL_INFO } from '../data/combat'
import { computeSkillStats, aoeRadiusCells, applyHpUpdate } from '../utils/combat'

const GRID_COLS = 20
const GRID_ROWS = 20
const CELL = 36 // px per cell — smaller to fit more on screen

export default function Combat() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { showDice } = useGameStore()

  // ── 多人联机相关 ──
  const [room, setRoom] = useState(null)  // null = 单人模式；非空 = 多人房间信息
  const { userId: myUserId } = useUser()
  // 我控制的角色 id（多人：从 SessionMember 推；单人：=playerId）
  const [myCharacterId, setMyCharacterId] = useState(null)

  const [combat, setCombat] = useState(null)
  const [logs, setLogs] = useState([])
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
    helpMode,   setHelpMode,
    clearAoePreview,
  } = useCombatTargeting()

  // 法术面板
  const [spellModalOpen, setSpellModalOpen] = useState(false)
  const [spells, setSpells] = useState([])
  const [playerSpellSlots, setPlayerSpellSlots] = useState({})
  const [playerKnownSpells, setPlayerKnownSpells] = useState([])
  const [playerCantrips, setPlayerCantrips] = useState([])
  const [playerId, setPlayerId] = useState(null)

  // 回合行动状态（从服务端同步）
  const [turnState, setTurnState] = useState(null)

  // 两步攻击流程状态
  // attackPhase: 'idle' | 'rolling_d20' | 'hit_result' | 'rolling_damage' | 'done'
  const [attackPhase, setAttackPhase] = useState('idle')
  const [pendingAttack, setPendingAttack] = useState(null)

  // P0/P1 职业特性状态
  const [smitePrompt, setSmitePrompt] = useState(null) // {show, lastAttackHit, targetId}
  const [playerClass, setPlayerClass] = useState('')
  const [playerLevel, setPlayerLevel] = useState(1)
  const [classResources, setClassResources] = useState({})
  const [playerSubclass, setPlayerSubclass] = useState('')
  const [playerSubclassEffects, setPlayerSubclassEffects] = useState({})
  const [maneuverModalOpen, setManeuverModalOpen] = useState(false)
  const [reactionPrompt, setReactionPrompt] = useState(null)

  // 自然语言战斗输入
  const [combatInput, setCombatInput] = useState('')

  // 先攻骰子动画标记（仅第一轮第一次显示）
  const [initiativeShown, setInitiativeShown] = useState(false)

  // v0.10 新增 — 完整 session 数据（供底部 HUD 展示）
  const [session, setSession] = useState(null)
  // v0.10 — 后端 /skill-bar 返回的技能栏
  const [skillBarV10, setSkillBarV10] = useState(null)
  // v0.10 — /predict 预测结果
  const [prediction, setPrediction] = useState(null)
  // v0.10 — 伤害飘字（保留 floats 占位，目前未使用）
  const floats = []

  const logsEndRef = useRef(null)
  const gridContainerRef = useRef(null)
  const aiTimer = useRef(null)
  const processingRef = useRef(false)

  // v0.10 — 加载技能栏（玩家信息就绪时一次性拉取）
  useEffect(() => {
    if (!sessionId || !playerId) return
    gameApi.getSkillBar(sessionId, playerId)
      .then((data) => { if (data?.bar) setSkillBarV10(data.bar) })
      .catch(() => {})
  }, [sessionId, playerId, playerSpellSlots])

  // v0.10 — 选中目标时获取命中率预测（带轻微去抖）
  useEffect(() => {
    if (!selectedTarget || !playerId || !sessionId) { setPrediction(null); return }
    const timer = setTimeout(() => {
      const actionKey =
        playerClass?.includes('Paladin') || playerClass?.includes('圣武') ? 'smite' :
        playerClass?.includes('Rogue')   || playerClass?.includes('游荡') ? 'sneak' :
        playerClass?.includes('Wizard')  || playerClass?.includes('法师') ? 'firebolt' :
        playerClass?.includes('Cleric')  || playerClass?.includes('牧师') ? 'sacred_flame' :
        'atk'
      gameApi.predict(sessionId, playerId, selectedTarget, actionKey, isRanged)
        .then(setPrediction)
        .catch(() => setPrediction(null))
    }, 150)
    return () => clearTimeout(timer)
  }, [selectedTarget, playerId, sessionId, playerClass, isRanged])

  // 自动滚动地图到玩家位置
  useEffect(() => {
    if (!combat || !playerId || !gridContainerRef.current) return
    const pos = combat.entity_positions?.[playerId]
    if (!pos) return
    const container = gridContainerRef.current
    const targetX = pos.x * CELL - container.clientWidth / 2 + CELL / 2
    const targetY = pos.y * CELL - container.clientHeight / 2 + CELL / 2
    container.scrollTo({ left: Math.max(0, targetX), top: Math.max(0, targetY), behavior: 'smooth' })
  }, [combat?.entity_positions?.[playerId]?.x, combat?.entity_positions?.[playerId]?.y, playerId])

  useEffect(() => {
    loadCombat()
    loadSpells()
    return () => clearTimeout(aiTimer.current)
  }, [sessionId])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const addLog = useCallback((entry) => {
    setLogs(prev => [...prev, { id: `log-${Date.now()}-${Math.random()}`, ...entry }])
  }, [])

  const isPlayerTurn = useCallback((c) => {
    if (!c) return false
    return c.turn_order?.[c.current_turn_index]?.is_player === true
  }, [])

  // 从 combat.turn_states 中取当前玩家的回合状态
  const getPlayerTs = useCallback((c, pid) => {
    if (!c || !pid) return null
    return c.turn_states?.[pid] || null
  }, [])

  const loadCombat = async () => {
    try {
      const data = await gameApi.getCombat(sessionId)
      setCombat(data)

      const sessionData = await gameApi.getSession(sessionId)
      const session = sessionData
      setSession(sessionData)
      const pid = session.player?.id
      setPlayerId(pid)
      if (session.player?.spell_slots)  setPlayerSpellSlots(session.player.spell_slots)
      if (session.player?.known_spells) setPlayerKnownSpells(session.player.known_spells)
      if (session.player?.cantrips)     setPlayerCantrips(session.player.cantrips)
      if (session.player?.char_class)   setPlayerClass(session.player.char_class)
      if (session.player?.level)        setPlayerLevel(session.player.level)
      if (session.player?.class_resources) setClassResources(session.player.class_resources || {})
      if (session.player?.subclass) setPlayerSubclass(session.player.subclass)
      if (session.player?.derived?.subclass_effects) setPlayerSubclassEffects(session.player.derived.subclass_effects)

      // 同步回合状态
      if (pid) setTurnState(data.turn_states?.[pid] || null)

      // 先攻骰子动画（仅第1轮首次加载时展示）— 玩家点击投掷
      if (data.round_number === 1 && !initiativeShown && pid) {
        const playerEntry = (data.turn_order || []).find(t => t.is_player)
        if (playerEntry && playerEntry.initiative != null) {
          setInitiativeShown(true)
          // 让玩家投掷先攻骰子（纯表演，结果已由后端决定）
          const { total: initD20 } = await rollDice3D(20)
          // 显示后端的实际先攻值（因为先攻已经在战斗初始化时计算好了）
          const d20Val = playerEntry.d20 || playerEntry.initiative
          showDice({ faces: 20, result: d20Val, label: '先攻检定' })
        }
      }

      const combatLogs = (session.logs || []).filter(l =>
        l.log_type === 'combat' || l.log_type === 'system'
      )
      setLogs(combatLogs)

      if (!isPlayerTurn(data)) {
        aiTimer.current = setTimeout(() => triggerAiTurn(), 1000)
      }
    } catch (e) {
      setError(e.message)
    }
  }

  const loadSpells = async () => {
    try {
      const list = await gameApi.getSpells()
      setSpells(list || [])
    } catch (_) { /* 静默失败 */ }
  }

  // ── 多人联机：检测房间 + 设置我控制的角色 ──
  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const r = await roomsApi.get(sessionId)
        if (!mounted) return
        if (r?.is_multiplayer) {
          setRoom(r)
          const me = (r.members || []).find(m => m.user_id === myUserId)
          if (me?.character_id) setMyCharacterId(me.character_id)
        }
      } catch (_) {
        // 单人会话，roomsApi.get 会 404 — 静默忽略
      }
    })()
    return () => { mounted = false }
  }, [sessionId, myUserId])

  // ── 多人联机：WS 事件 → 增量刷新战斗状态 ──
  const onWsEvent = useCallback((event) => {
    switch (event.type) {
      case 'combat_update':
      case 'turn_changed':
      case 'entity_moved':
      case 'dm_responded':
        // 简单粗暴：任意状态变化都重载
        loadCombat()
        break
      case 'member_offline':
      case 'member_online':
        // 刷新房间成员状态
        roomsApi.get(sessionId).then(r => r?.is_multiplayer && setRoom(r)).catch(() => {})
        break
      default:
        break
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  useWebSocket(room ? sessionId : null, onWsEvent)

  // ── 多人联机：判断当前回合是否归我 ──
  const isMyTurnMP = useMemo(() => {
    if (!room) return true  // 单人模式：永远轮到我
    if (!combat?.turn_order?.length) return false
    const cur = combat.turn_order[combat.current_turn_index || 0]
    return cur?.character_id === myCharacterId
  }, [room, combat, myCharacterId])

  // 当前回合归属玩家昵称（用于 UI 顶部指示）
  const currentTurnLabel = useMemo(() => {
    if (!room || !combat?.turn_order?.length) return ''
    const cur = combat.turn_order[combat.current_turn_index || 0]
    if (!cur) return ''
    const m = (room.members || []).find(mb => mb.character_id === cur.character_id)
    if (m) return `当前回合：${m.display_name}（${cur.name}）`
    return `当前回合：${cur.name}（AI 托管）`
  }, [room, combat])

  // 玩家实际可用法术（已习得/已准备的法术 + 戏法，按职业过滤）
  const playerAvailableSpells = useMemo(() => {
    const known = new Set([...playerKnownSpells, ...playerCantrips])
    if (known.size > 0) {
      return spells.filter(s => known.has(s.name))
    }
    // 没有习得法术时，按职业过滤（而非显示全部）
    if (playerClass) {
      const classKey = playerClass.replace(/[\u4e00-\u9fff]/g, '') || playerClass  // 处理中文职业名
      const classMap = {
        'Fighter': 'Fighter', '战士': 'Fighter',
        'Wizard': 'Wizard', '法师': 'Wizard',
        'Sorcerer': 'Sorcerer', '术士': 'Sorcerer',
        'Cleric': 'Cleric', '牧师': 'Cleric',
        'Bard': 'Bard', '吟游诗人': 'Bard',
        'Druid': 'Druid', '德鲁伊': 'Druid',
        'Warlock': 'Warlock', '邪术师': 'Warlock',
        'Paladin': 'Paladin', '圣武士': 'Paladin',
        'Ranger': 'Ranger', '游侠': 'Ranger',
      }
      const mappedClass = classMap[playerClass] || playerClass
      return spells.filter(s => s.classes?.includes(mappedClass))
    }
    return spells
  }, [spells, playerKnownSpells, playerCantrips, playerClass])

  // ── AI 回合处理 ────────────────────────────────────────
  const triggerAiTurn = useCallback(async () => {
    // 严格串行：整个 AI 循环期间保持锁定
    if (processingRef.current) return
    processingRef.current = true
    setIsProcessing(true)

    try {
      // 循环处理所有连续的 AI 回合，直到轮到玩家或战斗结束
      // 安全上限：最多处理 20 个 AI 回合（防止无限循环）
      let aiTurnCount = 0
      const AI_TURN_LIMIT = 20
      let lastTurnIndex = -1

      while (aiTurnCount < AI_TURN_LIMIT) {
        aiTurnCount++

        // 1. 从服务端获取最新状态，确认当前轮到谁
        let fresh
        try {
          fresh = await gameApi.getCombat(sessionId)
        } catch (_) { break }

        if (!fresh) break
        setCombat(fresh)

        // 防死循环：如果 turn_index 没变，说明回合未推进
        if (fresh.current_turn_index === lastTurnIndex) {
          console.warn('AI turn index not advancing, breaking loop')
          break
        }
        lastTurnIndex = fresh.current_turn_index

        const currentEntry = fresh.turn_order?.[fresh.current_turn_index]
        if (!currentEntry || currentEntry.is_player) {
          // 轮到玩家了，加载玩家的回合状态
          if (currentEntry?.is_player) {
            const pid = currentEntry.character_id
            setTurnState(fresh.turn_states?.[pid] || null)
          }
          break
        }

        // 2. 执行 AI 回合
        let result
        try {
          result = await gameApi.aiTurn(sessionId)
        } catch (e) {
          addLog({ role: 'system', content: `AI行动错误: ${e.message}`, log_type: 'system' })
          break  // 出错直接退出，不再重试
        }

        // 3. 更新前端状态
        if (result.concentration_check?.d20) {
          showDice({
            faces: 20,
            result: result.concentration_check.d20,
            label: `CON豁免 DC${result.concentration_check.dc || 10}`,
          })
        }

        setCombat(prev => {
          if (!prev) return prev
          const updated = applyHpUpdate(prev, result.target_id, result.target_new_hp)
          return {
            ...updated,
            current_turn_index: result.next_turn_index,
            round_number: result.round_number,
            ...(result.entity_positions ? { entity_positions: result.entity_positions } : {}),
          }
        })

        addLog({
          role: result.actor_id?.startsWith('enemy') ? 'enemy' : `companion_${result.actor_name}`,
          content: result.narration,
          log_type: 'combat',
          dice_result: result.attack_result?.d20
            ? { attack: result.attack_result, damage: result.damage }
            : null,
        })

        // 反应提示：敌人攻击玩家时可用反应
        if (result.reaction_prompt && result.player_can_react) {
          setReactionPrompt(result.reaction_prompt)
          // 暂停 AI 循环等待玩家决定
          processingRef.current = false
          setIsProcessing(false)
          break  // Exit the while loop to let player react
        }

        if (result.combat_over) {
          setCombatOver(result.outcome)
          break
        }

        // 4. 等待一下再处理下一个 AI（避免太快）
        await new Promise(r => setTimeout(r, 600))
      }
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [sessionId, addLog, showDice])

  // ── 结束回合（玩家明确操作）─────────────────────────────
  const handleEndTurn = useCallback(async () => {
    if (!isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setMoveMode(false)
    setHelpMode(false)
    setError('')
    try {
      const result = await gameApi.endTurn(sessionId)

      if (result.expired_conditions?.length) {
        result.expired_conditions.forEach(msg => addLog({ role: 'system', content: msg, log_type: 'system' }))
      }

      if (result.combat_over) { setCombatOver(result.outcome); return }

      // 更新本地状态
      setCombat(prev => {
        if (!prev) return prev
        return {
          ...prev,
          current_turn_index: result.next_turn_index,
          round_number: result.round_number,
        }
      })

      // 释放锁，然后检查是否需要启动 AI 循环
      processingRef.current = false
      setIsProcessing(false)

      // 从服务端获取最新状态来判断下一个是谁
      try {
        const fresh = await gameApi.getCombat(sessionId)
        if (fresh) {
          setCombat(fresh)
          const nextEntry = fresh.turn_order?.[fresh.current_turn_index]
          if (nextEntry && !nextEntry.is_player) {
            aiTimer.current = setTimeout(() => triggerAiTurn(), 600)
          } else if (nextEntry?.is_player) {
            // 玩家新回合：加载回合状态
            setTurnState(fresh.turn_states?.[nextEntry.character_id] || null)
          }
        }
      } catch (_) {}
    } catch (e) {
      setError(e.message)
      processingRef.current = false
      setIsProcessing(false)
    }
  }, [combat, sessionId, isProcessing, addLog, triggerAiTurn])

  // ── 自然语言战斗行动 ──────────────────────────────────
  const handleCombatAction = async () => {
    if (!combatInput.trim() || !playerTurn || isProcessing || actionUsed) return
    const text = combatInput.trim()
    setCombatInput('')
    processingRef.current = true
    setIsProcessing(true)
    setError('')

    try {
      addLog({ role: 'player', content: text, log_type: 'combat' })

      const resp = await gameApi.action({ session_id: sessionId, action_text: text })

      // 叙事日志
      if (resp.narrative) {
        addLog({ role: 'dm', content: resp.narrative, log_type: 'combat' })
      }
      if (resp.companion_reactions) {
        addLog({ role: 'companion', content: resp.companion_reactions, log_type: 'companion' })
      }

      // 逐个显示骰子 3D 动画
      if (resp.dice_display?.length > 0) {
        for (const dice of resp.dice_display) {
          const faces = dice.dice_face || 20
          const result = dice.raw || dice.total || 0
          const label = dice.label || '检定'
          if (result > 0) {
            await rollDice3D(faces)  // 3D 动画
            showDice({ faces, result, label })  // 数值覆盖
            await new Promise(r => setTimeout(r, 2000))  // 等待展示
          }
        }
      }

      // 更新战斗状态
      if (resp.combat_update) {
        setCombat(prev => {
          if (!prev) return prev
          return {
            ...prev,
            entity_positions: resp.combat_update.entity_positions || prev.entity_positions,
            turn_states: resp.combat_update.turn_states || prev.turn_states,
            current_turn_index: resp.combat_update.current_turn_index ?? prev.current_turn_index,
            round_number: resp.combat_update.round_number ?? prev.round_number,
          }
        })
        if (resp.combat_update.turn_states && playerId) {
          setTurnState(resp.combat_update.turn_states[playerId] || null)
        }
      }

      // 战斗结束
      if (resp.combat_ended) {
        setCombatOver(resp.combat_end_result)
      }

      // 刷新完整状态
      try {
        const fresh = await gameApi.getCombat(sessionId)
        if (fresh) setCombat(fresh)
      } catch (_) {}

    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  const handleCombatInputKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleCombatAction()
    }
  }

  // ── 玩家攻击（两步流程：attack-roll → dice动画 → damage-roll）──
  const handleAttack = async () => {
    if (!selectedTarget || !isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setAttackPhase('rolling_d20')
    setError('')
    try {
      // Step 1: 3D骰子掷d20 → 传给后端
      const { total: d20 } = await rollDice3D(20)
      showDice({ faces: 20, result: d20, label: '攻击检定' })

      const atkResult = await gameApi.attackRoll(
        sessionId, playerId, selectedTarget,
        isRanged ? 'ranged' : 'melee', false, d20,
      )

      if (atkResult.turn_state) setTurnState(atkResult.turn_state)
      setAttackPhase('hit_result')

      // Extra Attack 提示
      const attacksRemaining = atkResult.attacks_max - atkResult.attacks_made
      if (attacksRemaining > 0) {
        addLog({
          role: 'system',
          content: `\u2694\uFE0F 额外攻击：还可攻击 ${attacksRemaining} 次`,
          log_type: 'system',
        })
      }

      if (!atkResult.hit) {
        // Juice：未命中 / 大失手 音效
        try { JuiceAudio.miss() } catch (e) {}
        if (atkResult.is_fumble) {
          try { JuiceShake(document.querySelector('.combat-stage') || document.body, 6, 320) } catch (e) {}
        }
        // 未命中 — 显示 LLM 叙事或 fallback 日志
        const missText = atkResult.narration || (atkResult.is_fumble
          ? `\uD83D\uDC80 大失手！${atkResult.attacker_name} 对 ${atkResult.target_name} 攻击失手。（${atkResult.attack_total} vs AC${atkResult.target_ac}）`
          : `${atkResult.attacker_name} 攻击 ${atkResult.target_name}，未命中。（${atkResult.attack_total} vs AC${atkResult.target_ac}）`)
        addLog({ role: 'player', content: missText, log_type: 'combat',
          dice_result: { attack: { d20: atkResult.d20, attack_total: atkResult.attack_total, target_ac: atkResult.target_ac, hit: false, is_crit: false, is_fumble: atkResult.is_fumble } },
        })
        setSelectedTarget(null)
        setAttackPhase('idle')
        setPendingAttack(null)
        processingRef.current = false
        setIsProcessing(false)
        return
      }

      // Juice：命中 / 暴击 音效（暴击附加震屏）
      if (atkResult.is_crit) {
        try { JuiceAudio.crit() } catch (e) {}
        try { JuiceShake(document.querySelector('.combat-stage') || document.body, 10, 420) } catch (e) {}
      } else {
        try { JuiceAudio.hit() } catch (e) {}
      }
      // 命中 — 暂存待处理攻击，等 2 秒让玩家看 d20 结果后自动掷伤害
      const hitLabel = atkResult.is_crit ? '\uD83D\uDCA5 暴击！' : '命中！'
      addLog({ role: 'system', content: `${hitLabel} ${atkResult.attacker_name} 对 ${atkResult.target_name}（${atkResult.attack_total} vs AC${atkResult.target_ac}）`, log_type: 'combat',
        dice_result: { attack: { d20: atkResult.d20, attack_total: atkResult.attack_total, target_ac: atkResult.target_ac, hit: true, is_crit: atkResult.is_crit, is_fumble: false } },
      })

      setPendingAttack({ ...atkResult, targetId: selectedTarget })

      // 延迟 1.8 秒后自动掷伤害（让玩家看到 d20 动画 + 命中结果）
      setTimeout(async () => {
        try {
          setAttackPhase('rolling_damage')

          // 3D骰子掷伤害骰 → 传给后端
          const dmgDiceMatch = (atkResult.damage_dice || '1d8').match(/(\d*)d(\d+)/)
          const dmgCount = dmgDiceMatch ? parseInt(dmgDiceMatch[1] || '1') : 1
          const damageFaces = dmgDiceMatch ? parseInt(dmgDiceMatch[2]) : 8
          const { total: dmgTotal, rolls: dmgRolls } = await rollDice3D(damageFaces, dmgCount)
          showDice({ faces: damageFaces, result: dmgTotal, label: '伤害骰', count: dmgCount })

          const dmgResult = await gameApi.damageRoll(sessionId, atkResult.pending_attack_id, dmgRolls)

          // 更新 HP
          setCombat(prev => {
            if (!prev) return prev
            return applyHpUpdate(prev, dmgResult.target_id, dmgResult.target_new_hp)
          })

          if (dmgResult.turn_state) setTurnState(dmgResult.turn_state)

          addLog({ role: 'player', content: dmgResult.narration, log_type: 'combat',
            dice_result: { damage: dmgResult.damage_total, total_damage: dmgResult.total_damage },
          })

          // Sneak Attack 日志
          if (dmgResult.sneak_attack_damage > 0) {
            addLog({ role: 'system', content: `\uD83D\uDDE1\uFE0F 偷袭！额外造成 ${dmgResult.sneak_attack_damage} 点伤害`, log_type: 'system' })
          }

          // Paladin smite prompt
          if (dmgResult.can_smite) {
            setSmitePrompt({ show: true, targetId: dmgResult.target_id })
          }

          if (dmgResult.combat_over) { setCombatOver(dmgResult.outcome) }
        } catch (e2) {
          setError(e2.message)
        } finally {
          setSelectedTarget(null)
          setAttackPhase('idle')
          setPendingAttack(null)
          processingRef.current = false
          setIsProcessing(false)
        }
      }, 1800)
    } catch (e) {
      setError(e.message)
      setAttackPhase('idle')
      setPendingAttack(null)
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 神圣斩击 (Divine Smite) ────────────────────────────
  const handleSmite = async (slotLevel) => {
    if (isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    const currentSmiteTarget = smitePrompt?.targetId
    setSmitePrompt(null)
    try {
      // 先掷 3D 骰子（斩击骰：2d8 + 每环 +1d8）
      const smiteDiceCount = 2 + (slotLevel - 1)  // 基础2d8 + 每环+1d8
      const { total: smiteTotal, rolls: smiteRolls } = await rollDice3D(8, smiteDiceCount)
      showDice({ faces: 8, result: smiteTotal, label: '神圣斩击', count: smiteDiceCount })

      const result = await gameApi.smite(sessionId, slotLevel, false, smiteRolls, currentSmiteTarget)

      addLog({ role: 'player', content: result.narration, log_type: 'combat' })
      if (result.remaining_slots) setPlayerSpellSlots(result.remaining_slots)
      setCombat(prev => {
        if (!prev) return prev
        return applyHpUpdate(prev, currentSmiteTarget, result.target_new_hp)
      })
      if (result.combat_over) setCombatOver(result.outcome)
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 职业特性 ───────────────────────────────────────────
  const handleClassFeature = async (featureName) => {
    if (isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      // 需要前端掷骰的职业特性
      const FEATURE_DICE = {
        second_wind: { faces: 10, count: 1, label: '活力恢复' },
        ki_flurry: { faces: 20, count: 1, label: '疾风连击' },
        portent: { faces: 20, count: 1, label: '预言骰' },
        bardic_inspiration: { faces: 6, count: 1, label: '灵感骰' },  // 实际 die 从 subclass 获取
        shadow_step: { faces: 20, count: 1, label: '暗影步' },
      }
      const featureDice = FEATURE_DICE[featureName]
      if (featureDice) {
        const { total, rolls } = await rollDice3D(featureDice.faces, featureDice.count)
        showDice({ faces: featureDice.faces, result: total, label: featureDice.label, count: featureDice.count })
      }

      const result = await gameApi.classFeature(sessionId, featureName)
      addLog({ role: 'player', content: result.narration, log_type: 'combat' })
      if (result.turn_state) setTurnState(result.turn_state)
      if (result.class_resources) setClassResources(result.class_resources)
      // Update player HP in combat state
      setCombat(prev => {
        if (!prev || !playerId) return prev
        const updated = { ...prev, entities: { ...prev.entities } }
        if (updated.entities[playerId]) {
          updated.entities[playerId] = {
            ...updated.entities[playerId],
            hp_current: result.hp_current,
          }
        }
        return updated
      })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 反应 (Reaction) ─────────────────────────────────────
  const handleReaction = async (reactionType, targetId = null) => {
    setReactionPrompt(null)
    processingRef.current = true
    setIsProcessing(true)
    try {
      // 地狱斥责等反应法术需要掷骰
      if (reactionType === 'hellish_rebuke') {
        const { total, rolls } = await rollDice3D(10, 2)
        showDice({ faces: 10, result: total, label: '地狱斥责 2d10', count: 2 })
      }
      const result = await gameApi.useReaction(sessionId, reactionType, targetId)
      addLog({ role: 'player', content: result.narration, log_type: 'combat' })
      if (result.turn_state) setTurnState(result.turn_state)
      // Resume AI turns after reaction
      processingRef.current = false
      setIsProcessing(false)
      triggerAiTurn()
    } catch (e) {
      setError(e.message)
      processingRef.current = false
      setIsProcessing(false)
      triggerAiTurn()
    }
  }

  const skipReaction = () => {
    setReactionPrompt(null)
    // Resume AI turns
    triggerAiTurn()
  }

  // ── 战技 (Battle Master Maneuver) ───────────────────────
  const handleManeuver = async (maneuverName) => {
    if (isProcessing || !selectedTarget) return
    processingRef.current = true
    setIsProcessing(true)
    setError('')
    try {
      // 战技优越骰 3D 动画
      const sdFaces = parseInt((playerSubclassEffects?.superiority_die || 'd8').replace('d', '')) || 8
      const { total: sdTotal, rolls: sdRolls } = await rollDice3D(sdFaces)
      showDice({ faces: sdFaces, result: sdTotal, label: `战技·${maneuverName}` })

      const result = await gameApi.maneuver(sessionId, maneuverName, selectedTarget)
      addLog({ role: 'player', content: result.narration || result.description, log_type: 'combat',
        dice_result: result.superiority_die_roll ? { type: 'maneuver', value: result.superiority_die_roll, die: result.superiority_die } : null })
      if (result.turn_state) setTurnState(result.turn_state)
      if (result.class_resources) setClassResources(result.class_resources)
      setCombat(prev => {
        if (!prev) return prev
        if (result.target_new_hp !== undefined && result.target_new_hp !== null) {
          return applyHpUpdate(prev, selectedTarget, result.target_new_hp)
        }
        return prev
      })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 副手攻击（Two-Weapon Fighting，两步流程）──────────────
  const handleOffhandAttack = async () => {
    if (!selectedTarget || !isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setAttackPhase('rolling_d20')
    setError('')
    try {
      // Step 1: 3D骰子掷d20 → 传给后端
      const { total: d20 } = await rollDice3D(20)
      showDice({ faces: 20, result: d20, label: '副手攻击' })

      const atkResult = await gameApi.attackRoll(
        sessionId, playerId, selectedTarget, 'melee', true, d20,
      )

      if (atkResult.turn_state) setTurnState(atkResult.turn_state)
      setAttackPhase('hit_result')

      if (!atkResult.hit) {
        const missText = atkResult.is_fumble
          ? `\uD83D\uDC80 【副手】大失手！${atkResult.attacker_name} 对 ${atkResult.target_name} 攻击失手。`
          : `【副手】${atkResult.attacker_name} 攻击 ${atkResult.target_name}，未命中。（${atkResult.attack_total} vs AC${atkResult.target_ac}）`
        addLog({ role: 'player', content: missText, log_type: 'combat',
          dice_result: { attack: { d20: atkResult.d20, attack_total: atkResult.attack_total, target_ac: atkResult.target_ac, hit: false, is_crit: false, is_fumble: atkResult.is_fumble } },
        })
        setSelectedTarget(null)
        setAttackPhase('idle')
        setPendingAttack(null)
        processingRef.current = false
        setIsProcessing(false)
        return
      }

      const hitLabel = atkResult.is_crit ? '\uD83D\uDCA5 暴击！' : '命中！'
      addLog({ role: 'system', content: `【副手】${hitLabel} ${atkResult.attacker_name} 对 ${atkResult.target_name}（${atkResult.attack_total} vs AC${atkResult.target_ac}）`, log_type: 'combat' })
      setPendingAttack({ ...atkResult, targetId: selectedTarget })

      setTimeout(async () => {
        try {
          setAttackPhase('rolling_damage')

          // 3D骰子掷副手伤害骰 → 传给后端
          const ohDiceMatch = (atkResult.damage_dice || '1d8').match(/(\d*)d(\d+)/)
          const ohCount = ohDiceMatch ? parseInt(ohDiceMatch[1] || '1') : 1
          const damageFaces = ohDiceMatch ? parseInt(ohDiceMatch[2]) : 8
          const { total: ohTotal, rolls: ohRolls } = await rollDice3D(damageFaces, ohCount)
          showDice({ faces: damageFaces, result: ohTotal, label: '副手伤害', count: ohCount })

          const dmgResult = await gameApi.damageRoll(sessionId, atkResult.pending_attack_id, ohRolls)

          setCombat(prev => prev ? applyHpUpdate(prev, dmgResult.target_id, dmgResult.target_new_hp) : prev)
          if (dmgResult.turn_state) setTurnState(dmgResult.turn_state)
          addLog({ role: 'player', content: dmgResult.narration || '副手攻击命中！', log_type: 'combat',
            dice_result: { damage: dmgResult.damage_total, total_damage: dmgResult.total_damage },
          })

          if (dmgResult.can_smite) {
            setSmitePrompt({ show: true, targetId: dmgResult.target_id })
          }
          if (dmgResult.combat_over) { setCombatOver(dmgResult.outcome) }
        } catch (e2) {
          setError(e2.message)
        } finally {
          setSelectedTarget(null)
          setAttackPhase('idle')
          setPendingAttack(null)
          processingRef.current = false
          setIsProcessing(false)
        }
      }, 1800)
    } catch (e) {
      setError(e.message)
      setAttackPhase('idle')
      setPendingAttack(null)
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 玩家闪避 ───────────────────────────────────────────
  const handleDodge = async () => {
    if (!isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    try {
      const result = await gameApi.combatAction(sessionId, '闪避', null, false)
      if (result.turn_state) setTurnState(result.turn_state)
      addLog({ role: 'player', content: result.narration || '你采取了闪避姿态，专注于躲避攻击。', log_type: 'combat' })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 冲刺 ───────────────────────────────────────────────
  const handleDash = async () => {
    if (!isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    try {
      const result = await gameApi.combatAction(sessionId, '冲刺', null, false)
      if (result.turn_state) setTurnState(result.turn_state)
      addLog({ role: 'player', content: result.narration || '你使用冲刺，移动力翻倍！', log_type: 'combat' })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 脱离接战 ───────────────────────────────────────────
  const handleDisengage = async () => {
    if (!isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    try {
      const result = await gameApi.combatAction(sessionId, '脱离接战', null, false)
      if (result.turn_state) setTurnState(result.turn_state)
      addLog({ role: 'player', content: result.narration || '你脱离接战，本回合移动不触发借机攻击。', log_type: 'combat' })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 协助 ───────────────────────────────────────────────
  const handleHelp = async (targetAllyId = null) => {
    if (!isPlayerTurn(combat) || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    setHelpMode(false)
    try {
      const result = await gameApi.combatAction(sessionId, '协助', targetAllyId, false)
      if (result.turn_state) setTurnState(result.turn_state)
      addLog({ role: 'player', content: result.narration || '你协助队友，对方下次攻击具有优势！', log_type: 'combat' })
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 移动模式切换 ────────────────────────────────────────
  const handleMoveClick = () => {
    const ts = turnState
    const movementRemaining = ts ? ts.movement_max - ts.movement_used : 6
    if (movementRemaining <= 0) return
    setMoveMode(prev => !prev)
    setHelpMode(false)
    setSelectedTarget(null)
  }

  const handleCellClick = (x, y) => {
    if (!isPlayerTurn(combat) || isProcessing) return
    const positions = combat?.entity_positions || {}
    const entities = combat?.entities || {}
    const found = Object.entries(positions).find(([, pos]) => pos.x === x && pos.y === y)

    // 协助模式：点击队友
    if (helpMode) {
      if (found) {
        const [eid] = found
        const entity = entities[eid]
        if (entity && !entity.is_enemy && entity.id !== playerId && entity.hp_current > 0) {
          handleHelp(eid)
        }
      }
      return
    }

    // 移动模式：点击空地移动
    if (moveMode) {
      if (found) return
      if (!playerId) return
      gameApi.move(sessionId, playerId, x, y)
        .then(res => {
          setCombat(prev => prev ? {
            ...prev,
            entity_positions: res.positions,
          } : prev)
          if (res.turn_state) setTurnState(res.turn_state)
          const remaining = res.movement_max - res.movement_used
          addLog({
            role: 'player',
            content: `你移动到格子 (${x}, ${y})。剩余移动力：${remaining} 格`,
            log_type: 'combat',
          })
          // 借机攻击提示
          if (res.opportunity_attacks?.length) {
            for (const oa of res.opportunity_attacks) {
              const hitText = oa.hit ? `命中！造成 ${oa.damage} 点伤害` : '未命中！'
              addLog({
                role: 'system',
                content: `\u26A0\uFE0F 借机攻击！${oa.attacker} 对 ${oa.target} 发动攻击 \u2014 ${hitText}`,
                log_type: 'combat',
              })
              if (oa.hit) {
                showDice({ faces: 20, result: oa.d20 || 0, label: `${oa.attacker} 借机攻击` })
              }
            }
          }
          if (remaining <= 0) setMoveMode(false)
        })
        .catch(e => setError(e.message))
      return
    }

    // 选目标模式
    if (found) {
      const [eid] = found
      const entity = entities[eid]
      if (entity?.is_enemy && entity?.hp_current > 0) {
        setSelectedTarget(prev => prev === eid ? null : eid)
        return
      }
    }
    setSelectedTarget(null)
  }

  // ── 施法（两步流程：spell-roll → dice动画 → spell-confirm）───
  const handleCastSpell = async (spell, level) => {
    if (!playerId || isProcessing) return
    const target = selectedTarget || null
    const effectiveTarget = spell.type === 'heal' ? (target || playerId) : target

    if (spell.type === 'damage' && !effectiveTarget) {
      setError('请先选择一个目标再施法')
      return
    }

    processingRef.current = true
    setIsProcessing(true)
    setSpellModalOpen(false)
    setError('')

    try {
      // Step 1: 验证法术，获取将要掷的骰子信息
      const targetIds = Array.isArray(effectiveTarget) ? effectiveTarget : (effectiveTarget ? [effectiveTarget] : [])
      const rollResult = await gameApi.spellRoll(
        sessionId, playerId, spell.name, level,
        targetIds[0] || null, targetIds,
      )

      if (rollResult.turn_state) setTurnState(rollResult.turn_state)

      // 显示法术预告日志
      const targetDesc = (rollResult.targets || []).map(t => t.name).join('、') || ''
      const diceInfo = rollResult.damage_dice || rollResult.heal_dice || ''
      if (diceInfo) {
        addLog({
          role: 'system',
          content: `${spell.name}${targetDesc ? ` → ${targetDesc}` : ''} — 掷骰 ${diceInfo}`,
          log_type: 'system',
        })
      }

      // Step 2: 延迟后自动掷伤害/治疗骰
      setTimeout(async () => {
        try {
          // 3D骰子掷法术骰 → 传给后端
          const diceStr = rollResult.damage_dice || rollResult.heal_dice || ''
          const diceMatch = diceStr.match(/(\d*)d(\d+)/)
          const diceCount = diceMatch ? parseInt(diceMatch[1] || '1') : 1
          const diceFaces = diceMatch ? parseInt(diceMatch[2]) : 6
          let spellRolls = null
          if (diceStr) {
            const { total: spellTotal, rolls: spellDiceRolls } = await rollDice3D(diceFaces, diceCount)
            spellRolls = spellDiceRolls
            showDice({ faces: diceFaces, result: spellTotal, label: spell.name, count: diceCount })
          }

          const confirmResult = await gameApi.spellConfirm(sessionId, rollResult.pending_spell_id, spellRolls)
          const totalValue = confirmResult.damage || confirmResult.heal || 0

          // 更新 HP（单目标）
          if (confirmResult.target_new_hp != null) {
            setCombat(prev => {
              if (!prev) return prev
              return applyHpUpdate(prev, confirmResult.target_id, confirmResult.target_new_hp)
            })
          }

          // 更新 HP（AoE 多目标）
          if (confirmResult.aoe_results?.length) {
            setCombat(prev => {
              if (!prev) return prev
              let updated = prev
              for (const aoe of confirmResult.aoe_results) {
                const hp = aoe.new_hp != null ? aoe.new_hp : aoe.hp
                if (hp != null) {
                  updated = applyHpUpdate(updated, aoe.target_id, hp)
                }
              }
              return updated
            })
          }

          if (confirmResult.turn_state) setTurnState(confirmResult.turn_state)
          setPlayerSpellSlots(confirmResult.remaining_slots || {})
          addLog({ role: 'player', content: confirmResult.narration, log_type: 'combat' })
          setSelectedTarget(null)

          // 野蛮魔法涌动 — 玩家掷检测骰
          if (confirmResult.wild_magic_check) {
            const wmc = confirmResult.wild_magic_check
            if (wmc.forced) {
              // 混沌之潮反噬 — 不掷骰，直接涌动
              addLog({
                role: 'system',
                content: `🌀 混沌反噬！${confirmResult.wild_magic_surge?.effect || '野蛮魔法涌动！'}`,
                log_type: 'system',
              })
              if (wmc.surge_roll) {
                // 掷涌动效果骰
                const { total: surgeD20 } = await rollDice3D(20)
                showDice({ faces: 20, result: surgeD20, label: `涌动效果 #${wmc.surge_roll}` })
              }
            } else {
              // 玩家掷野蛮魔法检测 d20
              const { total: surgeCheck } = await rollDice3D(20)
              const triggered = surgeCheck === 1
              showDice({ faces: 20, result: surgeCheck, label: triggered ? '🌀 野蛮魔法涌动！' : '野蛮魔法检测' })

              if (triggered && confirmResult.wild_magic_surge) {
                addLog({
                  role: 'system',
                  content: `🌀 野蛮魔法涌动！d20=${surgeCheck} — ${confirmResult.wild_magic_surge.effect}`,
                  log_type: 'system',
                })
              } else {
                addLog({
                  role: 'system',
                  content: `🎲 野蛮魔法检测: d20=${surgeCheck}（安全，未触发涌动）`,
                  log_type: 'system',
                })
              }
            }
          }

          if (confirmResult.combat_over) { setCombatOver(confirmResult.outcome) }
        } catch (e2) {
          setError(e2.message)
        } finally {
          processingRef.current = false
          setIsProcessing(false)
        }
      }, 1200)
    } catch (e) {
      setError(e.message)
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  // ── 濒死豁免 ───────────────────────────────────────────
  const handleDeathSave = async () => {
    if (!playerId || isProcessing) return
    processingRef.current = true
    setIsProcessing(true)
    try {
      // 3D骰子掷d20 → 传给后端
      const { total: d20 } = await rollDice3D(20)
      showDice({ faces: 20, result: d20, label: '濒死豁免' })

      const result = await gameApi.deathSave(sessionId, playerId, d20)
      const { outcome, death_saves: ds } = result

      setCombat(prev => {
        if (!prev || !prev.entities[playerId]) return prev
        const updated = { ...prev, entities: { ...prev.entities } }
        updated.entities[playerId] = {
          ...updated.entities[playerId],
          hp_current: outcome === 'revived' ? 1 : 0,
          death_saves: ds,
        }
        return updated
      })

      const msg = outcome === 'revived'   ? `自然20！${playerEntity?.name}奇迹复活，恢复1点HP！`
                : outcome === 'stable'    ? `${playerEntity?.name}已稳定，不再需要豁免。`
                : outcome === 'dead'      ? `${playerEntity?.name}三次失败，已永久阵亡。`
                : d20 >= 10              ? `成功（${d20}）· 已累计 ${ds?.successes} 次成功`
                :                          `失败（${d20}）· 已累计 ${ds?.failures} 次失败`
      addLog({ role: 'system', content: msg, log_type: 'system' })

      if (outcome === 'dead') setCombatOver('defeat')
    } catch (e) {
      setError(e.message)
    } finally {
      processingRef.current = false
      setIsProcessing(false)
    }
  }

  const handleEndCombat = async () => {
    if (!confirm('确定强制结束战斗并返回探索？')) return
    try {
      await gameApi.endCombat(sessionId)
      navigate(`/adventure/${sessionId}`)
    } catch (e) { setError(e.message) }
  }

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

  const { turn_order = [], current_turn_index = 0, round_number = 1,
    entity_positions = {}, entities = {} } = combat
  const currentTurnEntry = turn_order[current_turn_index]
  const playerTurn = isPlayerTurn(combat)

  const playerEntity = playerId ? entities[playerId] : null
  const playerDying  = playerEntity && playerEntity.hp_current <= 0 && !playerEntity.death_saves?.stable
  const selectedEntity = selectedTarget ? entities[selectedTarget] : null

  // 行动配额（从服务端 turn_state 读取，回退到本地状态）
  const ts = (playerTurn ? turnState : null) || null
  const actionUsed    = ts?.action_used       ?? false
  const bonusUsed     = ts?.bonus_action_used ?? false
  const movementUsed  = ts?.movement_used     ?? 0
  const movementMax   = ts?.movement_max      ?? 6
  const movementLeft  = movementMax - movementUsed
  const disengaged    = ts?.disengaged     ?? false

  // Chebyshev distance (used for movement range highlighting)
  const _chebyshev = (a, b) => Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y))

  // Player position for movement range highlighting
  const playerPos = playerId ? entity_positions[playerId] : null

  // ── 威胁区：每个存活敌人 Chebyshev ≤ 1 的格子标记为威胁 ──
  const threatCells = useMemo(() => {
    const set = new Set()
    if (!showThreat || !combat) return set
    for (const [id, pos] of Object.entries(entity_positions)) {
      const ent = entities[id]
      if (!ent || !ent.is_enemy || (ent.hp_current ?? 0) <= 0) continue
      // 近战威胁：相邻 8 格 + 自身格
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if (dx === 0 && dy === 0) continue
          set.add(`${pos.x + dx}_${pos.y + dy}`)
        }
      }
    }
    return set
  }, [showThreat, combat, entity_positions, entities])

  // ── AoE 预览：hover 某格时，以该格为中心半径 R 内的所有格 ──
  const aoeCells = useMemo(() => {
    const out = { center: null, ring: new Set() }
    if (!aoePreview || !aoeHover) return out
    const [cx, cy] = aoeHover.split('_').map(Number)
    const R = aoePreview.radius || 1
    out.center = aoeHover
    for (let dy = -R; dy <= R; dy++) {
      for (let dx = -R; dx <= R; dx++) {
        // 圆形 AoE：欧几里得距离 ≤ R（含 R+0.5 使边界格好看）
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d <= R + 0.5) out.ring.add(`${cx + dx}_${cy + dy}`)
      }
    }
    return out
  }, [aoePreview, aoeHover])

  // 构建 20x20 格子数据
  const grid = Array.from({ length: GRID_ROWS }, (_, row) =>
    Array.from({ length: GRID_COLS }, (_, col) => {
      const entry = Object.entries(entity_positions).find(([, p]) => p.x === col && p.y === row)
      return { x: col, y: row, entityId: entry?.[0] || null, entity: entry ? entities[entry[0]] : null }
    })
  )

  // ═══════════════════════════════════════════════════════════
  // 新 iso 战场渲染（design v0.10）
  // 保留所有业务 handler / state；只重构视觉布局
  // ═══════════════════════════════════════════════════════════

  // Sprite key 派生
  const spriteKind = (ent) => {
    if (!ent) return 'paladin'
    if (ent.sprite) return ent.sprite
    if (ent.is_enemy) return 'cultist'
    return (ent.char_class || 'fighter').toLowerCase()
  }

  // 相机窗口（iso 视图显示 12x8 区域，居中在玩家）
  const GRID_W_TOTAL = 20, GRID_H_TOTAL = 12
  const VIEW_W = 12, VIEW_H = 8
  const playerPosV10 = combat?.entity_positions?.[playerId]
  const cam = (() => {
    const cx = Math.max(0, Math.min(GRID_W_TOTAL - VIEW_W, (playerPosV10?.x ?? 10) - VIEW_W / 2))
    const cy = Math.max(0, Math.min(GRID_H_TOTAL - VIEW_H, (playerPosV10?.y ?? 6) - VIEW_H / 2))
    return { x0: Math.floor(cx), y0: Math.floor(cy) }
  })()

  // 当前回合实体
  const currentTurnEntryV10 = combat?.turn_order?.[combat?.current_turn_index ?? 0]
  const isPlayerTurn_v10 = !!currentTurnEntryV10?.is_player

  // 走格索引
  const walls = new Set()
  const hazards = new Set()
  for (const [k, v] of Object.entries(combat?.grid_data || {})) {
    if (v === 'wall') walls.add(k)
    else if (v === 'hazard' || v === 'difficult') hazards.add(k)
  }

  const selectedTargetEntity = selectedTarget ? entities[selectedTarget] : null
  const targetCell = selectedTarget ? combat?.entity_positions?.[selectedTarget] : null

  // 先攻条（横向紧凑）
  const initiativeChips = (combat?.turn_order || []).map((t, i) => {
    const ent = entities[t.character_id]
    const hp = ent?.hp_current ?? 0
    const hpMax = ent?.hp_max ?? 1
    const pct = Math.max(0, Math.min(100, (hp / hpMax) * 100))
    const isCur = i === (combat?.current_turn_index ?? 0)
    const dead = hp <= 0
    return { ent, t, i, pct, isCur, dead, low: pct < 34 }
  })

  // 默认的技能栏（本地 fallback，若后端 /skill-bar 返回成功则替换）
  const defaultSkillBar = [
    { k: 'atk',   label: '攻击',     glyph: '⚔', cost: '动作', key: '1', kind: 'attack',  available: true },
    { k: 'spell', label: '法术',     glyph: '✧', cost: '动作', key: '2', kind: 'spell',   available: true },
    { k: 'shove', label: '推撞',     glyph: '↦', cost: '动作', key: '3', kind: 'attack',  available: true },
    { k: 'help',  label: '协助',     glyph: '☉', cost: '动作', key: '4', kind: 'bonus',   available: true },
    { k: 'dash',  label: '冲刺',     glyph: '»', cost: '动作', key: '5', kind: 'move',    available: true },
    { k: 'disg',  label: '脱离',     glyph: '↶', cost: '动作', key: '6', kind: 'move',    available: true },
    { k: 'dodge', label: '闪避',     glyph: '⊙', cost: '动作', key: '7', kind: 'bonus',   available: true },
    { k: 'death', label: '濒死',     glyph: '☠', cost: '—',   key: '8', kind: 'empty',   available: false },
    { k: 'empty', label: '',         glyph: '',  cost: '',    key: '9', kind: 'empty',   available: false },
    { k: 'pot',   label: '药剂',     glyph: '⚱', cost: '动作', key: '0', kind: 'bonus',   available: true },
  ]
  const skillBar = skillBarV10 && skillBarV10.length ? skillBarV10 : defaultSkillBar

  // 技能点击路由到现有 handler
  const onSkillClick = async (s) => {
    if (!s.available || isProcessing || !isPlayerTurn_v10) return
    try {
      switch (s.k) {
        case 'atk':
          if (!selectedTarget) { setError('请先选择目标'); return }
          await handleAttack(); break
        case 'smite':
          setError('神圣斩击将在命中后自动提示'); break
        case 'spell': case 'bless': case 'heal': case 'shield':
        case 'firebolt': case 'sacred_flame':
          setSpellModalOpen(true); break
        case 'shove':
          if (!selectedTarget) { setError('请先选择目标'); return }
          await gameApi.combatAction(sessionId, '推撞', selectedTarget, false)
          const fresh1 = await gameApi.getCombat(sessionId); setCombat(fresh1); break
        case 'help':
          setHelpMode(true); break
        case 'dash':       await handleDash?.(); break
        case 'disg':       await handleDisengage?.(); break
        case 'dodge':      await handleDodge?.(); break
        case 'lay':          await handleClassFeature?.('lay_on_hands'); break
        case 'second_wind':  await handleClassFeature?.('second_wind'); break
        case 'action_surge': await handleClassFeature?.('action_surge'); break
        case 'rage':         await handleClassFeature?.('rage'); break
        case 'cunning_action': await handleClassFeature?.('cunning_action_dash'); break
        case 'portent':      await handleClassFeature?.('portent'); break
        case 'ki_flurry':    await handleClassFeature?.('ki_flurry'); break
        case 'divine_sense': await handleClassFeature?.('divine_sense'); break
        case 'pot': case 'pot_heal':
          await gameApi.combatAction(sessionId, '饮用治疗药剂', null, false)
          const fresh2 = await gameApi.getCombat(sessionId); setCombat(fresh2); break
        default: break
      }
    } catch (e) { setError(e.message) }
  }

  // 移动：点击格子触发
  const handleMoveTo = async (x, y) => {
    if (!moveMode || isProcessing || !isPlayerTurn_v10) return
    try {
      const result = await gameApi.move(sessionId, playerId, x, y)
      if (result) {
        setCombat(prev => prev ? { ...prev, entity_positions: result.entity_positions || prev.entity_positions } : prev)
        if (result.turn_state) setTurnState(result.turn_state)
      }
      setMoveMode(false)
    } catch (e) { setError(e.message) }
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden',
      background: 'linear-gradient(180deg, #06040a 0%, #0a0604 100%)',
      position: 'relative', zIndex: 1,
    }}>
      <DiceRollerOverlay />

      {/* ── 多人联机：当前回合指示器 ── */}
      {room && currentTurnLabel && (
        <div style={{
          background: isMyTurnMP
            ? 'linear-gradient(90deg, rgba(74,138,74,0.4), rgba(74,138,74,0.15))'
            : 'linear-gradient(90deg, rgba(58,122,170,0.3), rgba(58,122,170,0.1))',
          borderBottom: '1px solid var(--amber)',
          padding: '5px 16px', color: 'var(--amber)',
          fontSize: 12, fontWeight: 'bold',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          zIndex: 5, flexShrink: 0,
        }}>
          <span>{currentTurnLabel}</span>
          <span style={{ fontSize: 11, opacity: 0.8 }}>
            {isMyTurnMP ? '你的回合' : '观战中…'} · 房间 {room.room_code}
          </span>
        </div>
      )}

      {/* ── 回合横幅 ── */}
      <div className="turn-banner">
        <span className="round-tag">R {combat?.round_number || 1}</span>
        <span style={{ color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '.2em', marginRight: 8 }}>轮到</span>
        <span className="active-name">{currentTurnEntryV10?.name || '—'}</span>
        {combatOver && (
          <span style={{ marginLeft: 14, color: combatOver === 'victory' ? 'var(--emerald-light)' : 'var(--blood-light)', fontFamily: 'var(--font-display)', fontSize: 13 }}>
            · {combatOver === 'victory' ? '🏆 胜利' : '💀 全灭'} ·
          </span>
        )}
        {/* 威胁区 toggle —— 右对齐 */}
        <span style={{ flex: 1 }} />
        <button
          onClick={() => { setShowThreat(v => !v); try { JuiceAudio.click() } catch (e) {} }}
          title="显示/隐藏敌人攻击范围"
          style={{
            background: showThreat ? 'rgba(240,64,64,.2)' : 'transparent',
            border: `1px solid ${showThreat ? 'rgba(240,80,80,.75)' : 'rgba(138,90,24,.5)'}`,
            color: showThreat ? '#ff9090' : 'var(--parchment-dark)',
            padding: '4px 10px',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            letterSpacing: '.15em',
            textTransform: 'uppercase',
            cursor: 'pointer',
            transition: 'all .15s',
          }}
        >⚔ 威胁区</button>
      </div>

      {/* ── 横向先攻条 ── */}
      <div className="init-ribbon">
        {initiativeChips.map(({ ent, t, i, pct, isCur, dead, low }) => (
          <div
            key={t.character_id}
            className={`unit-chip ${t.is_enemy ? 'enemy' : ''} ${isCur ? 'active' : ''} ${dead ? 'dead' : ''} ${low ? 'low' : ''}`}
            onClick={() => !dead && setSelectedTarget(t.character_id)}
            style={{ cursor: dead ? 'default' : 'pointer' }}
          >
            <div className="init-no">{t.initiative ?? '?'}</div>
            <div className="avatar" style={{ position: 'relative' }}>
              {(ent?.name || t.name || '?').slice(0, 1)}{dead && '×'}
              {low && !dead && <span className="avatar-crack" />}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment)', letterSpacing: '.08em', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {(ent?.name || t.name || '?').slice(0, 4)}
            </div>
            <div className="hp-tick"><div className="fill" style={{ width: `${pct}%` }} /></div>
            {ent?.conditions?.length > 0 && (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 1, marginTop: 2 }}>
                {ent.conditions.slice(0, 3).map((c, ci) => (
                  <span key={ci} style={{ fontSize: 8, color: '#f4a0a0' }} title={c}>⚠</span>
                ))}
              </div>
            )}
          </div>
        ))}
        <div style={{ flex: 1 }} />
      </div>

      {/* ── 战场 + 目标卡 + 伤害飘字 ── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'grid', placeItems: 'center', padding: '20px 20px 0', minHeight: 0 }}>
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(ellipse at 30% 40%, rgba(47,168,184,.08), transparent 60%), radial-gradient(ellipse at 80% 60%, rgba(196,40,40,.1), transparent 55%)' }} />

        <div className="iso-battlefield">
          <div className="iso-grid" style={{
            gridTemplateColumns: `repeat(${VIEW_W}, 54px)`,
            gridTemplateRows: `repeat(${VIEW_H}, 54px)`,
          }}>
            {Array.from({ length: VIEW_H }).flatMap((_, dy) =>
              Array.from({ length: VIEW_W }).map((_, dx) => {
                const x = cam.x0 + dx, y = cam.y0 + dy
                const key = `${x}_${y}`
                const isWall = walls.has(key)
                const isHazard = hazards.has(key)
                // 找该格上的实体
                const entryEntry = Object.entries(combat?.entity_positions || {})
                  .find(([, pos]) => pos?.x === x && pos?.y === y)
                const [entId] = entryEntry || []
                const ent = entId ? entities[entId] : null
                const isTarget = entId && entId === selectedTarget
                const isCurTurn = entId && entId === currentTurnEntryV10?.character_id

                let klass = ''
                if (isWall) klass = 'wall'
                else if (isTarget) klass = 'target'
                else if (isHazard) klass = 'hazard'

                // 威胁区与 AoE 覆盖层（非互斥，aoe 视觉上会盖过 threat，这符合期望）
                const isThreat = threatCells.has(key) && !isWall && !ent?.is_enemy
                const isAoeCenter = aoeCells.center === key
                const isAoeRing   = !isAoeCenter && aoeCells.ring.has(key) && !isWall

                return (
                  <div
                    key={key}
                    className={`iso-cell ${klass}${isThreat ? ' threat' : ''}${isAoeRing ? ' aoe' : ''}${isAoeCenter ? ' aoe-center' : ''}`}
                    onClick={() => {
                      if (ent && !isWall) {
                        setSelectedTarget(entId)
                      } else if (moveMode && !isWall) {
                        // 走现有移动流程
                        handleMoveTo?.(x, y)
                      }
                    }}
                    onMouseEnter={() => { if (aoePreview) setAoeHover(key) }}
                    onMouseLeave={() => { if (aoePreview && aoeHover === key) setAoeHover(null) }}
                  >
                    {ent && (
                      <div className={`iso-unit ${ent.is_enemy ? 'enemy' : (entId === playerId ? 'player' : 'ally')} ${isCurTurn ? 'active' : ''} ${(ent.hp_current / (ent.hp_max || 1)) < .34 ? 'low' : ''}`}
                        style={{
                          '--c-light': ent.is_enemy ? '#f04848' : (entId === playerId ? '#6ae884' : '#7fc8f8'),
                          '--c-dark':  ent.is_enemy ? '#3a0a0a' : (entId === playerId ? '#1a4a28' : '#143a5e'),
                          '--c-glow':  ent.is_enemy ? '#f04848' : (entId === playerId ? '#6ae884' : '#5fb8f8'),
                        }}>
                        <div className="base" />
                        <div className="sprite-wrap">
                          <Sprite kind={spriteKind(ent)} size={44} dead={ent.hp_current <= 0} />
                        </div>
                        <div className="micro-hp">
                          <div className="fill" style={{ width: `${Math.max(0, Math.min(100, (ent.hp_current / (ent.hp_max || 1)) * 100))}%` }} />
                        </div>
                        {isTarget && <div className="target-ring" />}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* 目标卡（含命中率预测） */}
        {selectedTargetEntity && (
          <div style={{ position: 'absolute', top: 20, right: 20, width: 230 }}>
            <div className="target-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="name">◈ {selectedTargetEntity.name}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.15em' }}>TARGET</span>
              </div>
              <div style={{ height: 8, background: '#0a0604', border: '1px solid rgba(196,40,40,.5)', marginTop: 6 }}>
                <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, (selectedTargetEntity.hp_current / (selectedTargetEntity.hp_max || 1)) * 100))}%`, background: 'linear-gradient(90deg, #f04040, #8a1818)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.3)' }} />
              </div>
              <div className="hit-pred">
                <span>HP <b style={{ color: '#f4a0a0' }}>{selectedTargetEntity.hp_current}/{selectedTargetEntity.hp_max}</b> · AC <b style={{ color: 'var(--parchment)' }}>{selectedTargetEntity.ac}</b></span>
              </div>
              {prediction && (
                <div style={{ borderTop: '1px solid rgba(138,90,24,.3)', marginTop: 8, paddingTop: 8 }}>
                  <div className="hit-pred">
                    <span>命中</span>
                    <span className="pct">{Math.round((prediction.hit_rate || 0) * 100)}%</span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--parchment-dark)', letterSpacing: '.08em', marginTop: 3 }}>
                    预期 <span style={{ color: 'var(--amber)', fontWeight: 700 }}>{prediction.expected_damage} {prediction.damage_type}</span>
                  </div>
                  {prediction.modifiers?.length > 0 && (
                    <div style={{ fontSize: 9, color: 'var(--parchment-dark)', marginTop: 2 }}>{prediction.modifiers.join(' · ')}</div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 伤害飘字 */}
        {floats.map(f => (
          <span key={f.id} className={`float-text ${f.kind}`} style={{ left: `${f.x}%`, top: `${f.y}%` }}>{f.val}</span>
        ))}

        {combatOver && (
          <div style={{
            position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
            padding: '24px 40px', background: 'rgba(10,6,4,.95)',
            border: `2px solid ${combatOver === 'victory' ? 'var(--emerald)' : 'var(--blood)'}`,
            textAlign: 'center', zIndex: 10,
          }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>{combatOver === 'victory' ? '🏆' : '💀'}</div>
            <div className="display-title" style={{ fontSize: 22, color: combatOver === 'victory' ? 'var(--emerald-light)' : 'var(--blood-light)' }}>
              {combatOver === 'victory' ? '战斗胜利' : '全队阵亡'}
            </div>
            <button onClick={async () => { await gameApi.endCombat?.(sessionId); navigate(`/adventure/${sessionId}`) }} className="btn-gold" style={{ marginTop: 16 }}>
              返回冒险 ►
            </button>
          </div>
        )}
      </div>

      {/* ═══ 底部 HUD ═══ */}
      <div className="combat-hud" style={{ flexShrink: 0 }}>
        {/* 左 · 当前角色 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="action-pips">
            <div className={`pip action ${turnState?.action_used ? 'used' : ''}`}><span>⚔</span></div>
            <div className={`pip bonus ${turnState?.bonus_action_used ? 'used' : ''}`}><span>✦</span></div>
            <div className={`pip react ${turnState?.reaction_used ? 'used' : ''}`}><span>⚡</span></div>
          </div>
          <div className="hud-portrait">
            <div className="big" style={{ position: 'relative' }}>
              {(session?.player?.name || 'P').slice(0, 1)}
              {(() => {
                const hp = session?.player?.hp_current ?? 0
                const hpMax = session?.player?.derived?.hp_max ?? 1
                return hp > 0 && hp / hpMax <= 0.25 ? <span className="avatar-crack" /> : null
              })()}
            </div>
            <div className="stats">
              <div className="name">{session?.player?.name || '玩家'}</div>
              <div className="sub">{playerClass || '?'} {playerSubclass ? `· ${playerSubclass} ` : ''}· Lv {playerLevel}</div>
              <div className={`hp-segmented ${(() => {
                const hp = session?.player?.hp_current ?? 0, hpMax = session?.player?.derived?.hp_max ?? 1
                return hp / hpMax < .34 ? 'low' : hp / hpMax < .67 ? 'mid' : ''
              })()}`}>
                {(() => {
                  const hp = session?.player?.hp_current ?? 0
                  const hpMax = session?.player?.derived?.hp_max ?? 1
                  const segs = 12
                  const filled = Math.round((hp / hpMax) * segs)
                  return Array.from({ length: segs }).map((_, i) => (
                    <div key={i} className={`seg ${i >= filled ? 'empty' : ''}`} />
                  ))
                })()}
              </div>
              <div className="hp-text">
                <span><span className="cur">{session?.player?.hp_current ?? 0}</span> / {session?.player?.derived?.hp_max ?? 0}</span>
                <span>移动 <b style={{ color: 'var(--arcane-light)' }}>{(turnState?.movement_max ?? 6) - (turnState?.movement_used ?? 0)}/{turnState?.movement_max ?? 6}</b></span>
              </div>
              <div className="stat-line">
                <span>AC <span className="v">{session?.player?.derived?.ac ?? 10}</span></span>
                <span>先攻 <span className="v">{(() => { const m = session?.player?.derived?.initiative ?? 0; return (m >= 0 ? '+' : '') + m })()}</span></span>
                {session?.player?.derived?.spell_save_dc && (
                  <span>DC <span className="v">{session.player.derived.spell_save_dc}</span></span>
                )}
              </div>
              {session?.player?.conditions?.length > 0 && (
                <div className="conditions">
                  {session.player.conditions.slice(0, 6).map((c, i) => (
                    <span key={i} className="cond-icon" title={c}>⚠</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 中 · 技能快捷栏 + 日志 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
          <div className="skill-bar">
            {skillBar.map(s => {
              const stats = computeSkillStats(s, session?.player, entities[selectedTarget])
              const info = SKILL_INFO[s.k] || {}
              return (
                <div
                  key={s.k}
                  className={`slot-key ${s.kind} ${!s.available ? 'used' : ''}`}
                  onClick={() => onSkillClick(s)}
                  onMouseEnter={() => { try { JuiceAudio.hover() } catch (e) {} }}
                  style={{ cursor: s.available && isPlayerTurn_v10 ? 'pointer' : 'not-allowed' }}
                >
                  <span className="hot">{s.key}</span>
                  <span className="glyph">{s.glyph}</span>
                  {s.cost && <span className="cost">{String(s.cost).split('·')[0]}</span>}

                  {/* 技能 tooltip */}
                  {s.label && (
                    <div className="skill-tooltip">
                      <div className="t-name">{s.label}</div>
                      <div className="t-meta">
                        {s.kind === 'attack' ? '攻击' : s.kind === 'spell' ? '法术' : s.kind === 'bonus' ? '附赠' : s.kind === 'move' ? '移动' : '—'}
                        {' · '}{s.cost || '—'}
                        {!s.available && <span style={{ color: '#f47070', marginLeft: 6 }}>✕ 不可用</span>}
                      </div>
                      {stats && stats.length > 0 && stats.map((r, ri) => (
                        <div key={ri} className="t-row">
                          <span>{r.label}</span>
                          <b>{r.value}</b>
                        </div>
                      ))}
                      {(s.reason || info.desc) && (
                        <div className="t-desc">{s.reason || info.desc}</div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <div className="slot-label-bar">
            {skillBar.map(s => <span key={s.k}>{s.label || '—'}</span>)}
          </div>

          <div className="combat-log" style={{ marginTop: 4 }}>
            {logs.slice(-8).map((log, i) => (
              <div key={log.id || i} className={`log-entry ${
                log.dice_result?.is_crit ? 'crit' :
                log.dice_result?.is_fumble ? 'miss' :
                log.log_type === 'combat' ? 'dmg' : 'normal'
              }`}>
                <span className="roll">
                  {log.dice_result ? `d20=${log.dice_result.d20 || log.dice_result.total}` : '日志'}
                </span>
                <span>{(log.content || '').slice(0, 80)}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* 右 · 法术位 + 结束回合 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{
            padding: '8px 10px',
            background: 'linear-gradient(180deg, #1a1208, #0a0604)',
            border: '1px solid rgba(138,90,24,.5)',
            boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
          }}>
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 10, color: 'var(--amber)', letterSpacing: '.2em', textTransform: 'uppercase', marginBottom: 6 }}>
              ✦ 法术位
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(playerSpellSlots || {}).filter(([lvl, cur]) => cur > 0 || /^(1st|2nd|3rd)$/.test(lvl)).slice(0, 4).map(([lvl, cur]) => {
                const max = session?.player?.derived?.spell_slots_max?.[lvl] || cur
                return (
                  <div key={lvl} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--arcane-light)', letterSpacing: '.08em', width: 24 }}>{lvl}</span>
                    <div className="spell-slots">
                      {Array.from({ length: Math.max(max, cur) }).map((_, i) => (
                        <div key={i} className={`slot-gem ${i >= cur ? 'used' : ''}`} />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
            {session?.player?.concentration && (
              <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(138,90,24,.3)', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.1em' }}>
                专注 <span style={{ color: 'var(--flame)' }}>{session.player.concentration}</span>
              </div>
            )}
          </div>

          <button
            className="end-turn-mega"
            onClick={handleEndTurn}
            disabled={isProcessing || !isPlayerTurn_v10}
          >☰ 结束回合</button>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
              onClick={() => setMoveMode(m => !m)}
              disabled={isProcessing || !isPlayerTurn_v10}>
              {moveMode ? '✓ 移动' : '► 移动'}
            </button>
            <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
              onClick={() => setIsRanged(r => !r)}
              disabled={isProcessing || !isPlayerTurn_v10}>
              {isRanged ? '✓ 远程' : '⊙ 远程'}
            </button>
            <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
              onClick={() => navigate(`/adventure/${sessionId}`)}>
              ⏎ 返回
            </button>
            <button className="btn-danger" style={{ fontSize: 9, padding: '5px 8px' }}
              onClick={async () => { if (confirm('强制结束战斗？')) { await gameApi.endCombat?.(sessionId); navigate(`/adventure/${sessionId}`) } }}>
              终止
            </button>
          </div>
        </div>
      </div>

      {/* ── Smite prompt（保留原版弹窗） ── */}
      {smitePrompt?.show && (
        <div className="fixed inset-0" style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)' }}>
          <div style={{ padding: 18, width: 320, background: 'var(--obsidian)', border: '1px solid var(--amber)' }}>
            <p style={{ color: 'var(--amber)', fontFamily: 'var(--font-display)', fontSize: 14, marginBottom: 10 }}>
              命中！是否使用神圣斩击？
            </p>
            <p style={{ color: 'var(--parchment-dark)', fontSize: 12, marginBottom: 12 }}>
              消耗 1 环法术位造成 +2d8 辐光伤害（每升一环 +1d8）
            </p>
            <div style={{ display: 'flex', gap: 6 }}>
              {[1, 2, 3, 4, 5].filter(l => (playerSpellSlots[['1st','2nd','3rd','4th','5th'][l-1]] || 0) > 0).map(l => (
                <button key={l} className="btn-gold" style={{ flex: 1, padding: 8, fontSize: 11 }} onClick={() => handleSmite(l)}>
                  {l}环
                </button>
              ))}
              <button className="btn-ghost" style={{ padding: 8, fontSize: 11 }} onClick={() => setSmitePrompt(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* ── 法术弹窗（保留） ── */}
      {spellModalOpen && (
        <SpellModal
          spells={playerAvailableSpells}
          cantrips={playerCantrips}
          slots={playerSpellSlots}
          onCast={handleCastSpell}
          onClose={() => { setSpellModalOpen(false); clearAoePreview() }}
          onSpellHover={(spell) => {
            if (spell && spell.aoe) {
              const radius = aoeRadiusCells(spell)
              setAoePreview({ radius, spellName: spell.name })
              // 自动以当前选中目标为预览中心（没选就以玩家所在格）
              const centerKey = selectedTarget && entity_positions[selectedTarget]
                ? `${entity_positions[selectedTarget].x}_${entity_positions[selectedTarget].y}`
                : (playerPos ? `${playerPos.x}_${playerPos.y}` : null)
              setAoeHover(centerKey)
            } else {
              setAoePreview(null)
              setAoeHover(null)
            }
          }}
        />
      )}

      {/* ── 战技弹窗（保留） ── */}
      {maneuverModalOpen && (
        <ManeuverModal
          diceType={playerSubclassEffects?.superiority_die || 'd8'}
          remaining={classResources?.superiority_dice_remaining ?? 0}
          onUse={handleManeuver}
          onClose={() => setManeuverModalOpen(false)}
        />
      )}

      {/* ── 反应弹窗（保留） ── */}
      {reactionPrompt && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)' }}>
          <div style={{ padding: 20, width: 360, background: 'var(--obsidian)', border: '1px solid var(--flame)' }}>
            <p style={{ color: 'var(--flame)', fontFamily: 'var(--font-display)', fontSize: 14, marginBottom: 8 }}>⚡ 反应触发</p>
            <p style={{ color: 'var(--parchment)', fontSize: 12, marginBottom: 12 }}>{reactionPrompt.context || '选择反应'}</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {(reactionPrompt.options || []).map((opt, i) => (
                <button key={i} className="btn-gold" style={{ padding: 8, fontSize: 12, textAlign: 'left' }}
                  onClick={() => handleReaction(opt.type, opt.target_id)}>
                  {opt.label}
                </button>
              ))}
              <button className="btn-ghost" style={{ padding: 6, fontSize: 11 }} onClick={() => setReactionPrompt(null)}>
                放弃反应
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div style={{ position: 'fixed', bottom: 16, left: '50%', transform: 'translateX(-50%)',
          padding: '8px 16px', background: 'rgba(139,32,32,.9)', color: '#fff',
          border: '1px solid var(--blood)', borderRadius: 4, zIndex: 999, fontSize: 12,
        }}>⚠ {error}</div>
      )}
    </div>
  )
}
