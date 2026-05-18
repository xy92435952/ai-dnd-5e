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
import { charactersApi } from '../api/characters'
import { gameApi } from '../api/game'

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
  setPendingCheck,
  setStreamingNarrative = () => {},
  setPlayer,
  setPrepareOpen,
  setRestOpen,
  setSession,
  setCompanions,
  buildDialogueQueue,
  enterDialogueStage,
  rollPending,
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
    setInput('')
    setError('')
    setPendingCheck(null)
    setStreamingNarrative('')
    setChoices([])
    setIsLoading(true)
    addLog('player', text, 'narrative')
    try {
      const payload = {
        session_id: sessionId,
        action_text: text,
        action_source: options.actionSource || 'human_input',
      }
      const resp = options.stream === false
        ? await gameApi.action(payload)
        : await gameApi.actionStream(payload, {
          onNarrativeDelta: (delta) => {
            setStreamingNarrative(prev => `${prev || ''}${delta}`)
          },
        })
      setStreamingNarrative('')

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
      setStreamingNarrative('')
      setError(e.message)
      addLog('system', `⚠ AI响应失败: ${e.message}`, 'system')
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }, [
    addLog,
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
    setStreamingNarrative,
  ])

  const handleDiceRoll = useCallback(async () => {
    const autoMsg = await rollPending()
    if (autoMsg) {
      setTimeout(() => handleAction(autoMsg), 800)
    }
    inputRef.current?.focus()
  }, [handleAction, inputRef, rollPending])

  const handleRest = useCallback(async (restType) => {
    setRestOpen(false)
    setIsLoading(true)
    try {
      const result = await gameApi.rest(sessionId, restType)
      const summary = result.characters?.map(c => `${c.name} HP+${c.hp_recovered} → ${c.hp_current}`).join(' | ')
      addLog('system', `🌙 完成${restType === 'long' ? '长休' : '短休'}。${summary}`, 'system')
      await refreshCharacters()
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [addLog, refreshCharacters, sessionId, setError, setIsLoading, setRestOpen])

  const handleGenerateJournal = useCallback(async () => {
    setJournalLoading(true)
    setJournalText('')
    try {
      setJournalText((await gameApi.generateJournal(sessionId)).journal || '（生成失败）')
    } catch (e) {
      setJournalText(`失败：${e.message}`)
    } finally {
      setJournalLoading(false)
    }
  }, [sessionId, setJournalLoading, setJournalText])

  const handlePrepareSpells = useCallback(async (prepared) => {
    try {
      await charactersApi.prepareSpells(playerId, prepared)
      setPlayer(prev => ({ ...prev, prepared_spells: prepared }))
      addLog('system', `📖 已备法术更新（${prepared.length} 个）`, 'system')
      setPrepareOpen(false)
    } catch (e) {
      addLog('system', `备法失败：${e.message}`, 'system')
    }
  }, [addLog, playerId, setPlayer, setPrepareOpen])

  const handleCheckpoint = useCallback(async () => {
    try {
      await gameApi.saveCheckpoint(sessionId)
      addLog('system', '💾 战役进度已保存', 'system')
    } catch (e) {
      addLog('system', `保存失败：${e.message}`, 'system')
    }
  }, [addLog, sessionId])

  return {
    refreshCharacters,
    handleAction,
    handleDiceRoll,
    handleRest,
    handleGenerateJournal,
    handlePrepareSpells,
    handleCheckpoint,
  }
}
