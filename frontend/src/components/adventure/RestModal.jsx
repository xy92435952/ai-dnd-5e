/**
 * RestModal — 休息选择弹窗（长休 / 短休）。
 *
 * Props:
 *   party   - 当前队伍角色，用于确认前预览休息影响
 *   onRest  - (rest_type: 'long' | 'short') => void
 *   onClose - () => void
 */
import Overlay from './Overlay'
import { RestIcon } from '../Icons'
import { summarizeRestPreview } from '../../utils/restPreview'
import { useState } from 'react'

function RestOption({ type, title, subtitle, summary, selected, onSelect }) {
  return (
    <button
      className={`btn-fantasy rest-option ${selected ? 'selected' : ''}`}
      aria-pressed={selected}
      aria-label={`选择${title}`}
      onClick={() => onSelect(type)}
    >
      <div className="rest-option-main">
        <strong>{title}</strong>
        <span>{subtitle}</span>
      </div>
      <div className="rest-option-stats" aria-label={`${title}预览摘要`}>
        <span>{summary.wounded} 人回血</span>
        <span>{summary.slotUsers} 人回法术位</span>
        {type === 'long' ? (
          <span>{summary.conditions} 个状态</span>
        ) : (
          <span>{summary.hitDiceRisk} 人生命骰不足</span>
        )}
      </div>
    </button>
  )
}

function PartyRestPreview({ preview }) {
  if (preview.length === 0) {
    return <p className="rest-empty">当前队伍没有可预览的角色状态。</p>
  }

  return (
    <div className="rest-party-preview" aria-label="休息前队伍状态预览">
      {preview.map(member => {
        const hpPct = member.hpMax ? Math.max(0, Math.min(100, (member.hpCurrent / member.hpMax) * 100)) : 0
        return (
          <section className="rest-member" key={member.id || member.name}>
            <div className="rest-member-head">
              <strong>{member.name}</strong>
              <span>HP {member.hpCurrent}/{member.hpMax || '?'}</span>
            </div>
            <div className="rest-member-meter" aria-hidden="true">
              <span className="rest-member-meter-fill" style={{ '--rest-member-hp-width': `${hpPct}%` }} />
            </div>
            <div className="rest-member-meta">
              {member.hitDiceRemaining != null && member.hitDiceTotal != null && (
                <span>生命骰 {member.hitDiceRemaining}/{member.hitDiceTotal}</span>
              )}
              {member.slotRestores.length > 0 && <span>法术位 {member.slotRestores.join('/')}</span>}
              {member.conditionChanges.length > 0 && <span>状态 {member.conditionChanges.join('/')}</span>}
            </div>
            <ul>
              {member.effects.map(effect => <li key={effect}>{effect}</li>)}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

export default function RestModal({ party = [], onRest, onClose }) {
  const [selectedRestType, setSelectedRestType] = useState('long')
  const longSummary = summarizeRestPreview(party, 'long')
  const shortSummary = summarizeRestPreview(party, 'short')
  const selectedSummary = selectedRestType === 'long' ? longSummary : shortSummary
  const selectedLabel = selectedRestType === 'long' ? '长休' : '短休'

  return (
    <Overlay onClose={onClose}>
      <div className="rest-modal-head">
        <h3>
          <RestIcon size={18} color="var(--amber)" /> 休息
        </h3>
        <button type="button" onClick={onClose} aria-label="关闭休息面板">×</button>
      </div>
      <p className="rest-explainer">
        休息会立即调用后端规则结算。下面是根据当前队伍状态推导的确认前预览，最终恢复量以掷骰和服务端结果为准。
      </p>
      <div className="rest-selection-status" role="status" aria-live="polite">
        <span>当前选择</span>
        <strong>{selectedLabel}</strong>
        <b>{selectedSummary.previews.length} 名角色预览</b>
      </div>
      <div className="rest-options">
        <RestOption
          type="long"
          title="长休（8小时）"
          subtitle="HP 回满、法术位全恢复、恢复部分生命骰并处理多数状态"
          summary={longSummary}
          selected={selectedRestType === 'long'}
          onSelect={setSelectedRestType}
        />
        <RestOption
          type="short"
          title="短休（1小时）"
          subtitle="受伤角色尝试消耗生命骰恢复 HP，魔契者恢复法术位"
          summary={shortSummary}
          selected={selectedRestType === 'short'}
          onSelect={setSelectedRestType}
        />
      </div>
      <PartyRestPreview preview={selectedSummary.previews} />
      <div className="rest-modal-actions" role="group" aria-label="休息操作">
        <button className="btn-fantasy" onClick={() => onRest(selectedRestType)} aria-label={`执行${selectedLabel}`}>
          执行{selectedLabel}
        </button>
        <button className="btn-fantasy secondary" onClick={onClose} aria-label="取消休息">取消</button>
      </div>
    </Overlay>
  )
}
