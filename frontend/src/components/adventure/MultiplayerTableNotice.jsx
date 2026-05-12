import {
  getMultiplayerTableStatus,
} from '../../utils/multiplayerGroups'
import MultiplayerSessionStatusBar from '../multiplayer/MultiplayerSessionStatusBar'

export default function MultiplayerTableNotice({
  room,
  myUserId,
  currentSeg,
  logs,
}) {
  if (!room?.is_multiplayer || !myUserId) return null

  const tableStatus = getMultiplayerTableStatus({ room, myUserId, currentSeg, logs })
  if (!tableStatus.shouldShowNotice) return null

  return (
    <MultiplayerSessionStatusBar
      room={room}
      label="DM 调度原因"
      title={tableStatus.tableDecisionLabel}
      reason={tableStatus.tableReason}
      focusLabel={tableStatus.activeGroupLabel ? `当前镜头：${tableStatus.activeGroupLabel}` : ''}
      nextLabel={tableStatus.nextReadySummary}
    />
  )
}
