import { useCallback, useMemo, useState } from 'react'

function cleanText(value) {
  return String(value || '').trim()
}

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatSigned(value) {
  return `${value > 0 ? '+' : ''}${value}`
}

function getBondEntries(source) {
  if (Array.isArray(source)) {
    return source.map((item, index) => [item?.id || item?.name || String(index), item])
  }
  return Object.entries(asObject(source))
}

function findCompanionBond(companion, source) {
  const candidates = [
    companion?.id,
    companion?.character_id,
    companion?.characterId,
    companion?.name,
  ].map(cleanText).filter(Boolean)
  if (candidates.length === 0) return null

  const entries = getBondEntries(source)
  for (const [key, value] of entries) {
    if (candidates.includes(cleanText(key))) return value
  }

  const matched = entries.find(([key, value]) => {
    const bond = asObject(value)
    const values = [
      key,
      bond.id,
      bond.character_id,
      bond.characterId,
      bond.name,
    ].map(cleanText).filter(Boolean)
    return candidates.some(candidate => values.includes(candidate))
  })
  return matched?.[1] || null
}

function buildCompanionSignal(companion, rawBond) {
  const bond = asObject(rawBond)
  const personalQuest = asObject(bond.personal_quest || bond.personalQuest || bond.quest)
  const approval = toFiniteNumber(bond.approval ?? bond.approval_score ?? bond.affinity)
  const delta = toFiniteNumber(bond.last_approval_delta ?? bond.approval_delta ?? bond.approval_change)
  const relationship = cleanText(bond.relationship || bond.relationship_label || bond.status)
  const reason = cleanText(bond.last_approval_reason || bond.reason || bond.approval_reason)
  const questTitle = cleanText(personalQuest.title || personalQuest.quest || personalQuest.name)
  const questDetail = cleanText(personalQuest.next_step || personalQuest.nextStep || personalQuest.detail || personalQuest.description)
  const summary = delta !== null
    ? `好感 ${formatSigned(delta)}`
    : approval !== null
      ? `好感 ${formatSigned(approval)}`
      : relationship
        ? `关系 ${relationship}`
        : questTitle
          ? '个人任务'
          : ''
  const detail = questDetail || reason
  if (!summary && !detail) return null

  const toneSource = delta ?? approval ?? 0
  const name = cleanText(companion?.name) || '队友'
  return {
    id: cleanText(companion?.id || companion?.character_id || companion?.characterId || name),
    name,
    summary,
    detail,
    tone: toneSource > 0 ? 'good' : toneSource < 0 ? 'danger' : 'default',
    title: [
      relationship ? `关系：${relationship}` : '',
      approval !== null ? `好感：${formatSigned(approval)}` : '',
      delta !== null ? `最近好感：${formatSigned(delta)}` : '',
      reason ? `最近影响：${reason}` : '',
      questTitle ? `个人任务：${questTitle}` : '',
      questDetail ? `下一步：${questDetail}` : '',
    ].filter(Boolean).join('\n'),
  }
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

  const companionSignals = useMemo(() => {
    const campaign = session?.campaign_state || {}
    const source = campaign.companion_bonds || campaign.companion_relationships || campaign.companion_states
    return (companions || [])
      .map(companion => buildCompanionSignal(companion, findCompanionBond(companion, source)))
      .filter(Boolean)
      .slice(0, 3)
  }, [session, companions])

  return {
    canPrepareSpells,
    sceneVibe: session?.game_state?.scene_vibe || {},
    locationGraph: session?.game_state?.location_graph || null,
    clues: (session?.campaign_state?.clues || []).slice(-4),
    questLine,
    npcUpdates,
    keyDecisions,
    recentConsequences,
    companionSignals,
    allMembers,
    latestDmLine,
  }
}
