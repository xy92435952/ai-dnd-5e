import { useMemo } from 'react'
import { buildMultiplayerTimeline, summarizeTimelineLane } from '../../utils/multiplayerTimeline'

function LaneColumn({ lane }) {
  const items = lane.items || []
  return (
    <div style={{
      minWidth: 0,
      display: 'grid',
      gap: 5,
      alignContent: 'start',
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 8,
        color: 'var(--arcane-light)',
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        letterSpacing: '.08em',
      }}>
        <span>{summarizeTimelineLane(lane)}</span>
      </div>

      {items.length === 0 ? (
        <div style={{
          minHeight: 36,
          padding: '7px 8px',
          border: '1px dashed rgba(198,168,92,.18)',
          color: 'rgba(230,220,186,.46)',
          fontSize: 10,
          fontStyle: 'italic',
        }}>
          暂无可见记录
        </div>
      ) : items.map(item => (
        <div
          key={item.id}
          style={{
            minHeight: 36,
            padding: '6px 8px',
            borderLeft: lane.id === 'public'
              ? '2px solid rgba(240,208,96,.45)'
              : lane.id === 'private'
                ? '2px solid rgba(220,110,160,.5)'
                : '2px solid rgba(127,232,248,.48)',
            background: 'rgba(255,248,220,.045)',
            color: 'var(--parchment-dark)',
            fontSize: 11,
            lineHeight: 1.45,
            overflow: 'hidden',
          }}
        >
          <span style={{
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}>
            {item.text}
          </span>
        </div>
      ))}
    </div>
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
    <div style={{
      margin: '0 24px',
      padding: '8px 10px',
      border: '1px solid rgba(198,168,92,.22)',
      borderTop: 0,
      background: 'rgba(10,8,14,.74)',
      color: 'var(--parchment)',
      display: 'grid',
      gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            color: 'var(--amber)',
            fontSize: 11,
            letterSpacing: '.14em',
          }}>
            分队时间线
          </span>
          <span style={{ color: 'var(--parchment-dark)', fontSize: 11 }}>
            {timeline.myGroup.name || timeline.myGroup.id}
          </span>
        </div>
        {activeGroupLabel && (
          <span style={{ color: 'rgba(230,220,186,.56)', fontSize: 10 }}>
            当前镜头：{activeGroupLabel}
          </span>
        )}
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 8,
      }}>
        <LaneColumn lane={timeline.lanes.public} />
        <LaneColumn lane={timeline.lanes.group} />
        <LaneColumn lane={timeline.lanes.private} />
      </div>
    </div>
  )
}
