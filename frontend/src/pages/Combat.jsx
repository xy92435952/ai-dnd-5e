import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { gameApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import DiceRollerOverlay, { rollDice3D } from '../components/DiceRollerOverlay'
import {
  ShieldIcon, SwordIcon, SkullIcon, DiceD20Icon,
  AttackIcon, SpellIcon, MoveIcon, DefendIcon, DashIcon,
  DisengageIcon, HelpIcon, OffhandIcon, BackIcon, HeartIcon,
} from '../components/Icons'

const GRID_COLS = 20
const GRID_ROWS = 20
const CELL = 36 // px per cell — smaller to fit more on screen

export default function Combat() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { showDice } = useGameStore()

  const [combat, setCombat] = useState(null)
  const [logs, setLogs] = useState([])
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [combatOver, setCombatOver] = useState(null) // null | 'victory' | 'defeat'
  const [error, setError] = useState('')

  // 移动模式
  const [moveMode, setMoveMode] = useState(false)
  const [isRanged, setIsRanged] = useState(false)

  // 协助模式（选择队友）
  const [helpMode, setHelpMode] = useState(false)

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

  // 先攻骰子动画标记（仅第一轮第一次显示）
  const [initiativeShown, setInitiativeShown] = useState(false)

  const logsEndRef = useRef(null)
  const gridContainerRef = useRef(null)
  const aiTimer = useRef(null)
  const processingRef = useRef(false)

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

      const session = await gameApi.getSession(sessionId)
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

      // 先攻骰子动画（仅第1轮首次加载时展示）
      if (data.round_number === 1 && !initiativeShown && pid) {
        const playerEntry = (data.turn_order || []).find(t => t.is_player)
        if (playerEntry && playerEntry.initiative != null) {
          // 从先攻值反推 d20 结果（先攻 = d20 + DEX mod）
          // turn_order 可能存有 d20 字段，否则直接显示先攻总值
          const d20Val = playerEntry.d20 || playerEntry.initiative
          showDice({ faces: 20, result: d20Val, label: '先攻检定' })
          setInitiativeShown(true)
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
      const result = await gameApi.smite(sessionId, slotLevel)

      // 播放斩击骰子动画（smite_dice 格式如 "3d8"）
      if (result.smite_dice && result.smite_damage) {
        const smiteMatch = result.smite_dice.match(/(\d*)d(\d+)/)
        const smiteCount = smiteMatch ? parseInt(smiteMatch[1] || '1') : 1
        const faces = smiteMatch ? parseInt(smiteMatch[2]) : 8
        showDice({ faces, result: result.smite_damage, label: '神圣斩击', count: smiteCount })
      }

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
      const result = await gameApi.classFeature(sessionId, featureName)
      // 骰子动画
      if (result.dice_roll) {
        showDice({ faces: result.dice_roll.faces, result: result.dice_roll.result, label: result.dice_roll.label })
      }
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
      const result = await gameApi.useReaction(sessionId, reactionType, targetId)
      if (result.dice_roll) {
        showDice({ faces: result.dice_roll.faces, result: result.dice_roll.result, label: result.dice_roll.label, count: result.dice_roll.count || 1 })
      }
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
      const result = await gameApi.maneuver(sessionId, maneuverName, selectedTarget)
      // 战技骰子动画
      if (result.dice_roll) {
        showDice({ faces: result.dice_roll.faces, result: result.dice_roll.result, label: result.dice_roll.label })
      }
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

          // 野蛮魔法涌动显示 + 骰子动画
          if (confirmResult.wild_magic_check) {
            const wmc = confirmResult.wild_magic_check
            // 延迟显示（等法术骰子动画结束）
            setTimeout(() => {
              if (wmc.triggered && confirmResult.wild_magic_surge) {
                // 涌动触发！先显示 d20=1 检测骰
                if (!wmc.forced) {
                  showDice({ faces: 20, result: wmc.d20, label: '🌀 野蛮魔法涌动！' })
                }
                addLog({
                  role: 'system',
                  content: `🌀 野蛮魔法涌动！${wmc.forced ? '（混沌之潮反噬）' : `d20=${wmc.d20}`} — ${confirmResult.wild_magic_surge.effect}`,
                  log_type: 'system',
                })
                // 延迟后显示涌动效果骰（d20 涌动表）
                if (wmc.surge_roll) {
                  setTimeout(() => {
                    showDice({ faces: 20, result: wmc.surge_roll, label: `涌动效果 #${wmc.surge_roll}` })
                  }, 3500)
                }
              } else if (!wmc.triggered) {
                // 未触发，显示检测骰子
                showDice({ faces: 20, result: wmc.d20, label: '野蛮魔法检测' })
                addLog({
                  role: 'system',
                  content: `🎲 野蛮魔法检测: d20=${wmc.d20}（安全，未触发涌动）`,
                  log_type: 'system',
                })
              }
            }, totalValue > 0 ? 3000 : 500)
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

  // 构建 20x20 格子数据
  const grid = Array.from({ length: GRID_ROWS }, (_, row) =>
    Array.from({ length: GRID_COLS }, (_, col) => {
      const entry = Object.entries(entity_positions).find(([, p]) => p.x === col && p.y === row)
      return { x: col, y: row, entityId: entry?.[0] || null, entity: entry ? entities[entry[0]] : null }
    })
  )

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: 'var(--bg)' }}>

      {/* 骰子动画浮层 */}
      <DiceRollerOverlay />

      {/* 战技选择 Modal */}
      {maneuverModalOpen && (
        <ManeuverModal
          diceType={playerSubclassEffects?.superiority_die || 'd8'}
          remaining={classResources?.superiority_dice_remaining ?? 0}
          onUse={handleManeuver}
          onClose={() => setManeuverModalOpen(false)}
        />
      )}

      {/* 法术选择 Modal */}
      {spellModalOpen && (
        <SpellModal
          spells={playerAvailableSpells}
          cantrips={playerCantrips}
          slots={playerSpellSlots}
          onCast={handleCastSpell}
          onClose={() => setSpellModalOpen(false)}
        />
      )}

      {/* 神圣斩击选择 Modal */}
      {smitePrompt?.show && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.6)' }}>
          <div className="panel p-4 w-80" style={{ background: 'var(--bg2)', borderColor: 'var(--gold)' }}>
            <p className="font-bold text-sm mb-3" style={{ color: 'var(--gold)' }}>
              命中！是否使用神圣斩击？
            </p>
            <p className="text-xs mb-3" style={{ color: 'var(--text-dim)' }}>
              消耗法术位追加辐光伤害（2d8 + 每环+1d8）
            </p>
            <div className="flex flex-wrap gap-2 mb-3">
              {[1,2,3,4,5].map(lvl => {
                const slotKey = ['1st','2nd','3rd','4th','5th'][lvl-1]
                const avail = playerSpellSlots[slotKey] || 0
                return avail > 0 ? (
                  <button key={lvl} className="btn-fantasy text-xs py-1 px-3"
                    style={{ borderColor: 'var(--gold)' }}
                    onClick={() => handleSmite(lvl)}>
                    {lvl}环 ({avail}槽)
                  </button>
                ) : null
              })}
            </div>
            <button className="btn-fantasy text-xs py-1 w-full"
              onClick={() => setSmitePrompt(null)}>
              不使用
            </button>
          </div>
        </div>
      )}

      {/* 反应提示 Modal */}
      {reactionPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
          <div className="panel p-5" style={{ background: 'var(--bg2)', borderColor: 'var(--red)', maxWidth: 420, width: '90%', border: '2px solid var(--red)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span style={{ fontSize: 24 }}>⚡</span>
              <div>
                <p style={{ color: 'var(--red-light)', fontWeight: 700, fontSize: 15, margin: 0 }}>你被攻击了！是否使用反应？</p>
                <p style={{ color: 'var(--text-dim)', fontSize: 11, margin: '4px 0 0' }}>
                  攻击者: {reactionPrompt.attacker_name} | 攻击骰: {reactionPrompt.attack_roll} | 你的AC: {reactionPrompt.player_ac}
                  {reactionPrompt.incoming_damage > 0 && ` | 伤害: ${reactionPrompt.incoming_damage}`}
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
              {(reactionPrompt.available_reactions || []).map(r => (
                <button key={r.id} className="panel" style={{
                  padding: '10px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10,
                  border: '1px solid var(--wood-light)', background: 'var(--bg)', textAlign: 'left',
                  transition: 'border-color 0.2s',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--red-light)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--wood-light)'}
                onClick={() => handleReaction(r.id, reactionPrompt.attacker_id)}>
                  <div style={{ flex: 1 }}>
                    <p style={{ color: 'var(--text-bright)', fontWeight: 600, fontSize: 13, margin: 0 }}>
                      {r.name}
                    </p>
                    <p style={{ color: 'var(--text-dim)', fontSize: 11, margin: '2px 0 0' }}>
                      {r.effect}
                      {r.cost && <span style={{ color: 'var(--gold-dim)', marginLeft: 6 }}>({r.cost})</span>}
                    </p>
                  </div>
                  {r.slots_remaining != null && (
                    <span style={{ color: 'var(--gold)', fontSize: 11, whiteSpace: 'nowrap' }}>
                      {r.slots_remaining}槽
                    </span>
                  )}
                </button>
              ))}
            </div>

            <button className="btn-fantasy" style={{ width: '100%', fontSize: 12, opacity: 0.7 }}
              onClick={skipReaction}>
              不使用反应
            </button>
          </div>
        </div>
      )}

      {/* 顶部栏 */}
      <div className="flex items-center justify-between px-4 py-2 border-b flex-shrink-0"
        style={{ borderColor: 'var(--wood-light)', background: 'var(--bg2)' }}>
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold px-2 py-1 rounded" style={{ background: 'var(--red)', color: 'var(--red-light)' }}>
            <SwordIcon size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            战斗
          </span>
          <span className="font-semibold" style={{ color: 'var(--gold)' }}>第 {round_number} 轮</span>
        </div>
        <div className="text-sm" style={{ color: playerTurn ? 'var(--blue-light)' : 'var(--red-light)' }}>
          {isProcessing
            ? <span className="animate-pulse">AI行动中...</span>
            : `当前行动：${currentTurnEntry?.name || '?'}`}
        </div>
        <div className="flex items-center gap-2">
          {playerId && (
            <button className="btn-fantasy text-xs py-1" onClick={() => navigate(`/character/${playerId}`)}>
              <ShieldIcon size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
              角色
            </button>
          )}
          <button className="btn-fantasy text-xs py-1" onClick={handleEndCombat}>
            <BackIcon size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            强制结束
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">

        {/* 左侧：先攻顺序 */}
        <div className="w-44 flex-shrink-0 border-r overflow-y-auto p-2 space-y-1"
          style={{ borderColor: 'var(--wood-light)', background: 'var(--bg2)' }}>
          <p className="text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>先攻顺序</p>
          {turn_order.map((entry, idx) => {
            const ent = entities[entry.character_id]
            const isCurrent = idx === current_turn_index
            const isDead = ent && ent.hp_current <= 0
            const hpPct = ent ? Math.max(0, ent.hp_current / ent.hp_max * 100) : 0
            const entTs = combat.turn_states?.[entry.character_id]

            return (
              <div key={`${entry.character_id}-${idx}`}
                className={`init-entry ${isCurrent ? 'init-entry-active' : ''}`}
                style={{ opacity: isDead ? 0.3 : 1 }}>
                <div className="flex items-center gap-1.5">
                  <span style={{ display: 'flex', alignItems: 'center' }}>
                    {entry.is_player
                      ? <ShieldIcon size={14} color="var(--blue-light)" />
                      : ent?.is_enemy
                        ? <SkullIcon size={14} color="var(--red-light)" />
                        : <SwordIcon size={14} color="var(--green-light)" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold truncate"
                      style={{ color: isCurrent ? 'var(--gold)' : 'var(--parchment)' }}>{entry.name}</p>
                    <p className="text-xs" style={{ color: 'var(--text-dim)' }}>先攻 {entry.initiative}</p>
                  </div>
                </div>
                {ent && (
                  <div className="mt-1.5">
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--wood)' }}>
                      <div className="h-full rounded-full transition-all"
                        style={{
                          width: `${hpPct}%`,
                          background: hpPct > 50 ? 'var(--green-light)' : hpPct > 25 ? 'var(--gold)' : 'var(--red-light)',
                        }} />
                    </div>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{ent.hp_current}/{ent.hp_max} HP</p>
                    {/* 状态条件 */}
                    {ent.conditions?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {ent.conditions.map(c => {
                          const dur = ent.condition_durations?.[c]
                          return (
                            <span key={c} style={{
                              fontSize: 9, padding: '1px 4px', borderRadius: 3,
                              background: 'rgba(139,32,32,0.3)', color: 'var(--red-light)', lineHeight: 1.4,
                              border: '1px solid var(--red)',
                            }}>
                              {c}{dur != null ? ` ${dur}r` : ' \u221e'}
                            </span>
                          )
                        })}
                      </div>
                    )}
                    {/* 被协助徽章 */}
                    {entTs?.being_helped && (
                      <span style={{
                        fontSize: 9, padding: '1px 4px', borderRadius: 3, marginTop: 2, display: 'inline-block',
                        background: 'rgba(26,58,90,0.3)', color: 'var(--blue-light)',
                        border: '1px solid var(--blue)',
                      }}>被协助</span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* 中间：网格地图 */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* 模式提示条 */}
          {(moveMode || helpMode) && (
            <div className="text-center py-1 text-xs font-semibold"
              style={{ background: helpMode ? 'var(--blue)' : 'var(--green)', color: helpMode ? 'var(--blue-light)' : 'var(--green-light)' }}>
              {helpMode
                ? '协助模式：点击地图上的队友选择协助对象'
                : `移动模式：点击空格子移动（剩余 ${movementLeft} 格）-- 再次点击「移动」取消`}
            </div>
          )}

          <div ref={gridContainerRef} className="flex-1 overflow-auto p-2 flex items-center justify-center">
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${GRID_COLS}, ${CELL}px)`,
              gridTemplateRows: `repeat(${GRID_ROWS}, ${CELL}px)`,
              gap: '1px',
              background: 'var(--wood)',
              border: '2px solid var(--wood-light)',
              borderRadius: 4,
              flexShrink: 0,
            }}>
              {grid.flat().map((cell) => {
                const isDead = cell.entity && cell.entity.hp_current <= 0
                const isSelected = selectedTarget === cell.entityId
                const isTargetable = playerTurn && !isProcessing && !moveMode && !helpMode &&
                  cell.entity?.is_enemy && cell.entity?.hp_current > 0
                const isHelpable = helpMode && playerTurn && !isProcessing &&
                  cell.entity && !cell.entity.is_enemy && cell.entity.id !== playerId && cell.entity.hp_current > 0
                const isMoveTarget = moveMode && playerTurn && !isProcessing && !cell.entity
                const hpPct = cell.entity
                  ? Math.max(0, cell.entity.hp_current / cell.entity.hp_max * 100) : 0

                // Movement range highlighting
                const reachable = moveMode && playerPos && !cell.entity
                  ? _chebyshev(playerPos, { x: cell.x, y: cell.y }) <= movementLeft
                  : false
                const outOfRange = moveMode && playerPos && !cell.entity && !reachable

                // Determine cell CSS class
                let cellClass = 'battle-cell'
                if (cell.entity?.is_player) cellClass += ' battle-cell-player'
                else if (cell.entity?.is_enemy) cellClass += ' battle-cell-enemy'
                else if (cell.entity) cellClass += ' battle-cell-ally'

                const cellBg = isSelected ? 'rgba(196,64,64,0.35)'
                  : isHelpable ? 'rgba(58,122,170,0.2)'
                  : reachable ? 'rgba(201,168,76,0.08)'
                  : isMoveTarget ? 'rgba(74,138,74,0.15)'
                  : undefined // let CSS class handle default

                return (
                  <div key={`${cell.x}-${cell.y}`}
                    className={cellClass}
                    onClick={() => {
                      if (moveMode && outOfRange) {
                        setError('超出移动范围！')
                        return
                      }
                      handleCellClick(cell.x, cell.y)
                    }}
                    style={{
                      width: CELL, height: CELL,
                      ...(cellBg ? { background: cellBg } : {}),
                      ...(outOfRange ? { opacity: 0.35 } : {}),
                      cursor: reachable ? 'crosshair'
                        : isMoveTarget || isTargetable || isHelpable ? 'crosshair'
                        : outOfRange ? 'not-allowed'
                        : cell.entity ? 'pointer' : 'default',
                      position: 'relative',
                      border: isSelected ? '1px solid var(--red-light)'
                        : isHelpable ? '1px solid rgba(58,122,170,0.6)'
                        : reachable ? '1px solid rgba(201,168,76,0.35)'
                        : isMoveTarget ? '1px solid rgba(74,138,74,0.4)'
                        : isTargetable ? '1px solid rgba(196,64,64,0.5)' : undefined,
                      transition: 'background 0.1s, opacity 0.15s',
                      boxSizing: 'border-box',
                    }}>
                    {cell.entity && (
                      <>
                        <span style={{ fontSize: 22, lineHeight: 1, opacity: isDead ? 0.25 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          {isDead
                            ? <SkullIcon size={20} color="var(--text-dim)" />
                            : cell.entity.is_player
                              ? <ShieldIcon size={20} color="var(--blue-light)" />
                              : cell.entity.is_enemy
                                ? <SkullIcon size={20} color="var(--red-light)" />
                                : <SwordIcon size={20} color="var(--green-light)" />}
                        </span>
                        {!isDead && (
                          <div style={{
                            position: 'absolute', bottom: 3, left: 4, right: 4,
                            height: 3, background: 'var(--wood)', borderRadius: 2,
                          }}>
                            <div style={{
                              height: '100%', borderRadius: 2,
                              width: `${hpPct}%`,
                              background: hpPct > 50 ? 'var(--green-light)' : hpPct > 25 ? 'var(--gold)' : 'var(--red-light)',
                            }} />
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* 行动栏 */}
          <div className="border-t flex-shrink-0 p-3" style={{ borderColor: 'var(--wood-light)', background: 'var(--bg2)' }}>
            {error && <p className="text-xs mb-2" style={{ color: 'var(--red-light)' }}>
              <span style={{ marginRight: 4 }}>!</span>{error}
            </p>}

            {/* 濒死豁免面板 */}
            {playerDying && !combatOver && (
              <div className="panel mb-3 p-3" style={{ borderColor: 'var(--red)' }}>
                <p className="text-sm font-bold mb-2" style={{ color: 'var(--red-light)' }}>
                  <SkullIcon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                  {playerEntity?.name} 濒死中
                </p>
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex gap-1">
                    {[0,1,2].map(i => (
                      <div key={i} className="w-4 h-4 rounded-full border"
                        style={{
                          borderColor: 'var(--green-light)',
                          background: i < (playerEntity?.death_saves?.successes || 0) ? 'var(--green-light)' : 'transparent',
                        }} />
                    ))}
                    <span className="text-xs ml-1" style={{ color: 'var(--green-light)' }}>成功</span>
                  </div>
                  <div className="flex gap-1">
                    {[0,1,2].map(i => (
                      <div key={i} className="w-4 h-4 rounded-full border"
                        style={{
                          borderColor: 'var(--red-light)',
                          background: i < (playerEntity?.death_saves?.failures || 0) ? 'var(--red-light)' : 'transparent',
                        }} />
                    ))}
                    <span className="text-xs ml-1" style={{ color: 'var(--red-light)' }}>失败</span>
                  </div>
                </div>
                <button className="btn-fantasy w-full py-2 text-sm"
                  style={{ borderColor: 'var(--red-light)', color: 'var(--red-light)' }}
                  disabled={isProcessing} onClick={handleDeathSave}>
                  <DiceD20Icon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                  {isProcessing ? '检定中...' : '进行濒死豁免'}
                </button>
                <p className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>3次成功=稳定，3次失败=阵亡，自然20=立即复活</p>
              </div>
            )}

            {combatOver ? (
              <div className="text-center py-1">
                <p className="text-lg font-bold mb-3"
                  style={{ color: combatOver === 'victory' ? 'var(--gold)' : 'var(--red-light)' }}>
                  {combatOver === 'victory'
                    ? <><SwordIcon size={18} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />胜利！所有敌人已被击倒！</>
                    : <><SkullIcon size={18} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />队伍全灭，冒险结束...</>}
                </p>
                <button className="btn-gold px-6 py-2"
                  onClick={() => navigate(`/adventure/${sessionId}`)}>
                  <BackIcon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                  返回探索
                </button>
              </div>
            ) : playerTurn && !isProcessing ? (
              <div>
                {/* 目标信息 */}
                {selectedEntity && (
                  <p className="text-xs mb-2" style={{ color: 'var(--red-light)' }}>
                    <SkullIcon size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                    目标：{selectedEntity.name}（{selectedEntity.hp_current}/{selectedEntity.hp_max} HP · AC {selectedEntity.ac}）
                  </p>
                )}

                {/* 行动配额显示 */}
                {ts && (
                  <div className="flex gap-3 mb-2 text-xs" style={{ color: 'var(--text-dim)' }}>
                    <span style={{ color: actionUsed ? 'var(--wood-light)' : 'var(--gold)', display: 'flex', alignItems: 'center', gap: 3 }}>
                      <AttackIcon size={12} /> 行动{actionUsed ? '（已用）' : ''}
                    </span>
                    <span style={{ color: movementLeft <= 0 ? 'var(--wood-light)' : 'var(--green-light)', display: 'flex', alignItems: 'center', gap: 3 }}>
                      <MoveIcon size={12} /> 移动 {movementUsed}/{movementMax} 格
                    </span>
                    {disengaged && (
                      <span style={{ color: 'var(--blue-light)', display: 'flex', alignItems: 'center', gap: 3 }}>
                        <DisengageIcon size={12} /> 脱离接战
                      </span>
                    )}
                  </div>
                )}

                {/* 行动按钮区 */}
                <div className="flex gap-2 flex-wrap items-center mb-2">
                  {/* 远程/近战切换 */}
                  <button className="action-btn"
                    style={{ width: 'auto', borderColor: isRanged ? 'var(--blue-light)' : 'var(--wood-light)' }}
                    onClick={() => setIsRanged(r => !r)}>
                    {isRanged
                      ? <><AttackIcon size={14} color="var(--blue-light)" /> 远程</>
                      : <><AttackIcon size={14} /> 近战</>}
                  </button>

                  {/* 攻击 (支持 Extra Attack：attacks_made < attacks_max 时仍可攻击) */}
                  <button className="action-btn action-btn-attack"
                    style={{ width: 'auto', opacity: actionUsed ? 0.35 : 1 }}
                    disabled={!selectedTarget || actionUsed} onClick={handleAttack}>
                    <AttackIcon size={14} color="var(--red-light)" /> 攻击{!selectedTarget && <span className="ml-1 text-xs" style={{ color: 'var(--text-dim)' }}>（先选目标）</span>}
                  </button>

                  {/* 副手攻击（双武器战斗：主手已攻击 + 附赠行动未用） */}
                  {actionUsed && !bonusUsed && (
                    <button className="action-btn action-btn-attack"
                      style={{ width: 'auto', opacity: selectedTarget ? 1 : 0.35 }}
                      disabled={!selectedTarget} onClick={handleOffhandAttack}>
                      <OffhandIcon size={14} color="var(--red-light)" /> 副手攻击{!selectedTarget && <span className="ml-1 text-xs" style={{ color: 'var(--text-dim)' }}>（选目标）</span>}
                    </button>
                  )}

                  {/* 移动 */}
                  <button
                    className="action-btn action-btn-move"
                    style={{
                      width: 'auto',
                      borderColor: moveMode ? 'var(--green-light)' : undefined,
                      opacity: movementLeft <= 0 ? 0.35 : 1,
                    }}
                    disabled={movementLeft <= 0}
                    onClick={handleMoveClick}
                  >
                    <MoveIcon size={14} color="var(--blue-light)" /> {moveMode ? '取消移动' : `移动（${movementLeft}格）`}
                  </button>

                  {/* 闪避 */}
                  <button className="action-btn"
                    style={{ width: 'auto', opacity: actionUsed ? 0.35 : 1 }}
                    disabled={actionUsed} onClick={handleDodge}>
                    <DefendIcon size={14} /> 闪避
                  </button>

                  {/* 冲刺 */}
                  <button className="action-btn"
                    style={{ width: 'auto', borderColor: 'var(--gold-dim)', opacity: actionUsed ? 0.35 : 1 }}
                    disabled={actionUsed} onClick={handleDash}>
                    <DashIcon size={14} color="var(--gold)" /> 冲刺
                  </button>

                  {/* 脱离接战 */}
                  <button className="action-btn"
                    style={{ width: 'auto', borderColor: 'var(--blue-light)', opacity: actionUsed ? 0.35 : 1 }}
                    disabled={actionUsed} onClick={handleDisengage}>
                    <DisengageIcon size={14} color="var(--blue-light)" /> 脱离
                  </button>

                  {/* 协助 */}
                  <button className="action-btn"
                    style={{ width: 'auto', borderColor: helpMode ? 'var(--blue-light)' : 'var(--wood-light)', opacity: actionUsed ? 0.35 : 1 }}
                    disabled={actionUsed}
                    onClick={() => { setHelpMode(h => !h); setMoveMode(false) }}>
                    <HelpIcon size={14} color={helpMode ? 'var(--blue-light)' : undefined} /> 协助{helpMode ? '（选队友）' : ''}
                  </button>

                  {/* 法术 */}
                  <button className="action-btn action-btn-spell"
                    style={{ width: 'auto', opacity: actionUsed ? 0.35 : 1 }}
                    disabled={actionUsed}
                    onClick={() => { setSpellModalOpen(true); setMoveMode(false); setHelpMode(false) }}>
                    <SpellIcon size={14} color="#8a5af6" /> 法术
                  </button>
                </div>

                {/* 职业特性按钮 */}
                <div className="flex gap-2 flex-wrap items-center mb-2">
                  {/* Fighter: Second Wind */}
                  {(playerClass === 'Fighter' || playerClass === '战士') && !classResources?.second_wind_used && (
                    <button className="action-btn"
                      style={{ width: 'auto', borderColor: 'var(--green-light)', opacity: bonusUsed ? 0.35 : 1 }}
                      disabled={bonusUsed}
                      onClick={() => handleClassFeature('second_wind')}>
                      <HeartIcon size={14} color="var(--green-light)" /> 活力恢复
                    </button>
                  )}

                  {/* Fighter: Action Surge */}
                  {(playerClass === 'Fighter' || playerClass === '战士') && playerLevel >= 2 && !classResources?.action_surge_used && (
                    <button className="action-btn"
                      style={{ width: 'auto', borderColor: 'var(--gold)' }}
                      onClick={() => handleClassFeature('action_surge')}>
                      <AttackIcon size={14} color="var(--gold)" /> 行动奔涌
                    </button>
                  )}

                  {/* Barbarian: Rage */}
                  {(playerClass === 'Barbarian' || playerClass === '野蛮人') && (
                    <button className="action-btn"
                      style={{
                        width: 'auto',
                        borderColor: classResources?.raging ? 'var(--red-light)' : 'var(--gold)',
                        background: classResources?.raging ? 'rgba(196,64,64,0.2)' : undefined,
                        opacity: (!classResources?.raging && bonusUsed) ? 0.35 : 1,
                      }}
                      disabled={!classResources?.raging && bonusUsed}
                      onClick={() => handleClassFeature('rage')}>
                      <SwordIcon size={14} color={classResources?.raging ? 'var(--red-light)' : 'var(--gold)'} />
                      {classResources?.raging ? '结束狂暴' : `狂暴 (${classResources?.rage_remaining ?? '?'})`}
                    </button>
                  )}

                  {/* Rogue: Cunning Action */}
                  {(playerClass === 'Rogue' || playerClass === '游荡者') && playerLevel >= 2 && !bonusUsed && (
                    <>
                      <button className="action-btn"
                        style={{ width: 'auto', borderColor: 'var(--green-light)' }}
                        onClick={() => handleClassFeature('cunning_action_dash')}>
                        <DashIcon size={14} color="var(--green-light)" /> 灵巧冲刺
                      </button>
                      <button className="action-btn"
                        style={{ width: 'auto', borderColor: 'var(--blue-light)' }}
                        onClick={() => handleClassFeature('cunning_action_disengage')}>
                        <DisengageIcon size={14} color="var(--blue-light)" /> 灵巧脱离
                      </button>
                      <button className="action-btn"
                        style={{ width: 'auto', borderColor: '#8a5af6' }}
                        onClick={() => handleClassFeature('cunning_action_hide')}>
                        <DefendIcon size={14} color="#8a5af6" /> 灵巧隐匿
                      </button>
                    </>
                  )}

                  {/* ── Battle Master: 战技 ── */}
                  {(playerClass === 'Fighter' || playerClass === '战士') && playerSubclassEffects?.battle_master && (classResources?.superiority_dice_remaining ?? 0) > 0 && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#f59e0b' }}
                      disabled={actionUsed} onClick={() => setManeuverModalOpen(true)}>
                      🎯 战技 ({classResources.superiority_dice_remaining})
                    </button>
                  )}

                  {/* ── Samurai: 战意 ── */}
                  {(playerClass === 'Fighter' || playerClass === '战士') && playerSubclassEffects?.samurai && (classResources?.fighting_spirit_remaining ?? 0) > 0 && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#ef4444' }}
                      disabled={bonusUsed} onClick={() => handleClassFeature('fighting_spirit')}>
                      ⚔️ 战意 ({classResources.fighting_spirit_remaining})
                    </button>
                  )}

                  {/* ── Bard: 灵感骰 ── */}
                  {(playerClass === 'Bard' || playerClass === '吟游诗人') && (classResources?.bardic_inspiration_remaining ?? 0) > 0 && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#a855f7' }}
                      disabled={bonusUsed} onClick={() => handleClassFeature('bardic_inspiration')}>
                      🎵 灵感骰 ({playerSubclassEffects?.inspiration_die || 'd6'} × {classResources.bardic_inspiration_remaining})
                    </button>
                  )}

                  {/* ── Monk: 疾风连击 ── */}
                  {(playerClass === 'Monk' || playerClass === '武僧') && playerLevel >= 2 && (classResources?.ki_remaining ?? 0) >= 1 && !bonusUsed && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#06b6d4' }}
                      onClick={() => handleClassFeature('ki_flurry')}>
                      👊 疾风连击 (气:{classResources.ki_remaining})
                    </button>
                  )}

                  {/* ── Monk: 震慑打击 ── */}
                  {(playerClass === 'Monk' || playerClass === '武僧') && playerLevel >= 5 && (classResources?.ki_remaining ?? 0) >= 1 && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#eab308' }}
                      onClick={() => handleClassFeature('ki_stunning_strike')}>
                      💥 震慑打击 (气:{classResources.ki_remaining})
                    </button>
                  )}

                  {/* ── Shadow Monk: 暗影步 ── */}
                  {(playerClass === 'Monk' || playerClass === '武僧') && playerSubclassEffects?.shadow_monk && (classResources?.ki_remaining ?? 0) >= 2 && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#6366f1' }}
                      onClick={() => handleClassFeature('shadow_step')}>
                      🌑 暗影步 (气:{classResources.ki_remaining})
                    </button>
                  )}

                  {/* ── Paladin: 引导神力 ── */}
                  {(playerClass === 'Paladin' || playerClass === '圣武士') && !classResources?.channel_divinity_used && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#fbbf24' }}
                      onClick={() => handleClassFeature('channel_divinity')}>
                      ✨ 引导神力
                    </button>
                  )}

                  {/* ── Paladin: 圣手 ── */}
                  {(playerClass === 'Paladin' || playerClass === '圣武士') && (classResources?.lay_on_hands_remaining ?? 0) > 0 && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#34d399' }}
                      onClick={() => handleClassFeature('lay_on_hands')}>
                      🤲 圣手 ({classResources.lay_on_hands_remaining}HP)
                    </button>
                  )}

                  {/* ── War Cleric: 战争牧师 ── */}
                  {(playerClass === 'Cleric' || playerClass === '牧师') && playerSubclassEffects?.war_domain && (classResources?.war_priest_remaining ?? 0) > 0 && !bonusUsed && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#dc2626' }}
                      onClick={() => handleClassFeature('war_priest_attack')}>
                      ⚔️ 战争牧师 ({classResources.war_priest_remaining})
                    </button>
                  )}

                  {/* ── Tempest Cleric: 毁灭之怒 ── */}
                  {(playerClass === 'Cleric' || playerClass === '牧师') && playerSubclassEffects?.tempest_domain && !classResources?.channel_divinity_used && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#3b82f6' }}
                      onClick={() => handleClassFeature('destructive_wrath')}>
                      ⚡ 毁灭之怒
                    </button>
                  )}

                  {/* ── Moon Druid: 野性形态 ── */}
                  {(playerClass === 'Druid' || playerClass === '德鲁伊') && playerSubclassEffects?.circle_of_moon && (classResources?.wild_shape_remaining ?? 0) > 0 && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#84cc16', background: classResources?.wild_shape_active ? 'rgba(132,204,22,0.15)' : undefined }}
                      onClick={() => handleClassFeature('wild_shape')}>
                      🐻 {classResources?.wild_shape_active ? `形态: ${classResources.wild_shape_active}` : `野性形态 (${classResources.wild_shape_remaining})`}
                    </button>
                  )}

                  {/* ── Spores Druid: 共生实体 ── */}
                  {(playerClass === 'Druid' || playerClass === '德鲁伊') && playerSubclassEffects?.circle_of_spores && (classResources?.wild_shape_remaining ?? 0) > 0 && !classResources?.symbiotic_entity_active && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#a3e635' }}
                      onClick={() => handleClassFeature('symbiotic_entity')}>
                      🍄 共生实体
                    </button>
                  )}

                  {/* ── Wild Magic Sorcerer: 混沌之潮 ── */}
                  {(playerClass === 'Sorcerer' || playerClass === '术士') && playerSubclassEffects?.wild_magic && !classResources?.tides_of_chaos_used && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#f472b6' }}
                      onClick={() => handleClassFeature('tides_of_chaos')}>
                      🌀 混沌之潮
                    </button>
                  )}

                  {/* ── Divination Wizard: 预言骰 ── */}
                  {(playerClass === 'Wizard' || playerClass === '法师') && playerSubclassEffects?.portent && (classResources?.portent_remaining ?? 0) > 0 && (
                    <button className="action-btn" style={{ width: 'auto', borderColor: '#818cf8' }}
                      onClick={() => handleClassFeature('portent')}>
                      🔮 预言骰 ({classResources.portent_remaining}) {classResources?.portent_value ? `[${classResources.portent_value}]` : ''}
                    </button>
                  )}

                  {/* Attack count display for Extra Attack */}
                  {ts && ts.attacks_max > 1 && (
                    <span className="text-xs px-2 py-1 rounded" style={{
                      background: 'rgba(196,159,64,0.15)',
                      color: 'var(--gold)',
                      border: '1px solid var(--gold-dim)',
                    }}>
                      攻击 {ts.attacks_made || 0}/{ts.attacks_max}
                    </span>
                  )}
                </div>

                {/* 结束回合按钮 */}
                <div className="flex items-center gap-2">
                  <button
                    className="action-btn action-btn-end"
                    style={{ width: 'auto', padding: '8px 20px' }}
                    onClick={handleEndTurn}
                  >
                    结束回合
                  </button>
                  {!selectedTarget && !moveMode && !helpMode && (
                    <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
                      点击地图上的 <SkullIcon size={11} color="var(--red-light)" style={{ display: 'inline', verticalAlign: 'middle' }} /> 选择攻击/法术目标，
                      <SwordIcon size={11} color="var(--green-light)" style={{ display: 'inline', verticalAlign: 'middle' }} /> 选择协助队友
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm animate-pulse" style={{ color: 'var(--gold)' }}>
                {isProcessing ? 'AI正在行动...' : '等待其他角色回合...'}
              </p>
            )}

            {/* 地图图例 */}
            <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--gold-dim)', marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--wood)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><ShieldIcon size={12} color="var(--blue-light)" /> 玩家</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><SwordIcon size={12} color="var(--green-light)" /> 队友</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><SkullIcon size={12} color="var(--red-light)" /> 敌人</span>
            </div>
          </div>
        </div>

        {/* 右侧：战斗日志 */}
        <div className="w-64 flex-shrink-0 border-l flex flex-col"
          style={{ borderColor: 'var(--wood-light)', background: 'var(--bg2)' }}>
          <p className="text-xs uppercase tracking-wider p-2 border-b flex-shrink-0"
            style={{ borderColor: 'var(--wood-light)', color: 'var(--text-dim)' }}>战斗日志</p>
          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {logs.map((log, i) => <CombatLogEntry key={log.id || i} log={log} />)}
            <div ref={logsEndRef} />
          </div>
        </div>

      </div>
    </div>
  )
}

// ── 法术选择 Modal ─────────────────────────────────────────
function SpellModal({ spells, cantrips, slots, onCast, onClose }) {
  const [selectedSpell, setSelectedSpell] = useState(null)
  const [level, setLevel] = useState(0)  // 0 = 戏法标签页

  const slotLabel = (lvl) => ['1st','2nd','3rd','4th','5th','6th','7th','8th','9th'][lvl-1] || `${lvl}th`
  const available = (lvl) => slots?.[slotLabel(lvl)] || 0

  const cantripList = spells.filter(s => s.level === 0 || cantrips?.includes(s.name))
  const spellList   = spells.filter(s => s.level > 0 && !cantrips?.includes(s.name))
  const shownSpells = level === 0 ? cantripList : spellList.filter(s => s.level <= level)
  const availableLevels = [1,2,3,4,5].filter(l => available(l) > 0)

  const canCast = selectedSpell
    ? (selectedSpell.level === 0 || cantrips?.includes(selectedSpell.name))
      ? true
      : available(level) > 0
    : false

  return (
    <div onClick={onClose} style={{
      position:'fixed', inset:0, zIndex:500,
      background:'rgba(0,0,0,0.65)',
      display:'flex', alignItems:'center', justifyContent:'center',
    }}>
      <div onClick={e => e.stopPropagation()} className="panel" style={{
        padding:20, minWidth:340, maxWidth:420,
        maxHeight:'80vh', display:'flex', flexDirection:'column',
      }}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-sm" style={{ color:'var(--gold)' }}>
            <SpellIcon size={14} color="#8a5af6" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
            选择法术
          </h3>
          <button onClick={onClose} style={{ color:'var(--text-dim)', fontSize:18, background:'none', border:'none', cursor:'pointer' }}>x</button>
        </div>

        <div className="flex gap-1.5 mb-3 flex-wrap">
          <button onClick={() => { setLevel(0); setSelectedSpell(null) }}
            className="px-2 py-1 rounded text-xs"
            style={{
              background: level===0 ? 'rgba(58,122,170,0.25)' : 'var(--bg)',
              border: `1px solid ${level===0 ? 'var(--blue-light)' : 'var(--wood-light)'}`,
              color: level===0 ? 'var(--blue-light)' : cantripList.length > 0 ? 'var(--parchment)' : 'var(--wood-light)',
              cursor: 'pointer', fontFamily: 'inherit',
            }}>
            戏法 ({cantripList.length})
          </button>
          {[1,2,3,4,5].map(lvl => {
            const cnt = available(lvl)
            const hasSpells = spellList.some(s => s.level <= lvl)
            return (
              <button key={lvl} onClick={() => { setLevel(lvl); setSelectedSpell(null) }}
                disabled={cnt <= 0 || !hasSpells}
                className="px-2 py-1 rounded text-xs"
                style={{
                  background: level===lvl ? 'rgba(138,90,246,0.25)' : 'var(--bg)',
                  border: `1px solid ${level===lvl ? '#8a5af6' : 'var(--wood-light)'}`,
                  color: (cnt > 0 && hasSpells) ? (level===lvl ? '#c084fc' : 'var(--parchment)') : 'var(--wood-light)',
                  cursor: (cnt > 0 && hasSpells) ? 'pointer' : 'not-allowed',
                  fontFamily: 'inherit',
                }}>
                {lvl}环 ({cnt})
              </button>
            )
          })}
        </div>

        <div className="space-y-1.5 overflow-y-auto flex-1" style={{ maxHeight:260 }}>
          {shownSpells.length === 0 ? (
            <p className="text-xs text-center py-4" style={{ color: 'var(--text-dim)' }}>
              {level === 0 ? '未习得戏法' : '当前法术位不足或无可用法术'}
            </p>
          ) : shownSpells.map(spell => {
            const isSel = selectedSpell?.name === spell.name
            const isCantrip = spell.level === 0 || cantrips?.includes(spell.name)
            return (
              <div key={spell.name} onClick={() => setSelectedSpell(isSel ? null : spell)}
                style={{
                  padding:'8px 10px', borderRadius:6, cursor:'pointer',
                  background: isSel ? (isCantrip ? 'rgba(58,122,170,0.18)' : 'rgba(138,90,246,0.18)') : 'var(--bg)',
                  border: `1px solid ${isSel ? (isCantrip ? 'var(--blue-light)' : '#8a5af6') : 'var(--wood)'}`,
                  transition:'all 0.1s',
                }}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold" style={{ color:'var(--parchment)' }}>
                    {isCantrip
                      ? <SpellIcon size={12} color="var(--blue-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
                      : spell.type==='heal'
                        ? <HeartIcon size={12} color="var(--green-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
                        : <SpellIcon size={12} color="var(--red-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />}
                    {spell.name}
                    {isCantrip && <span className="ml-1 text-xs" style={{ color:'var(--blue-light)', opacity:0.7 }}>戏法</span>}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                    {spell.type==='damage' ? spell.damage : spell.heal}
                  </span>
                </div>
                {spell.desc && <p className="text-xs mt-0.5 line-clamp-1" style={{ color: 'var(--text-dim)' }}>{spell.desc}</p>}
              </div>
            )
          })}
        </div>

        <div className="flex gap-2 mt-3">
          <button className="flex-1 btn-fantasy py-2 text-sm"
            style={{ borderColor: canCast ? '#8a5af6' : 'var(--wood)', opacity: canCast ? 1 : 0.4 }}
            disabled={!canCast}
            onClick={() => selectedSpell && onCast(selectedSpell, level || 1)}>
            <SpellIcon size={14} color="#8a5af6" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
            施放{selectedSpell ? `【${selectedSpell.name}】` : ''}
          </button>
          <button className="btn-fantasy px-4 py-2 text-sm" onClick={onClose}>取消</button>
        </div>
      </div>
    </div>
  )
}

// ── 战技选择 Modal ────────────────────────────────────────────
const MANEUVERS = [
  { id: 'precision', name: '精准攻击', desc: '将优越骰加到攻击检定上', icon: '🎯', needsTarget: false },
  { id: 'trip', name: '绊摔', desc: '目标力量豁免失败则倒地 + 优越骰伤害', icon: '🦶', needsTarget: true },
  { id: 'disarm', name: '缴械', desc: '目标力量豁免失败则掉落武器 + 优越骰伤害', icon: '🤚', needsTarget: true },
  { id: 'riposte', name: '反击', desc: '敌人攻击未中时用反应攻击 + 优越骰伤害', icon: '⚔️', needsTarget: false },
  { id: 'menacing', name: '威慑攻击', desc: '目标感知豁免失败则恐惧 + 优越骰伤害', icon: '😱', needsTarget: true },
  { id: 'pushing', name: '推力攻击', desc: '将目标推开15尺 + 优越骰伤害', icon: '💨', needsTarget: true },
  { id: 'goading', name: '引诱攻击', desc: '目标攻击你以外的生物有劣势 + 优越骰伤害', icon: '🤬', needsTarget: true },
]

function ManeuverModal({ diceType, remaining, onUse, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }} onClick={onClose}>
      <div className="panel p-5" style={{ background: 'var(--bg2)', borderColor: 'var(--gold)', maxWidth: 400, width: '90%' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <p style={{ color: 'var(--gold)', fontWeight: 700, fontSize: 15, margin: 0 }}>战技选择</p>
          <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>优越骰: {diceType} × {remaining}</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {MANEUVERS.map(m => (
            <button key={m.id} className="panel" style={{
              padding: '10px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10,
              border: '1px solid var(--wood-light)', background: 'var(--bg)', textAlign: 'left',
              transition: 'border-color 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--gold)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--wood-light)'}
            onClick={() => { onUse(m.id); onClose() }}>
              <span style={{ fontSize: 20 }}>{m.icon}</span>
              <div>
                <p style={{ color: 'var(--text-bright)', fontWeight: 600, fontSize: 13, margin: 0 }}>{m.name}</p>
                <p style={{ color: 'var(--text-dim)', fontSize: 11, margin: 0 }}>{m.desc}</p>
              </div>
            </button>
          ))}
        </div>
        <button className="btn-fantasy" style={{ width: '100%', marginTop: 12, fontSize: 12 }} onClick={onClose}>取消</button>
      </div>
    </div>
  )
}

// ── 战斗日志条目 ───────────────────────────────────────────
function CombatLogEntry({ log }) {
  const isPlayer = log.role === 'player'
  const isEnemy = log.role === 'enemy'
  const isCompanion = log.role?.startsWith('companion_')
  const color = isPlayer ? 'var(--blue-light)' : isEnemy ? 'var(--red-light)' : isCompanion ? 'var(--green-light)' : 'var(--text-dim)'
  const atk = log.dice_result?.attack
  const dmg = log.dice_result?.damage
  const dmgTotal = dmg ? (typeof dmg === 'object' ? dmg.total : dmg) : null

  return (
    <div style={{
      padding: '6px 8px', marginBottom: 4, borderRadius: 6,
      background: isPlayer ? 'rgba(58,122,170,0.08)' : isEnemy ? 'rgba(196,64,64,0.08)' : isCompanion ? 'rgba(74,138,74,0.08)' : 'transparent',
      borderLeft: `2px solid ${color}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
        <span style={{ flexShrink: 0, marginTop: 2, display: 'flex' }}>
          {isPlayer
            ? <ShieldIcon size={12} color="var(--blue-light)" />
            : isEnemy
              ? <SkullIcon size={12} color="var(--red-light)" />
              : isCompanion
                ? <SwordIcon size={12} color="var(--green-light)" />
                : <DiceD20Icon size={12} color="var(--text-dim)" />}
        </span>
        <p style={{ color, lineHeight: 1.6, fontSize: '0.8rem', fontStyle: 'normal' }}>{log.content}</p>
      </div>
      {atk?.d20 !== undefined && (
        <p style={{
          paddingLeft: 20, marginTop: 2,
          color: 'var(--parchment-dark)', opacity: 0.6, fontSize: '0.7rem',
          fontFamily: 'var(--font-mono, monospace)',
        }}>
          d20({atk.d20})+{atk.attack_bonus}={atk.attack_total} vs AC{atk.target_ac}
          {atk.hit
            ? ` → 命中${dmgTotal ? ` (${dmgTotal}伤害)` : ''}`
            : ' → 未命中'}
          {atk.is_crit ? ' 暴击！' : ''}{atk.is_fumble ? ' 大失手' : ''}
        </p>
      )}
    </div>
  )
}

// ── 工具函数：更新实体 HP ──────────────────────────────────
function applyHpUpdate(combat, targetId, newHp) {
  if (!targetId || newHp === null || newHp === undefined) return combat
  const entities = { ...combat.entities }
  if (entities[targetId]) {
    entities[targetId] = { ...entities[targetId], hp_current: Math.max(0, newHp) }
  }
  return { ...combat, entities }
}
