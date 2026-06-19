import Portrait from '../Portrait'
import { classKey } from '../Crests'
import { Divider } from '../Ornaments'

export default function RoomAiCompanionsSection({ aiCompanions }) {
  if ((aiCompanions || []).length === 0) return null

  return (
    <>
      <Divider>❧ AI 队友 ❧</Divider>
      <div className="room-ai-grid">
        {aiCompanions.map((companion) => (
          <div
            key={companion.id}
            className="panel-ornate room-ai-card"
          >
            <Portrait cls={classKey(companion.char_class || 'fighter')} size="sm" />
            <div className="room-ai-body">
              <div className="room-ai-identity">
                <span className="room-ai-name">
                  {companion.name}
                </span>
                <span className="tag room-ai-tag">
                  ✦ AI
                </span>
              </div>
              <div className="room-ai-meta">
                {companion.race} · {companion.char_class} · Lv{companion.level}
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
