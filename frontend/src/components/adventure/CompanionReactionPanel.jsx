import { renderLightMarkdown } from '../../utils/markdown'

export default function CompanionReactionPanel({ reactions = [], visible = true }) {
  const items = Array.isArray(reactions) ? reactions.filter(item => item?.text) : []
  if (!visible || items.length === 0) return null

  return (
    <aside
      aria-label="队友反应"
      style={{
        marginTop: 10,
        padding: '10px 12px',
        border: '1px solid rgba(127,232,248,.28)',
        borderLeft: '3px solid rgba(127,232,248,.75)',
        borderRadius: 6,
        background: 'linear-gradient(180deg, rgba(10,24,34,.68), rgba(6,14,22,.82))',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,.04)',
      }}
    >
      <div style={{
        marginBottom: 7,
        fontFamily: 'var(--font-heading)',
        fontSize: 11,
        color: 'var(--arcane-light)',
        letterSpacing: 0,
        fontWeight: 700,
      }}>
        队友反应
      </div>
      <div style={{ display: 'grid', gap: 6 }}>
        {items.map((item, index) => (
          <p
            key={`${item.speaker || 'companion'}-${index}`}
            style={{
              margin: 0,
              padding: '0 0 0 10px',
              borderLeft: '2px solid rgba(90,168,120,.55)',
              color: '#b8f0d0',
              fontFamily: 'var(--font-body)',
              fontSize: 12,
              lineHeight: 1.6,
              fontStyle: 'italic',
            }}
          >
            <strong style={{
              color: 'var(--emerald-light)',
              fontStyle: 'normal',
              fontWeight: 700,
            }}>
              {item.speaker || '队友'}：
            </strong>
            {renderLightMarkdown(item.text, '#a8f0c0')}
          </p>
        ))}
      </div>
    </aside>
  )
}
