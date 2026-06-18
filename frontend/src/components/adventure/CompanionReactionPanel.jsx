import { renderLightMarkdown } from '../../utils/markdown'

export default function CompanionReactionPanel({ reactions = [], visible = true }) {
  const items = Array.isArray(reactions) ? reactions.filter(item => item?.text) : []
  if (!visible || items.length === 0) return null

  return (
    <aside
      className="companion-reaction-panel"
      aria-label="队友反应"
      aria-live="polite"
    >
      <div className="companion-reaction-title">
        队友反应
      </div>
      <div className="companion-reaction-list" role="list" aria-label="队友反应列表">
        {items.map((item, index) => (
          <p
            key={`${item.speaker || 'companion'}-${index}`}
            className="companion-reaction-item"
            role="listitem"
          >
            <strong className="companion-reaction-speaker">
              {item.speaker || '队友'}：
            </strong>
            {renderLightMarkdown(item.text, '#a8f0c0')}
          </p>
        ))}
      </div>
    </aside>
  )
}
