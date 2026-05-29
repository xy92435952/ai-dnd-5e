import { buildCombatLogView } from '../../utils/combatLog'
import { DiceD20Icon, ScrollIcon } from '../Icons'

export default function CombatLogEntry({ log }) {
  const view = buildCombatLogView(log)
  const Icon = view.tone === 'system' ? ScrollIcon : DiceD20Icon
  const feedbackClasses = view.feedback.map(item => `feedback-${item.kind}`).join(' ')

  return (
    <article className={`log-entry ${view.tone} ${feedbackClasses}`.trim()}>
      <div className="log-entry-head">
        <span className="log-entry-icon" aria-hidden="true">
          <Icon size={13} />
        </span>
        <span className="log-entry-role">{view.roleLabel}</span>
      </div>

      <div className="log-entry-body">
        {view.feedback.length > 0 && (
          <div className="log-feedback-row" aria-label="战斗反馈">
            {view.feedback.map(item => (
              <span key={item.kind} className={`log-feedback ${item.kind}`}>{item.label}</span>
            ))}
          </div>
        )}

        {view.sections.map(section => (
          <div key={section.kind} className={`log-section ${section.kind}`}>
            <span className="log-section-label">{section.label}</span>
            <div className="log-section-items">
              {section.items.map((item, index) => (
                <span key={`${section.kind}-${index}`}>{item}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </article>
  )
}
