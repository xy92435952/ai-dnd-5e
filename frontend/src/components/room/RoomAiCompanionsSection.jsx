import Portrait from '../Portrait'
import { classKey } from '../Crests'
import { Divider } from '../Ornaments'

export default function RoomAiCompanionsSection({ aiCompanions }) {
  if ((aiCompanions || []).length === 0) return null

  return (
    <>
      <Divider>❧ AI 队友 ❧</Divider>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10, marginTop: 12 }}>
        {aiCompanions.map((companion) => (
          <div
            key={companion.id}
            className="panel-ornate"
            style={{ padding: 10, display: 'flex', gap: 10, alignItems: 'center', opacity: 0.92 }}
          >
            <Portrait cls={classKey(companion.char_class || 'fighter')} size="sm" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ fontFamily: 'var(--font-heading)', color: 'var(--parchment)', fontSize: 13, fontWeight: 600 }}>
                  {companion.name}
                </span>
                <span className="tag" style={{ fontSize: 9, background: 'rgba(139,110,230,.25)', border: '1px solid rgba(139,110,230,.6)', color: '#d4c2ff' }}>
                  ✦ AI
                </span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                {companion.race} · {companion.char_class} · Lv{companion.level}
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
