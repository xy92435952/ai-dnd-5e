import { useMemo } from 'react'
import { buildMultiplayerTimeline, summarizeTimelineLane } from '../../utils/multiplayerTimeline'

function LaneColumn({ lane }) {
  const items = lane.items || []
  const laneSummary = summarizeTimelineLane(lane)
  return (
    <section className={`multiplayer-timeline-lane ${lane.id}`} aria-label={laneSummary}>
      <div className="multiplayer-timeline-lane-head">
        <span>{laneSummary}</span>
        <b>{items.length}</b>
      </div>

      {items.length === 0 ? (
        <div className="multiplayer-timeline-empty">
          暂无可见记录
        </div>
      ) : items.map(item => (
        <div
          key={item.id}
          className="multiplayer-timeline-item"
        >
          <span>{item.text}</span>
        </div>
      ))}
    </section>
  )
}

function getActiveGroupLabel(room, timeline) {
  if (!timeline.activeGroupId) return ''
  if (timeline.activeGroupId === timeline.myGroup?.id) return '我的分队'
  const activeGroup = (room?.party_groups || []).find(group => group.id === timeline.activeGroupId)
  return activeGroup?.name || timeline.activeGroupId
}

export default function MultiplayerTimelinePanel({ room, logs, myUserId }) {
  const timeline = useMemo(
    () => buildMultiplayerTimeline({ logs, room, myUserId }),
    [logs, room, myUserId],
  )

  if (!room || !myUserId || !timeline.myGroup) return null
  const activeGroupLabel = getActiveGroupLabel(room, timeline)

  return (
    <section className="multiplayer-timeline-panel" aria-label="分队时间线">
      <div className="multiplayer-timeline-head">
        <div className="multiplayer-timeline-title">
          <span>分队时间线</span>
          <strong>
            {timeline.myGroup.name || timeline.myGroup.id}
          </strong>
        </div>
        {activeGroupLabel && (
          <span className="multiplayer-timeline-active" role="status">
            当前镜头：{activeGroupLabel}
          </span>
        )}
      </div>

      <div className="multiplayer-timeline-lanes" aria-label="分队可见记录">
        <LaneColumn lane={timeline.lanes.public} />
        <LaneColumn lane={timeline.lanes.group} />
        <LaneColumn lane={timeline.lanes.private} />
      </div>
    </section>
  )
}
