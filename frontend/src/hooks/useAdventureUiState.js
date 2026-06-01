import { useCallback, useMemo, useState } from 'react'

function cleanText(value) {
  return String(value || '').trim()
}

export function useAdventureUiState() {
  const [logs, setLogs] = useState([])
  const [input, setInput] = useState('')
  const [choices, setChoices] = useState([])
  const [error, setError] = useState('')
  const [restOpen, setRestOpen] = useState(false)
  const [prepareOpen, setPrepareOpen] = useState(false)
  const [journalOpen, setJournalOpen] = useState(false)
  const [journalText, setJournalText] = useState('')
  const [journalLoading, setJournalLoading] = useState(false)

  const addLog = useCallback((role, content, logType = 'narrative', extra = {}) => {
    setLogs(prev => [...prev, {
      id: `${role}-${Date.now()}-${Math.random()}`,
      role,
      content,
      log_type: logType,
      created_at: new Date().toISOString(),
      ...extra,
    }])
  }, [])

  return {
    logs, setLogs, addLog,
    input, setInput,
    choices, setChoices,
    error, setError,
    restOpen, setRestOpen,
    prepareOpen, setPrepareOpen,
    journalOpen, setJournalOpen,
    journalText, setJournalText,
    journalLoading, setJournalLoading,
  }
}

export function useAdventureDerivedState({ session, player, companions, logs }) {
  const canPrepareSpells = useMemo(() => {
    if (!player?.char_class) return false
    const cls = player.char_class.toLowerCase()
    return cls.includes('wizard') || cls.includes('cleric') || cls.includes('druid') ||
           cls.includes('法师') || cls.includes('牧师') || cls.includes('德鲁伊')
  }, [player])

  const allMembers = useMemo(() => {
    const list = player ? [{ ...player, isPlayer: true }] : []
    ;(companions || []).forEach(c => list.push({ ...c, isPlayer: false }))
    return list
  }, [player, companions])

  const latestDmLine = useMemo(() => {
    for (let i = logs.length - 1; i >= 0; i--) {
      const line = logs[i]
      if (line.role === 'dm' && line.log_type === 'narrative') return line
    }
    return null
  }, [logs])

  const npcUpdates = useMemo(() => {
    const registry = session?.campaign_state?.npc_registry || {}
    return Object.entries(registry)
      .map(([name, data]) => ({
        name,
        relationship: data?.relationship || '未知',
        keyFacts: Array.isArray(data?.key_facts) ? data.key_facts : [],
      }))
      .slice(-3)
  }, [session])

  const keyDecisions = useMemo(() => (
    Array.isArray(session?.campaign_state?.key_decisions)
      ? session.campaign_state.key_decisions.slice(-3)
      : []
  ), [session])

  const recentConsequences = useMemo(() => (
    Array.isArray(session?.campaign_state?.recent_updates)
      ? session.campaign_state.recent_updates.slice(-4).reverse()
      : []
  ), [session])

  const questLine = useMemo(() => {
    const campaign = session?.campaign_state || {}
    const quests = Array.isArray(campaign.quest_log)
      ? campaign.quest_log.filter(q => q?.quest)
      : []
    const selectedQuest = quests.find(q => String(q.status || '').toLowerCase() === 'active') || quests[quests.length - 1]
    if (!selectedQuest) return selectedQuest

    const progressCount = Array.isArray(campaign.recent_updates)
      ? campaign.recent_updates.filter(item => (
        item?.type === 'quest' && cleanText(item.label) === cleanText(selectedQuest.quest)
      )).length
      : 0

    return { ...selectedQuest, progressCount }
  }, [session])

  return {
    canPrepareSpells,
    sceneVibe: session?.game_state?.scene_vibe || {},
    locationGraph: session?.game_state?.location_graph || null,
    clues: (session?.campaign_state?.clues || []).slice(-4),
    questLine,
    npcUpdates,
    keyDecisions,
    recentConsequences,
    allMembers,
    latestDmLine,
  }
}
