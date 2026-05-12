import { extractNarrative } from './dialogue'

const DEFAULT_LIMIT = 5

function findMyGroup(room, myUserId) {
  const groups = room?.party_groups || []
  return groups.find(group => (group.member_user_ids || []).includes(myUserId))
    || groups.find(group => group.id === room?.active_group_id)
    || groups[0]
    || null
}

function isVisibleToUser(visibility, myUserId) {
  const visibleTo = visibility?.visible_to_user_ids
  if (!Array.isArray(visibleTo) || visibleTo.length === 0) return true
  return visibleTo.includes(myUserId)
}

function normalizeTimelineItem(log, index) {
  return {
    id: log.id || log.log_id || `${index}-${log.role || 'log'}`,
    role: log.role,
    text: extractNarrative(log.content || log.text || ''),
    visibility: log.visibility || null,
    createdAt: log.created_at || log.createdAt || null,
  }
}

export function buildMultiplayerTimeline({ logs = [], room = null, myUserId = null, limit = DEFAULT_LIMIT }) {
  const myGroup = findMyGroup(room, myUserId)
  const lanes = {
    public: { id: 'public', label: '公共', items: [] },
    group: { id: 'group', label: '我的分队', items: [] },
    private: { id: 'private', label: '私密', items: [] },
  }

  logs.forEach((log, index) => {
    if (log?.role !== 'dm') return
    if (!isVisibleToUser(log.visibility, myUserId)) return

    const item = normalizeTimelineItem(log, index)
    if (!item.text) return

    const scope = log.visibility?.scope || 'party'
    if (scope === 'private') {
      lanes.private.items.push(item)
    } else if (scope === 'group') {
      lanes.group.items.push(item)
    } else {
      lanes.public.items.push(item)
    }
  })

  Object.values(lanes).forEach(lane => {
    lane.items = lane.items.slice(-limit).reverse()
  })

  return {
    myGroup,
    activeGroupId: room?.active_group_id || null,
    lanes,
    hasItems: Object.values(lanes).some(lane => lane.items.length > 0),
  }
}

export function summarizeTimelineLane(lane) {
  return `${lane?.label || '时间线'} ${(lane?.items || []).length}`
}
