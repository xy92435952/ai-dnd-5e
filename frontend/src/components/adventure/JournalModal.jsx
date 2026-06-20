/**
 * JournalModal — 生成 / 展示冒险日志的弹窗。
 *
 * Props:
 *   session    - 当前冒险 session，用于结构化卷宗
 *   room       - 多人房间快照，用于分队地点
 *   text       - 当前日志文本（可为空）
 *   loading    - 生成中标志
 *   initialSection - 打开后优先定位的卷宗区域
 *   onGenerate - () => void 重新生成
 *   onClose    - () => void
 */
import { useEffect, useRef } from 'react'
import Overlay from './Overlay'
import { JournalIcon } from '../Icons'
import { extractNarrative, splitCompanionReactions } from '../../utils/dialogue'
import { filterPublicClues, filterPublicRecentUpdates } from '../../utils/clueVisibility'

function cleanText(value) {
  return String(value || '').trim()
}

function firstSceneLine(value) {
  const text = cleanText(value)
  if (!text) return ''
  return text.split(/[\n。]/)[0].slice(0, 48)
}

function flagLabel(key) {
  return String(key || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function joinParts(parts) {
  return parts.map(cleanText).filter(Boolean).join(' · ')
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

const QUEST_STATUS_META = {
  active: { label: '进行中', tone: 'active' },
  completed: { label: '完成', tone: 'good' },
  failed: { label: '失败', tone: 'danger' },
  blocked: { label: '受阻', tone: 'danger' },
  paused: { label: '暂停', tone: 'default' },
}

const RECENT_TYPE_META = {
  quest: { label: '任务', tone: 'active' },
  clue: { label: '线索', tone: 'active' },
  companion: { label: '队友', tone: 'good' },
  decision: { label: '决定', tone: 'default' },
  location: { label: '地点', tone: 'active' },
  npc: { label: 'NPC', tone: 'good' },
  world: { label: '后果', tone: 'danger' },
  threat: { label: '威胁', tone: 'danger' },
}

function getQuestStatusMeta(status) {
  const key = cleanText(status || 'active').toLowerCase()
  return QUEST_STATUS_META[key] || { label: status || '记录', tone: 'default' }
}

function getApprovalMeta(value) {
  const score = toFiniteNumber(value)
  if (score === null) return null
  const clamped = Math.max(-100, Math.min(100, Math.round(score)))
  const label = clamped >= 50
    ? '信赖'
    : clamped >= 10
      ? '认可'
      : clamped <= -50
        ? '疏离'
        : clamped < 0
          ? '动摇'
          : '中立'
  const next = clamped >= 50
    ? { label: '最高信赖', remaining: 0, text: '已达最高信赖' }
    : clamped >= 10
      ? { label: '信赖', remaining: 50 - clamped }
      : clamped >= 0
        ? { label: '认可', remaining: 10 - clamped }
        : clamped >= -49
          ? { label: '中立', remaining: 0 - clamped }
          : { label: '动摇', remaining: -49 - clamped }
  return {
    score: clamped,
    label,
    tone: clamped > 0 ? 'good' : clamped < 0 ? 'danger' : 'default',
    text: `${clamped > 0 ? '+' : ''}${clamped}`,
    fill: `${(clamped + 100) / 2}%`,
    nextText: next.text || `距${next.label} ${next.remaining}`,
  }
}

function getRecentTypeMeta(type) {
  const key = cleanText(type || 'note').toLowerCase()
  return RECENT_TYPE_META[key] || { label: '记录', tone: 'default' }
}

function getQuestDetail(quest) {
  return [
    quest?.outcome,
    quest?.next_step,
    quest?.consequence,
    quest?.failure_consequence,
    quest?.fail_forward,
    quest?.detail,
  ].map(cleanText).find(Boolean) || ''
}

function buildQuestHooks(quest, primaryDetail) {
  return [
    ['路线', quest?.branch, 'active'],
    ['下一步', quest?.next_step, 'active'],
    ['后果', quest?.consequence, 'default'],
    ['失败代价', quest?.failure_consequence, 'danger'],
    ['失败推进', quest?.fail_forward, 'danger'],
  ]
    .map(([label, value, tone]) => ({ label, text: cleanText(value), tone }))
    .filter(item => item.text && item.text !== primaryDetail)
}

function buildQuestSummary(quest, recentUpdates) {
  const status = getQuestStatusMeta(quest?.status)
  const detail = getQuestDetail(quest)
  const timeline = recentUpdates
    .filter(item => item?.type === 'quest' && cleanText(item.label) === cleanText(quest?.quest))
    .slice(-3)
    .map((item, index) => {
      const itemStatus = getQuestStatusMeta(item.status || quest?.status)
      return {
        id: `${item.label}-${item.at || index}`,
        status: itemStatus.label,
        tone: itemStatus.tone,
        detail: cleanText(item.detail || item.status || quest?.outcome),
        at: cleanText(item.at || item.created_at || item.turn),
      }
    })

  return {
    quest: quest?.quest,
    statusLabel: status.label,
    statusTone: status.tone,
    detail,
    hooks: buildQuestHooks(quest, detail),
    timeline,
    progressCount: timeline.length,
  }
}

function buildQuestStatusSummary(quests) {
  const summary = new Map()
  quests.forEach(quest => {
    const key = `${quest.statusLabel}-${quest.statusTone}`
    const current = summary.get(key) || {
      label: quest.statusLabel,
      tone: quest.statusTone,
      count: 0,
    }
    current.count += 1
    summary.set(key, current)
  })
  return Array.from(summary.values())
}

function buildTimelineEntry(item, index) {
  const type = cleanText(item?.type || 'note').toLowerCase()
  const typeMeta = getRecentTypeMeta(type)
  const questStatus = type === 'quest' ? getQuestStatusMeta(item?.status) : null
  return {
    id: `${type}-${item?.label || 'entry'}-${item?.at || index}`,
    type,
    typeLabel: typeMeta.label,
    tone: questStatus?.tone || typeMeta.tone,
    label: cleanText(item?.label),
    detail: cleanText(item?.detail || item?.status),
    at: cleanText(item?.at || item?.created_at || item?.turn),
  }
}

function buildTimelineSummary(timeline) {
  const counts = new Map()
  timeline.forEach(item => {
    const key = item.typeLabel || '记录'
    const current = counts.get(key) || { label: key, tone: item.tone, count: 0 }
    current.count += 1
    counts.set(key, current)
  })
  return [...counts.values()]
}

function matchCompanionByName(speaker, companions) {
  const cleanSpeaker = cleanText(speaker)
  if (!cleanSpeaker) return null
  return companions.find(companion => {
    const name = cleanText(companion?.name)
    return name && (name === cleanSpeaker || name.includes(cleanSpeaker) || cleanSpeaker.includes(name))
  }) || null
}

function matchCompanionByIdentity(key, data, companions) {
  const candidates = [
    key,
    data?.id,
    data?.character_id,
    data?.characterId,
  ].map(cleanText).filter(Boolean)
  const byId = companions.find(companion => {
    const ids = [companion?.id, companion?.character_id, companion?.characterId].map(cleanText)
    return ids.some(id => id && candidates.includes(id))
  })
  if (byId) return byId
  return matchCompanionByName(data?.name || key, companions)
}

function buildCompanionReactionMap(session, companions) {
  const map = new Map()
  asArray(session?.logs).forEach(log => {
    const role = cleanText(log?.role)
    const isCompanionLog = role === 'companion' || role.startsWith('companion_') || log?.log_type === 'companion'
    if (!isCompanionLog) return

    if (role.startsWith('companion_')) {
      const companion = matchCompanionByName(role.slice('companion_'.length), companions)
      const text = cleanText(extractNarrative(log?.content))
      if (companion && text) {
        map.set(companion.id || companion.name, { text, at: log?.created_at })
      }
      return
    }

    splitCompanionReactions(log?.content, companions).forEach(reaction => {
      const companion = matchCompanionByName(reaction.speaker, companions)
      const text = cleanText(reaction.text)
      if (companion && text) {
        map.set(companion.id || companion.name, { text, at: log?.created_at })
      }
    })
  })
  return map
}

function normalizeCompanionBond(rawBond) {
  const bond = asObject(rawBond)
  const personalQuest = asObject(bond.personal_quest || bond.personalQuest || bond.quest)
  const approval = getApprovalMeta(bond.approval ?? bond.approval_score ?? bond.affinity)
  const delta = toFiniteNumber(bond.last_approval_delta ?? bond.approval_delta ?? bond.approval_change)
  const roundedDelta = delta === null ? null : Math.round(delta)
  return {
    relationship: cleanText(bond.relationship || bond.status),
    approval,
    delta: roundedDelta,
    deltaText: roundedDelta === null ? '' : `${roundedDelta > 0 ? '+' : ''}${roundedDelta}`,
    deltaTone: roundedDelta > 0 ? 'good' : roundedDelta < 0 ? 'danger' : 'default',
    reason: cleanText(bond.last_approval_reason || bond.reason || bond.approval_reason),
    personalQuest: {
      title: cleanText(personalQuest.title || personalQuest.quest || personalQuest.name),
      status: getQuestStatusMeta(personalQuest.status || 'active'),
      detail: cleanText(personalQuest.detail || personalQuest.outcome || personalQuest.summary),
      nextStep: cleanText(personalQuest.next_step || personalQuest.nextStep),
    },
  }
}

function buildCompanionBondMap(campaign, companions) {
  const map = new Map()
  const source = campaign?.companion_bonds || campaign?.companion_relationships || campaign?.companion_states
  const entries = Array.isArray(source)
    ? source.map((item, index) => [item?.id || item?.character_id || item?.name || index, item])
    : Object.entries(asObject(source))
  entries.forEach(([key, rawBond]) => {
    const companion = matchCompanionByIdentity(key, rawBond, companions)
    if (!companion) return
    const normalized = normalizeCompanionBond(rawBond)
    const hasQuest = normalized.personalQuest.title || normalized.personalQuest.detail || normalized.personalQuest.nextStep
    if (!normalized.relationship && !normalized.approval && !normalized.reason && !hasQuest) return
    map.set(companion.id || companion.name, normalized)
  })
  return map
}

function buildCompanionSummary(companion, reactionsByCompanion, bondsByCompanion) {
  const className = companion?.char_class || companion?.class || companion?.class_name
  const level = companion?.level ? `Lv ${companion.level}` : ''
  const role = joinParts([companion?.race, className, level]) || '队友'
  const derived = asObject(companion?.derived)
  const key = companion?.id || companion?.name || role
  const stats = joinParts([
    companion?.hp_max || derived.hp_max
      ? `HP ${companion?.hp_current ?? companion?.hp_max ?? derived.hp_max}/${companion?.hp_max ?? derived.hp_max}`
      : '',
    companion?.ac || derived.ac ? `AC ${companion?.ac ?? derived.ac}` : '',
    derived.speed ? `速度 ${derived.speed}` : '',
  ])

  return {
    id: key,
    name: companion?.name || '未命名队友',
    role,
    stats,
    recentReaction: reactionsByCompanion.get(key) || null,
    bond: bondsByCompanion.get(key) || null,
    personality: cleanText(companion?.personality || companion?.personality_traits),
    speechStyle: cleanText(companion?.speech_style),
    combatPreference: cleanText(companion?.combat_preference),
    catchphrase: cleanText(companion?.catchphrase),
    backstory: cleanText(companion?.backstory),
  }
}

function buildJournalSections(session, room) {
  const campaign = asObject(session?.campaign_state)
  const gameState = asObject(session?.game_state)
  const sceneVibe = asObject(gameState.scene_vibe)
  const rawClues = asArray(campaign.clues)
  const clues = filterPublicClues(rawClues)
  const recentUpdates = filterPublicRecentUpdates(
    asArray(campaign.recent_updates).filter(Boolean),
    rawClues,
  )
  const timeline = recentUpdates
    .slice(-12)
    .reverse()
    .map(buildTimelineEntry)
    .filter(item => item.label)
  const timelineSummary = buildTimelineSummary(timeline)
  const quests = asArray(campaign.quest_log)
    .filter(q => q?.quest)
    .map(q => buildQuestSummary(q, recentUpdates))
  const companions = asArray(session?.companions)
    .filter(companion => companion && cleanText(companion.name))
  const reactionsByCompanion = buildCompanionReactionMap(session, companions)
  const bondsByCompanion = buildCompanionBondMap(campaign, companions)
  const companionSummaries = companions.map(companion => buildCompanionSummary(companion, reactionsByCompanion, bondsByCompanion))
  const decisions = asArray(campaign.key_decisions).filter(Boolean)
  const completedScenes = asArray(campaign.completed_scenes).filter(Boolean)

  const npcs = Object.entries(asObject(campaign.npc_registry))
    .filter(([name]) => cleanText(name))
    .map(([name, data]) => ({
      name,
      relationship: data?.relationship || '关系未知',
      facts: Array.isArray(data?.key_facts) ? data.key_facts.filter(Boolean) : [],
      promises: Array.isArray(data?.promises) ? data.promises.filter(Boolean) : [],
    }))

  const locations = []
  const addLocation = (name, detail = '') => {
    const clean = cleanText(name)
    if (!clean || locations.some(item => item.name === clean)) return
    locations.push({ name: clean, detail })
  }
  addLocation(sceneVibe.location, '当前地点')
  addLocation(firstSceneLine(session?.current_scene), '当前场景')
  completedScenes.forEach(scene => addLocation(scene, '已完成场景'))
  clues.filter(c => c.category === 'location').forEach(c => addLocation(c.text, '地点线索'))
  asArray(room?.party_groups).forEach(group => addLocation(group.location, group.name || '分队位置'))

  const threats = []
  if (session?.combat_active) threats.push({ label: '战斗仍在进行', detail: '当前遭遇未结束' })
  if (['危险', '致命', '紧张'].includes(sceneVibe.tension)) {
    threats.push({ label: sceneVibe.tension, detail: sceneVibe.location ? `${sceneVibe.location} 局势` : '当前局势' })
  }
  Object.entries(asObject(campaign.world_flags))
    .filter(([, value]) => value === true)
    .forEach(([key]) => threats.push({ label: flagLabel(key), detail: '未解决世界状态' }))
  asArray(campaign.unresolved_threats || campaign.threats)
    .filter(Boolean)
    .forEach(item => {
      if (typeof item === 'string') threats.push({ label: item, detail: '威胁' })
      else if (item?.label || item?.name || item?.text) {
        threats.push({ label: item.label || item.name || item.text, detail: item.detail || item.status || '威胁' })
      }
    })
  recentUpdates
    .filter(item => item.type === 'world' || item.type === 'threat')
    .forEach(item => threats.push({ label: item.label, detail: item.detail || '近期后果' }))

  return {
    quests,
    questSummary: buildQuestStatusSummary(quests),
    companions: companionSummaries,
    clues,
    npcs,
    locations,
    threats,
    decisions,
    timeline,
    timelineSummary,
  }
}

function EmptyLine({ children }) {
  return <p className="journal-empty-line">{children}</p>
}

function Section({ title, count, children, sectionRef, sectionKey }) {
  return (
    <section
      ref={sectionRef}
      className="journal-section"
      data-journal-section={sectionKey}
      tabIndex={sectionRef ? -1 : undefined}
    >
      <h4>
        <span>{title}</span>
        <b>{count}</b>
      </h4>
      {children}
    </section>
  )
}

function Pill({ children, tone = 'default' }) {
  return <span className={`journal-pill ${tone}`}>{children}</span>
}

export default function JournalModal({ session, room, text, loading, initialSection = '', onGenerate, onClose }) {
  const journal = buildJournalSections(session, room)
  const companionsSectionRef = useRef(null)
  const dossierSummary = [
    { label: '任务', count: journal.quests.length, tone: journal.quests.length ? 'active' : 'default' },
    { label: '时间线', count: journal.timeline.length, tone: journal.timeline.length ? 'active' : 'default' },
    { label: '队友', count: journal.companions.length, tone: journal.companions.length ? 'good' : 'default' },
    { label: '线索', count: journal.clues.length, tone: journal.clues.length ? 'active' : 'default' },
    { label: '威胁', count: journal.threats.length, tone: journal.threats.length ? 'danger' : 'default' },
  ]

  useEffect(() => {
    if (initialSection !== 'companions') return
    const target = companionsSectionRef.current
    if (!target) return
    if (typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ block: 'start' })
    }
    if (typeof target.focus === 'function') {
      target.focus({ preventScroll: true })
    }
  }, [initialSection])

  return (
    <Overlay onClose={onClose}>
      <div className="journal-modal-head">
        <h3>
          <JournalIcon size={18} color="var(--amber)" /> 冒险卷宗
        </h3>
        <button type="button" onClick={onClose} aria-label="关闭卷宗">×</button>
      </div>

      <div className="journal-dossier-summary" role="status" aria-label="卷宗概览">
        {dossierSummary.map(item => (
          <span key={item.label} className={item.tone} aria-label={`${item.label} ${item.count}`}>
            <b>{item.count}</b>{item.label}
          </span>
        ))}
      </div>

      <div className="journal-dossier" aria-label="冒险卷宗">
        <Section title="任务" count={journal.quests.length}>
          {journal.quests.length === 0 ? <EmptyLine>暂无任务记录</EmptyLine> : (
            <>
              <div className="journal-quest-summary" aria-label="任务状态汇总">
                {journal.questSummary.map(item => (
                  <span key={item.label} className={item.tone}>
                    <b>{item.count}</b>{item.label}
                  </span>
                ))}
              </div>
              {journal.quests.map((quest, index) => (
                <article key={`${quest.quest}-${index}`} className={`journal-card quest ${quest.statusTone}`}>
                  <div className="journal-card-head">
                    <strong>{quest.quest}</strong>
                    <Pill tone={quest.statusTone}>{quest.statusLabel}</Pill>
                    {quest.progressCount > 0 && <Pill>进展 {quest.progressCount}</Pill>}
                  </div>
                  {quest.detail && <p>{quest.detail}</p>}
                  {quest.hooks.length > 0 && (
                    <dl className="journal-quest-hooks">
                      {quest.hooks.map(item => (
                        <div key={`${quest.quest}-${item.label}`} className={item.tone}>
                          <dt>{item.label}</dt>
                          <dd>{item.text}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                  {quest.timeline.length > 0 && (
                    <ol className="journal-quest-timeline" aria-label={`${quest.quest} 任务进展`}>
                      {quest.timeline.map(step => (
                        <li key={step.id} className={step.tone}>
                          <b>{step.status}</b>
                          <span>{step.detail}</span>
                          {step.at && <time>{step.at}</time>}
                        </li>
                      ))}
                    </ol>
                  )}
                </article>
              ))}
            </>
          )}
        </Section>

        <Section title="时间线" count={journal.timeline.length}>
          {journal.timeline.length === 0 ? <EmptyLine>暂无近期变化</EmptyLine> : (
            <>
              <div className="journal-timeline-summary" aria-label="时间线汇总">
                {journal.timelineSummary.map(item => (
                  <span key={item.label} className={item.tone}>
                    <b>{item.count}</b>{item.label}
                  </span>
                ))}
              </div>
              <ol className="journal-campaign-timeline" aria-label="完整时间线">
                {journal.timeline.map(item => (
                  <li key={item.id} className={`${item.tone} ${item.type}`}>
                    <b>{item.typeLabel}</b>
                    <span>{item.label}{item.detail ? `：${item.detail}` : ''}</span>
                    {item.at && <time>{item.at}</time>}
                  </li>
                ))}
              </ol>
            </>
          )}
        </Section>

        <Section title="队友" count={journal.companions.length} sectionRef={companionsSectionRef} sectionKey="companions">
          {journal.companions.length === 0 ? <EmptyLine>暂无队友档案</EmptyLine> : journal.companions.map(companion => (
            <article key={companion.id} className="journal-card companion">
              <div className="journal-card-head">
                <strong>{companion.name}</strong>
                <Pill tone="good">{companion.role}</Pill>
              </div>
              {companion.stats && <p className="journal-muted">{companion.stats}</p>}
              {companion.personality && <p>{companion.personality}</p>}
              {companion.speechStyle && <p className="journal-muted">说话风格：{companion.speechStyle}</p>}
              {companion.combatPreference && <p className="journal-muted">战斗偏好：{companion.combatPreference}</p>}
              {companion.catchphrase && <p className="journal-muted">口头禅：{companion.catchphrase}</p>}
              {companion.bond && (
                <div className="journal-companion-bond">
                  <div className="journal-companion-bond-row">
                    {companion.bond.relationship && <Pill tone="good">关系：{companion.bond.relationship}</Pill>}
                    {companion.bond.approval && <Pill tone={companion.bond.approval.tone}>好感 {companion.bond.approval.text} · {companion.bond.approval.label}</Pill>}
                    {companion.bond.deltaText && <Pill tone={companion.bond.deltaTone}>最近好感 {companion.bond.deltaText}</Pill>}
                  </div>
                  {companion.bond.approval && (
                    <div className={`journal-approval-meter ${companion.bond.approval.tone}`} aria-label={`${companion.name} 好感 ${companion.bond.approval.text}`}>
                      <span className="journal-approval-meter-fill" style={{ '--journal-approval-meter-width': companion.bond.approval.fill }} />
                    </div>
                  )}
                  {companion.bond.approval && (
                    <div className="journal-approval-thresholds" aria-label={`${companion.name} 好感阈值`}>
                      <span><b>阶段</b>{companion.bond.approval.label}</span>
                      <span><b>下一档</b>{companion.bond.approval.nextText}</span>
                    </div>
                  )}
                  {companion.bond.reason && <p className="journal-muted">最近影响：{companion.bond.reason}</p>}
                  {(companion.bond.personalQuest.title || companion.bond.personalQuest.detail || companion.bond.personalQuest.nextStep) && (
                    <div className="journal-personal-quest">
                      <div className="journal-card-head">
                        <strong>个人任务：{companion.bond.personalQuest.title || '未命名羁绊'}</strong>
                        <Pill tone={companion.bond.personalQuest.status.tone}>{companion.bond.personalQuest.status.label}</Pill>
                      </div>
                      {companion.bond.personalQuest.detail && <p>{companion.bond.personalQuest.detail}</p>}
                      {companion.bond.personalQuest.nextStep && <p className="journal-muted">下一步：{companion.bond.personalQuest.nextStep}</p>}
                    </div>
                  )}
                </div>
              )}
              {companion.recentReaction && (
                <p className="journal-companion-reaction" title={companion.recentReaction.at || ''}>
                  <span>最近反应</span>{companion.recentReaction.text}
                </p>
              )}
              {companion.backstory && <p>{companion.backstory}</p>}
            </article>
          ))}
        </Section>

        <Section title="NPC" count={journal.npcs.length}>
          {journal.npcs.length === 0 ? <EmptyLine>暂无 NPC 记录</EmptyLine> : journal.npcs.map(npc => (
            <article key={npc.name} className="journal-card">
              <div className="journal-card-head">
                <strong>{npc.name}</strong>
                <Pill>{npc.relationship}</Pill>
              </div>
              {npc.facts.length > 0 && <p>{npc.facts.join('；')}</p>}
              {npc.promises.length > 0 && <p className="journal-muted">承诺：{npc.promises.join('；')}</p>}
            </article>
          ))}
        </Section>

        <Section title="线索" count={journal.clues.length}>
          {journal.clues.length === 0 ? <EmptyLine>暂无线索记录</EmptyLine> : journal.clues.map((clue, index) => (
            <article key={`${clue.text}-${index}`} className="journal-card compact">
              <div className="journal-card-head">
                <strong>{clue.text}</strong>
                <Pill tone={clue.is_new ? 'active' : 'default'}>{clue.category || 'general'}</Pill>
              </div>
            </article>
          ))}
        </Section>

        <Section title="地点" count={journal.locations.length}>
          {journal.locations.length === 0 ? <EmptyLine>暂无地点记录</EmptyLine> : journal.locations.map(location => (
            <article key={location.name} className="journal-card compact">
              <div className="journal-card-head">
                <strong>{location.name}</strong>
                <Pill>{location.detail || '地点'}</Pill>
              </div>
            </article>
          ))}
        </Section>

        <Section title="未解决威胁" count={journal.threats.length}>
          {journal.threats.length === 0 ? <EmptyLine>暂无明确威胁</EmptyLine> : journal.threats.map((threat, index) => (
            <article key={`${threat.label}-${index}`} className="journal-card compact threat">
              <div className="journal-card-head">
                <strong>{threat.label}</strong>
                <Pill tone="danger">{threat.detail || '待处理'}</Pill>
              </div>
            </article>
          ))}
        </Section>

        <Section title="关键决定" count={journal.decisions.length}>
          {journal.decisions.length === 0 ? <EmptyLine>暂无关键决定</EmptyLine> : journal.decisions.map((decision, index) => (
            <article key={`${decision}-${index}`} className="journal-card compact">
              <p>{decision}</p>
            </article>
          ))}
        </Section>
      </div>

      <div className="journal-generated-panel" aria-label="生成日志" aria-live="polite">
        {loading ? (
          <div className="journal-generated-loading" role="status">
            DM 正在撰写日志...
          </div>
        ) : text ? (
          <p>{text}</p>
        ) : (
          <p className="journal-generated-empty">
            点击下方按钮生成本次冒险的叙述日志
          </p>
        )}
      </div>
      <div className="journal-modal-actions" role="group" aria-label="日志操作">
        <button className="btn-fantasy" onClick={onGenerate} disabled={loading} aria-label={loading ? '日志生成中' : '重新生成日志'}>
          {loading ? '生成中...' : '🔄 重新生成'}
        </button>
        <button className="btn-fantasy" onClick={onClose} aria-label="关闭日志">关闭</button>
      </div>
    </Overlay>
  )
}
