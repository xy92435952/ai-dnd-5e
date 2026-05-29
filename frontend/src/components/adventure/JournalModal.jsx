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

function buildJournalSections(session, room) {
  const campaign = asObject(session?.campaign_state)
  const gameState = asObject(session?.game_state)
  const sceneVibe = asObject(gameState.scene_vibe)
  const quests = asArray(campaign.quest_log).filter(q => q?.quest)
  const clues = asArray(campaign.clues).filter(c => c?.text)
  const decisions = asArray(campaign.key_decisions).filter(Boolean)
  const completedScenes = asArray(campaign.completed_scenes).filter(Boolean)
  const recentUpdates = asArray(campaign.recent_updates).filter(Boolean)

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
    clues,
    npcs,
    locations,
    threats,
    decisions,
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
            <article key={`${quest.quest}-${index}`} className="journal-card">
              <div className="journal-card-head">
                <strong>{quest.quest}</strong>
                <Pill tone={quest.status === 'completed' ? 'good' : quest.status === 'failed' ? 'danger' : 'active'}>{quest.status || 'active'}</Pill>
              </div>
              {quest.outcome && <p>{quest.outcome}</p>}
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
