/**
 * JournalModal — 生成 / 展示冒险日志的弹窗。
 *
 * Props:
 *   session    - 当前冒险 session，用于结构化卷宗
 *   room       - 多人房间快照，用于分队地点
 *   text       - 当前日志文本（可为空）
 *   loading    - 生成中标志
 *   onGenerate - () => void 重新生成
 *   onClose    - () => void
 */
import Overlay from './Overlay'
import { JournalIcon } from '../Icons'

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
  decision: { label: '决定', tone: 'default' },
  npc: { label: 'NPC', tone: 'good' },
  world: { label: '后果', tone: 'danger' },
  threat: { label: '威胁', tone: 'danger' },
}

function getQuestStatusMeta(status) {
  const key = cleanText(status || 'active').toLowerCase()
  return QUEST_STATUS_META[key] || { label: status || '记录', tone: 'default' }
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

function buildQuestSummary(quest, recentUpdates) {
  const status = getQuestStatusMeta(quest?.status)
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
      }
    })

  return {
    quest: quest?.quest,
    statusLabel: status.label,
    statusTone: status.tone,
    detail: getQuestDetail(quest),
    timeline,
  }
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
  }
}

function buildCompanionSummary(companion) {
  const className = companion?.char_class || companion?.class || companion?.class_name
  const level = companion?.level ? `Lv ${companion.level}` : ''
  const role = joinParts([companion?.race, className, level]) || '队友'
  const derived = asObject(companion?.derived)
  const stats = joinParts([
    companion?.hp_max || derived.hp_max
      ? `HP ${companion?.hp_current ?? companion?.hp_max ?? derived.hp_max}/${companion?.hp_max ?? derived.hp_max}`
      : '',
    companion?.ac || derived.ac ? `AC ${companion?.ac ?? derived.ac}` : '',
    derived.speed ? `速度 ${derived.speed}` : '',
  ])

  return {
    id: companion?.id || companion?.name || role,
    name: companion?.name || '未命名队友',
    role,
    stats,
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
  const recentUpdates = asArray(campaign.recent_updates).filter(Boolean)
  const timeline = recentUpdates
    .slice(-8)
    .reverse()
    .map(buildTimelineEntry)
    .filter(item => item.label)
  const quests = asArray(campaign.quest_log)
    .filter(q => q?.quest)
    .map(q => buildQuestSummary(q, recentUpdates))
  const clues = asArray(campaign.clues).filter(c => c?.text)
  const companions = asArray(session?.companions)
    .filter(companion => companion && cleanText(companion.name))
    .map(buildCompanionSummary)
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
    companions,
    clues,
    npcs,
    locations,
    threats,
    decisions,
    timeline,
  }
}

function EmptyLine({ children }) {
  return <p style={{ margin: 0, color: 'var(--parchment-dark)', fontSize: 12, fontStyle: 'italic' }}>{children}</p>
}

function Section({ title, count, children }) {
  return (
    <section className="journal-section">
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

export default function JournalModal({ session, room, text, loading, onGenerate, onClose }) {
  const journal = buildJournalSections(session, room)

  return (
    <Overlay onClose={onClose}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ color: 'var(--amber)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <JournalIcon size={18} color="var(--amber)" /> 冒险卷宗
        </h3>
        <button onClick={onClose} style={{ color: 'var(--parchment-dark)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
      </div>

      <div className="journal-dossier" aria-label="冒险卷宗">
        <Section title="任务" count={journal.quests.length}>
          {journal.quests.length === 0 ? <EmptyLine>暂无任务记录</EmptyLine> : journal.quests.map((quest, index) => (
            <article key={`${quest.quest}-${index}`} className={`journal-card quest ${quest.statusTone}`}>
              <div className="journal-card-head">
                <strong>{quest.quest}</strong>
                <Pill tone={quest.statusTone}>{quest.statusLabel}</Pill>
              </div>
              {quest.detail && <p>{quest.detail}</p>}
              {quest.timeline.length > 0 && (
                <ol className="journal-quest-timeline" aria-label={`${quest.quest} 任务进展`}>
                  {quest.timeline.map(step => (
                    <li key={step.id} className={step.tone}>
                      <b>{step.status}</b>
                      <span>{step.detail}</span>
                    </li>
                  ))}
                </ol>
              )}
            </article>
          ))}
        </Section>

        <Section title="近期" count={journal.timeline.length}>
          {journal.timeline.length === 0 ? <EmptyLine>暂无近期变化</EmptyLine> : (
            <ol className="journal-campaign-timeline" aria-label="近期时间线">
              {journal.timeline.map(item => (
                <li key={item.id} className={`${item.tone} ${item.type}`}>
                  <b>{item.typeLabel}</b>
                  <span>{item.label}{item.detail ? `：${item.detail}` : ''}</span>
                </li>
              ))}
            </ol>
          )}
        </Section>

        <Section title="队友" count={journal.companions.length}>
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

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 160, maxHeight: '32vh', background: '#0a0604', borderRadius: 8, padding: 16, border: '1px solid var(--bark)' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--amber)' }}>
            DM 正在撰写日志...
          </div>
        ) : text ? (
          <p style={{ color: 'var(--parchment)', lineHeight: 1.9, fontSize: 14, whiteSpace: 'pre-wrap', margin: 0 }}>{text}</p>
        ) : (
          <p style={{ color: 'var(--parchment-dark)', textAlign: 'center', marginTop: 32, fontSize: 13 }}>
            点击下方按钮生成本次冒险的叙述日志
          </p>
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onGenerate} disabled={loading}>
          {loading ? '生成中...' : '🔄 重新生成'}
        </button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>关闭</button>
      </div>
    </Overlay>
  )
}
