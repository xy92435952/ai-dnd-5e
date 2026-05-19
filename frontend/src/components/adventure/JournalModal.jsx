/**
 * JournalModal — 生成 / 展示冒险日志的弹窗。
 *
 * Props:
 *   text          - 当前日志文本（可为空）
 *   loading       - 生成中标志
 *   campaignState - session.campaign_state，用于结构化展示长期记忆
 *   onGenerate    - () => void 重新生成
 *   onClose       - () => void
 */
import Overlay from './Overlay'
import { JournalIcon } from '../Icons'

function compactText(value, fallback = '暂无记录') {
  if (typeof value === 'string' && value.trim()) return value.trim()
  return fallback
}

function questTitle(quest) {
  return compactText(quest?.title || quest?.name || quest?.quest || quest?.id)
}

function clueText(clue) {
  if (typeof clue === 'string') return clue
  return compactText(clue?.text || clue?.summary || clue?.description || clue?.clue)
}

function decisionText(decision) {
  if (typeof decision === 'string') return decision
  return compactText(decision?.text || decision?.summary || decision?.decision)
}

function statusLabel(status) {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed' || normalized === 'done') return '已完成'
  if (normalized === 'failed') return '失败'
  if (normalized === 'inactive') return '暂缓'
  return '进行中'
}

function Section({ title, children, empty }) {
  return (
    <section style={{
      border: '1px solid rgba(138,90,24,.55)',
      background: 'rgba(22,14,8,.72)',
      borderRadius: 6,
      padding: 12,
      minHeight: 96,
    }}>
      <h4 style={{
        margin: '0 0 8px',
        color: 'var(--amber)',
        fontSize: 13,
        fontFamily: 'var(--font-heading)',
        letterSpacing: 0,
      }}>{title}</h4>
      {children || (
        <p style={{ margin: 0, color: 'var(--parchment-dark)', fontSize: 12, lineHeight: 1.6 }}>{empty}</p>
      )}
    </section>
  )
}

export default function JournalModal({ text, loading, campaignState = {}, onGenerate, onClose }) {
  const quests = Array.isArray(campaignState?.quest_log) ? campaignState.quest_log : []
  const clues = Array.isArray(campaignState?.clues) ? campaignState.clues : []
  const npcEntries = Object.entries(campaignState?.npc_registry || {})
  const keyDecisions = Array.isArray(campaignState?.key_decisions) ? campaignState.key_decisions : []

  return (
    <Overlay onClose={onClose}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ color: 'var(--amber)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <JournalIcon size={18} color="var(--amber)" /> 冒险日志
        </h3>
        <button onClick={onClose} style={{ color: 'var(--parchment-dark)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 260, maxHeight: '62vh', background: '#0a0604', borderRadius: 8, padding: 16, border: '1px solid var(--bark)' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--amber)' }}>
            DM 正在撰写日志...
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 14 }}>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 10,
            }}>
              <Section title="任务" empty="尚未记录任务线。">
                {quests.length > 0 && (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {quests.map((quest, idx) => (
                      <div key={`${questTitle(quest)}-${idx}`}>
                        <div style={{ color: 'var(--parchment)', fontSize: 13 }}>{questTitle(quest)}</div>
                        <div style={{ color: 'var(--parchment-dark)', fontSize: 11, marginTop: 2 }}>
                          {statusLabel(quest?.status)}
                          {quest?.summary ? ` · ${quest.summary}` : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Section>

              <Section title="线索" empty="玩家还没有发现可追踪线索。">
                {clues.length > 0 && (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {clues.map((clue, idx) => (
                      <div key={`${clueText(clue)}-${idx}`}>
                        <div style={{ color: 'var(--parchment)', fontSize: 13 }}>{clueText(clue)}</div>
                        {clue?.found_at && (
                          <div style={{ color: 'var(--parchment-dark)', fontSize: 11, marginTop: 2 }}>
                            发现于 {clue.found_at}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Section>

              <Section title="人物" empty="尚未记录重要 NPC。">
                {npcEntries.length > 0 && (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {npcEntries.map(([name, data]) => (
                      <div key={name}>
                        <div style={{ color: 'var(--parchment)', fontSize: 13 }}>{name}</div>
                        <div style={{ color: 'var(--parchment-dark)', fontSize: 11, marginTop: 2 }}>
                          {compactText(data?.relationship, '关系未明')}
                          {Array.isArray(data?.key_facts) && data.key_facts.length > 0 ? ` · ${data.key_facts.slice(-2).join('；')}` : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Section>

              <Section title="关键决定" empty="尚未记录关键决定。">
                {keyDecisions.length > 0 && (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {keyDecisions.map((decision, idx) => (
                      <div key={`${decisionText(decision)}-${idx}`} style={{ color: 'var(--parchment)', fontSize: 13, lineHeight: 1.5 }}>
                        {decisionText(decision)}
                      </div>
                    ))}
                  </div>
                )}
              </Section>
            </div>

            {text ? (
              <div style={{
                borderTop: '1px solid rgba(138,90,24,.45)',
                paddingTop: 12,
              }}>
                <p style={{ color: 'var(--parchment)', lineHeight: 1.9, fontSize: 14, whiteSpace: 'pre-wrap', margin: 0 }}>{text}</p>
              </div>
            ) : (
              <p style={{ color: 'var(--parchment-dark)', textAlign: 'center', margin: '12px 0 0', fontSize: 13 }}>
                点击下方按钮生成本次冒险的叙述日志
              </p>
            )}
          </div>
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onGenerate} disabled={loading}>
          {loading ? '生成中...' : '重新生成'}
        </button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>关闭</button>
      </div>
    </Overlay>
  )
}
