/**
 * useAdventureActions — Adventure 页面里与"玩家操作"有关的一组 async handler。
 *
 * 原位：Adventure.jsx 中的
 *   - refreshCharacters
 *   - handleAction
 *   - handleDiceRoll
 *   - handleRest
 *   - handleGenerateJournal
 *   - handlePrepareSpells
 *   - handleCheckpoint
 *
 * 抽出后，Adventure 只负责把 state/setter 传进来并把返回的 handler 塞回现有子组件。
 */
import { useCallback } from 'react'
import { gameApi, charactersApi } from '../api/client'

function createActionIdempotencyKey(sessionId) {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
  return `${sessionId}:${random}`
}

function formatSlotSummary(slots) {
  if (!slots || Object.keys(slots).length === 0) return ''
  return `法术位 ${Object.entries(slots).map(([level, count]) => `${level}+${count}`).join('/')}`
}

function formatRestCharacterSummary(character, restType) {
  const parts = [
    `${character.name} HP+${character.hp_recovered} → ${character.hp_current}${character.hp_max ? `/${character.hp_max}` : ''}`,
  ]
  if (restType === 'short') {
    if (character.ordinary_healing_blocked) {
      parts.push('普通治疗无法复活')
    } else if (character.hit_dice_spent) {
      const con = character.con_mod || 0
      const conText = con >= 0 ? `+${con}` : `${con}`
      parts.push(`生命骰 ${character.hit_die_roll}${conText}`)
    } else if (character.no_healing_needed) {
      parts.push('满血未消耗生命骰')
    } else if (character.no_hit_dice) {
      parts.push('无可用生命骰')
    }
  }
  if (restType === 'long' && character.hit_dice_restored) {
    parts.push(`生命骰+${character.hit_dice_restored}`)
  }
  if (restType === 'long' && character.ordinary_healing_blocked) {
    parts.push('普通休息无法复活')
  }
  if (character.hit_dice_remaining != null && character.hit_dice_total != null) {
    parts.push(`剩余 ${character.hit_dice_remaining}/${character.hit_dice_total}`)
  }
  const slotSummary = formatSlotSummary(character.slots_restored)
  if (slotSummary) parts.push(slotSummary)
  if (character.exhaustion_level_before != null && character.exhaustion_level_after != null
    && character.exhaustion_level_before !== character.exhaustion_level_after) {
    parts.push(`力竭 ${character.exhaustion_level_before}→${character.exhaustion_level_after}`)
  }
  if (character.conditions_removed?.length) {
    parts.push(`移除 ${character.conditions_removed.join('/')}`)
  }
  if (character.death_saves_reset) {
    parts.push('重置濒死豁免')
  }
  return parts.join('，')
}

export function formatRestSummary(result, restType) {
  const summaries = result.characters?.map(c => formatRestCharacterSummary(c, restType)).filter(Boolean) || []
  return summaries.length ? summaries.join(' | ') : '没有角色状态变化'
}

export function useAdventureActions({
  sessionId,
  playerId,
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
  setPendingExplorationReaction,
  setPendingCheck,
  setPlayer,
  setPrepareOpen,
  setRestOpen,
  setSession,
  setCompanions,
  buildDialogueQueue,
  enterDialogueStage,
  rollPending,
  actionBlockedReason = '',
}) {
  const refreshCharacters = useCallback(async () => {
    try {
      const data = await gameApi.getSession(sessionId)
      setSession(data)
      setPlayer(data.player)
      setCompanions(data.companions || [])
    } catch {
      // Keep the current character snapshot if refresh fails.
    }
  }, [sessionId, setSession, setPlayer, setCompanions])

  const handleAction = useCallback(async (overrideText, options = {}) => {
    const text = (overrideText ?? input).trim()
    if (!text || isLoading) return
    if (actionBlockedReason) {
      setError(actionBlockedReason)
      inputRef.current?.focus()
      return
    }
    setInput('')
    setError('')
    setIsLoading(true)
    addLog('player', text, 'narrative')
    try {
      const resp = await gameApi.action({
        session_id: sessionId,
        action_text: text,
        action_source: options.actionSource || 'human_input',
        idempotency_key: options.idempotencyKey || createActionIdempotencyKey(sessionId),
      })

      if (resp.retryable) {
        const message = resp.narrative || 'AI DM 暂时没有完成回应，当前行动尚未写入剧情。请稍后重试。'
        setInput(text)
        setError(message)
        addLog('system', message, 'system')
        return
      }

      setPendingCheck(null)
      setChoices([])
      const queue = buildDialogueQueue(resp.narrative, resp.companion_reactions, companions)
      if (resp.visibility && Array.isArray(queue)) {
        queue.forEach(seg => {
          if (seg?.role === 'dm') seg.visibility = resp.visibility
        })
      }
      if (resp.table_reason && Array.isArray(queue)) {
        queue.forEach(seg => {
          if (seg?.role === 'dm') seg.table_reason = resp.table_reason
        })
      }
      if (resp.table_decision && Array.isArray(queue)) {
        queue.forEach(seg => {
          if (seg?.role === 'dm') seg.table_decision = resp.table_decision
        })
      }

      if (resp.dice_display?.length) {
        for (const d of resp.dice_display) {
          addLog(
            'dice',
            `${d.label || '骰子'}：${d.raw}${d.modifier ? ` + ${d.modifier}` : ''} = ${d.total}${d.against ? ` vs ${d.against}` : ''} ${d.outcome ? `→ ${d.outcome}` : ''}`,
            'dice',
            { dice_result: d },
          )
        }
      }

      if (resp.exploration_reaction_prompt) {
        setPendingExplorationReaction?.(resp.exploration_reaction_prompt)
      } else {
        setPendingExplorationReaction?.(null)
      }
      if (resp.needs_check?.required) setPendingCheck(resp.needs_check)
      if (resp.player_choices?.length) setChoices(resp.player_choices)

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
  }, [
    addLog,
    actionBlockedReason,
    buildDialogueQueue,
    companions,
    enterDialogueStage,
    isLoading,
    input,
    inputRef,
    navigate,
    refreshCharacters,
    sessionId,
    setChoices,
    setError,
    setInput,
    setIsLoading,
    setPendingCheck,
    setPendingExplorationReaction,
  ])

  const handleExplorationReaction = useCallback(async (reactionType, prompt) => {
    if (!prompt || isLoading) return
    if (actionBlockedReason) {
      setError(actionBlockedReason)
      inputRef.current?.focus()
      return
    }
    setError('')
    setIsLoading(true)
    try {
      const result = await gameApi.useExplorationReaction(
        sessionId,
        reactionType,
        prompt.reactor_character_id,
      )
      setPendingExplorationReaction?.(null)

      if (result.dice_display?.length) {
        for (const d of result.dice_display) {
          addLog(
            'dice',
            `${d.label || 'Dice'}: ${d.raw ?? ''}${d.modifier ? ` + ${d.modifier}` : ''}${d.total != null ? ` = ${d.total}` : ''}`,
            'dice',
            { dice_result: d },
          )
        }
      }

      const queue = buildDialogueQueue(result.narrative, result.companion_reactions, companions)
      if (queue.length > 0) enterDialogueStage(queue)
      await refreshCharacters()
    } catch (e) {
      setError(e.message)
      addLog('system', `Reaction failed: ${e.message}`, 'system')
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }, [
    actionBlockedReason,
    addLog,
    buildDialogueQueue,
    companions,
    enterDialogueStage,
    inputRef,
    isLoading,
    refreshCharacters,
    sessionId,
    setError,
    setIsLoading,
    setPendingExplorationReaction,
  ])

  const handleDiceRoll = useCallback(async () => {
    if (actionBlockedReason) {
      setError(actionBlockedReason)
      inputRef.current?.focus()
      return
    }
    const autoMsg = await rollPending()
    if (autoMsg) {
      setTimeout(() => handleAction(autoMsg, { actionSource: 'system_action' }), 800)
    }
    inputRef.current?.focus()
  }, [actionBlockedReason, handleAction, inputRef, rollPending, setError])

  const handleRest = useCallback(async (restType) => {
    if (actionBlockedReason) {
      setError(actionBlockedReason)
      return
    }
    setRestOpen(false)
    setIsLoading(true)
    try {
      const result = await gameApi.rest(sessionId, restType)
      const summary = formatRestSummary(result, restType)
      addLog('system', `🌙 完成${restType === 'long' ? '长休' : '短休'}。${summary}`, 'system')
      await refreshCharacters()
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [actionBlockedReason, addLog, refreshCharacters, sessionId, setError, setIsLoading, setRestOpen])

  const handleGenerateJournal = useCallback(async () => {
    if (actionBlockedReason) {
      setError(actionBlockedReason)
      setJournalText(prev => prev || '房间正在重新同步，恢复后可重新生成日志。')
      return
    }
    setJournalLoading(true)
    setJournalText('')
    try {
      setJournalText((await gameApi.generateJournal(sessionId)).journal || '（生成失败）')
    } catch (e) {
      setJournalText(`失败：${e.message}`)
    } finally {
      setJournalLoading(false)
    }
  }, [actionBlockedReason, sessionId, setError, setJournalLoading, setJournalText])

  const handlePrepareSpells = useCallback(async (prepared) => {
    if (actionBlockedReason) {
      setError(actionBlockedReason)
      return
    }
    try {
      await charactersApi.prepareSpells(playerId, prepared)
      setPlayer(prev => ({ ...prev, prepared_spells: prepared }))
      addLog('system', `📖 已备法术更新（${prepared.length} 个）`, 'system')
      setPrepareOpen(false)
    } catch (e) {
      addLog('system', `备法失败：${e.message}`, 'system')
    }
  }, [actionBlockedReason, addLog, playerId, setError, setPlayer, setPrepareOpen])

  const handleCheckpoint = useCallback(async () => {
    if (actionBlockedReason) {
      setError(actionBlockedReason)
      throw new Error(actionBlockedReason)
    }
    try {
      const result = await gameApi.saveCheckpoint(sessionId)
      if (result?.ok === false) {
        addLog('system', `存档未更新：${result.message || '没有可以存档的内容'}`, 'system')
        return result
      }
      addLog('system', '💾 战役进度已保存', 'system')
      return result
    } catch (e) {
      addLog('system', `保存失败：${e.message}`, 'system')
      throw e
    }
  }, [actionBlockedReason, addLog, sessionId, setError])

  return {
    refreshCharacters,
    handleAction,
    handleDiceRoll,
    handleRest,
    handleGenerateJournal,
    handlePrepareSpells,
    handleCheckpoint,
    handleExplorationReaction,
  }
}
