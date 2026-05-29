import { useEffect, useMemo, useState } from 'react'
import Overlay from './Overlay'
import { CheckpointIcon } from '../Icons'
import { gameApi } from '../../api/client'

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function countSummary(campaignState = {}) {
  const state = asObject(campaignState)
  return {
    quests: asArray(state.quest_log).filter(item => item?.quest).length,
    npcs: Object.keys(asObject(state.npc_registry)).length,
    clues: asArray(state.clues).filter(item => item?.text).length,
    scenes: asArray(state.completed_scenes).filter(Boolean).length,
    flags: Object.values(asObject(state.world_flags)).filter(Boolean).length,
    decisions: asArray(state.key_decisions).filter(Boolean).length,
  }
}

function SummaryPill({ label, value }) {
  return (
    <span className="checkpoint-pill">
      <b>{value}</b>
      {label}
    </span>
  )
}

function PreviewList({ title, items, empty }) {
  return (
    <section className="checkpoint-preview-section">
      <h4>{title}</h4>
      {items.length === 0 ? (
        <p className="checkpoint-empty">{empty}</p>
      ) : (
        <ul>
          {items.slice(0, 4).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ul>
      )}
    </section>
  )
}

function buildPreviewItems(campaignState = {}) {
  const state = asObject(campaignState)
  const quests = asArray(state.quest_log)
    .filter(item => item?.quest)
    .map(item => `${item.quest}${item.status ? ` · ${item.status}` : ''}`)
  const npcs = Object.entries(asObject(state.npc_registry))
    .map(([name, data]) => `${name}${data?.relationship ? ` · ${data.relationship}` : ''}`)
  const clues = asArray(state.clues).filter(item => item?.text).map(item => item.text)
  const flags = Object.entries(asObject(state.world_flags))
    .filter(([, value]) => value)
    .map(([key]) => key.replace(/[_-]+/g, ' '))
  return { quests, npcs, clues, flags }
}

export default function CheckpointModal({ sessionId, onSave, onClose }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [checkpoint, setCheckpoint] = useState(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    gameApi.getCheckpoint(sessionId)
      .then(data => { if (alive) setCheckpoint(data) })
      .catch(e => { if (alive) setError(e.message || '读取 checkpoint 失败') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [sessionId])

  const campaignState = useMemo(() => checkpoint?.campaign_state || {}, [checkpoint])
  const summary = useMemo(() => countSummary(campaignState), [campaignState])
  const preview = useMemo(() => buildPreviewItems(campaignState), [campaignState])

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const result = await onSave()
      if (result?.campaign_state) {
        setCheckpoint({ has_checkpoint: true, campaign_state: result.campaign_state })
      }
      onClose()
    } catch (e) {
      setError(e.message || '保存 checkpoint 失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Overlay onClose={onClose}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ color: 'var(--amber)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <CheckpointIcon size={18} color="var(--amber)" /> Checkpoint
        </h3>
        <button onClick={onClose} style={{ color: 'var(--parchment-dark)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
      </div>

      <div className="checkpoint-explainer">
        <p>
          这个 checkpoint 会更新 DM 的长期战役记忆。之后继续冒险时，DM 会参考这里的任务、NPC、线索、地点和世界状态。
        </p>
        <p className="checkpoint-warning">
          它不会回滚 HP、位置、背包、战斗回合或已经写入的日志；这些仍以当前会话状态为准。
        </p>
      </div>

      <div className="checkpoint-summary" aria-label="Checkpoint 当前记忆摘要">
        <SummaryPill label="任务" value={summary.quests} />
        <SummaryPill label="NPC" value={summary.npcs} />
        <SummaryPill label="线索" value={summary.clues} />
        <SummaryPill label="场景" value={summary.scenes} />
        <SummaryPill label="状态" value={summary.flags} />
        <SummaryPill label="决定" value={summary.decisions} />
      </div>

      <div className="checkpoint-preview" aria-label="Checkpoint 会恢复的记忆">
        {loading ? (
          <p className="checkpoint-empty">正在读取 checkpoint...</p>
        ) : checkpoint?.has_checkpoint ? (
          <>
            <PreviewList title="任务" items={preview.quests} empty="暂无任务记忆" />
            <PreviewList title="NPC" items={preview.npcs} empty="暂无 NPC 记忆" />
            <PreviewList title="线索" items={preview.clues} empty="暂无线索记忆" />
            <PreviewList title="世界状态" items={preview.flags} empty="暂无世界状态" />
          </>
        ) : (
          <p className="checkpoint-empty">还没有 checkpoint。保存后会从可见日志生成长期战役记忆。</p>
        )}
      </div>

      {error && <p className="checkpoint-error">{error}</p>}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={handleSave} disabled={loading || saving}>
          {saving ? '保存中...' : '保存 / 更新 checkpoint'}
        </button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>关闭</button>
      </div>
    </Overlay>
  )
}
