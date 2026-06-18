import { useEffect, useMemo, useState } from 'react'
import Overlay from './Overlay'
import { CheckpointIcon } from '../Icons'
import { gameApi } from '../../api/client'
import { filterPublicClues } from '../../utils/clueVisibility'

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
    clues: filterPublicClues(asArray(state.clues)).length,
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

function CheckpointScopeList({ title, items, tone = '' }) {
  return (
    <section className={`checkpoint-scope ${tone}`.trim()}>
      <h4>{title}</h4>
      <ul>
        {items.map(item => <li key={item}>{item}</li>)}
      </ul>
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
  const clues = filterPublicClues(asArray(state.clues)).map(item => item.text)
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
      <div className="checkpoint-modal-head">
        <h3>
          <CheckpointIcon size={18} color="var(--amber)" /> Checkpoint
        </h3>
        <button type="button" onClick={onClose} aria-label="关闭 checkpoint">×</button>
      </div>

      <div className="checkpoint-explainer" aria-label="Checkpoint 保存范围">
        <CheckpointScopeList
          title="会更新"
          items={['DM 长期战役记忆', '任务、NPC、线索、地点与世界状态', '之后继续冒险时的上下文参考']}
        />
        <CheckpointScopeList
          title="不会回滚"
          tone="warn"
          items={['HP、位置、背包或法术位', '战斗回合、临时提示或实时同步状态', '已经写入的可见日志']}
        />
      </div>

      <div className="checkpoint-summary" aria-label="Checkpoint 当前记忆摘要">
        <SummaryPill label="任务" value={summary.quests} />
        <SummaryPill label="NPC" value={summary.npcs} />
        <SummaryPill label="线索" value={summary.clues} />
        <SummaryPill label="场景" value={summary.scenes} />
        <SummaryPill label="状态" value={summary.flags} />
        <SummaryPill label="决定" value={summary.decisions} />
      </div>

      <div className="checkpoint-preview" aria-label="Checkpoint 会恢复的记忆" aria-live="polite">
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

      {saving && <p className="checkpoint-status" role="status">正在保存 checkpoint 记忆...</p>}
      {error && <p className="checkpoint-error" role="alert">{error}</p>}

      <div className="checkpoint-actions" role="group" aria-label="Checkpoint 操作">
        <button className="btn-fantasy checkpoint-action" onClick={handleSave} disabled={loading || saving}>
          {saving ? '保存中...' : '保存 / 更新 checkpoint'}
        </button>
        <button className="btn-fantasy checkpoint-action" onClick={onClose}>关闭</button>
      </div>
    </Overlay>
  )
}
