import { useCallback, useMemo, useState } from 'react'

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

  return {
    canPrepareSpells,
    sceneVibe: session?.game_state?.scene_vibe || {},
    clues: (session?.campaign_state?.clues || []).slice(-4),
    questLine: session?.campaign_state?.quest_log?.find(q => q.status === 'active'),
    allMembers,
    latestDmLine,
  }
}
