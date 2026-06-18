import { useId } from 'react'
import {
  getReactionPromptContext,
  getReactionPromptMeta,
  isReactionPromptForCharacter,
  normalizeReactionOptions,
} from '../../utils/combatReactionPrompt'

export default function ReactionPrompt({
  prompt,
  currentCharacterId = null,
  onReact,
  onCancel,
}) {
  const promptDomId = useId()

  if (!prompt) return null

  const canReact = isReactionPromptForCharacter(prompt, currentCharacterId)
  const options = normalizeReactionOptions(prompt)
  const meta = getReactionPromptMeta(prompt)
  const context = getReactionPromptContext(prompt)
  const reactorLabel = prompt.reactor_name || prompt.reactor_character_name || prompt.reactor_character_id || '另一名角色'
  const titleId = `${promptDomId}-title`
  const contextId = `${promptDomId}-context`
  const statusId = `${promptDomId}-status`
  const optionCountLabel = options.length > 0 ? `${options.length} 个可用反应` : '没有可用反应'

  if (!canReact) {
    return (
      <aside className="reaction-watch" role="status" aria-live="polite">
        <strong>反应窗口</strong>
        <span>{reactorLabel} 正在选择反应</span>
      </aside>
    )
  }

  return (
    <div
      className="reaction-prompt-layer"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={`${contextId} ${statusId}`}
      aria-live="polite"
    >
      <section className="reaction-prompt-card">
        <header className="reaction-prompt-head">
          <span className="reaction-prompt-icon" aria-hidden="true">⚡</span>
          <div>
            <p id={titleId} className="reaction-prompt-title">反应触发</p>
            <p id={contextId} className="reaction-prompt-context">{context}</p>
          </div>
        </header>

        {meta.length > 0 && (
          <div className="reaction-prompt-meta">
            {meta.map(item => <span key={item}>{item}</span>)}
          </div>
        )}

        <div id={statusId} className="reaction-prompt-status">
          <span>{optionCountLabel}</span>
          <span>等待你的裁定</span>
        </div>

        <div className="reaction-prompt-actions" role="group" aria-label="可用反应">
          {options.length > 0 ? options.map((opt, i) => (
            <button
              key={`${opt.type}-${i}`}
              className="btn-gold reaction-prompt-action"
              title={reactionActionTitle(opt)}
              onClick={() => {
                if (opt.type === 'cutting_words' || opt.type === 'cutting_words_damage' || opt.type === 'bardic_spell_save') {
                  onReact(opt.type, opt.target_id, opt.character_id || prompt.reactor_character_id, opt)
                } else {
                  onReact(opt.type, opt.target_id, opt.character_id || prompt.reactor_character_id)
                }
              }}
            >
              <span>{opt.label}</span>
              {opt.cost && <small>{opt.cost}</small>}
              {opt.hp_outcome ? <ReactionOutcome outcome={opt.hp_outcome} /> : opt.hp_preview && (
                <small className="reaction-prompt-hp">{opt.hp_preview}</small>
              )}
            </button>
          )) : (
            <div className="reaction-prompt-empty" role="status">
              当前没有可用反应，只能放弃反应窗口。
            </div>
          )}
          <button className="btn-ghost reaction-prompt-decline" onClick={() => onCancel?.(prompt)}>
            放弃反应
          </button>
        </div>
      </section>
    </div>
  )
}

function ReactionOutcome({ outcome }) {
  const hasHp = outcome.hp_before !== undefined
  return (
    <span className="reaction-outcome-panel" aria-label="反应结果预览">
      <span className="reaction-outcome-caption">结果预览</span>
      {hasHp ? (
        <>
          <span>{outcome.no_reaction_label}</span>
          <b>{outcome.reaction_label}</b>
        </>
      ) : (
        <b>{outcome.hp_preview}</b>
      )}
      <em>{outcome.prevented_label}</em>
      {outcome.risk_label && <strong>{outcome.risk_label}</strong>}
    </span>
  )
}

function reactionActionTitle(option = {}) {
  return [option.label, option.cost, option.hp_preview, option.hp_outcome?.prevented_label, option.hp_outcome?.risk_label]
    .filter(Boolean)
    .join(' · ')
}
