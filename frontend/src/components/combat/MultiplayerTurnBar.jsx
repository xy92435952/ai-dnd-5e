import { getCombatTurnControllerStatus, getCombatTurnStatusText } from '../../utils/multiplayerStatus'
import MultiplayerSessionStatusBar from '../multiplayer/MultiplayerSessionStatusBar'
import WebSocketStatusPill from '../multiplayer/WebSocketStatusPill'

export default function MultiplayerTurnBar({
  room,
  wsConnected = false,
  wsStatus = null,
  syncBlocked = false,
  currentTurnLabel,
  isMyTurnMP,
  controllerName = '',
  currentTurnCharacterId = null,
}) {
  if (!room?.is_multiplayer || !currentTurnLabel) return null
  const controllerStatus = getCombatTurnControllerStatus({ room, currentTurnCharacterId, isMyTurnMP })
  const turnStatusText = controllerStatus.label || getCombatTurnStatusText({
    isMyTurnMP,
    controllerName: controllerStatus.controllerName || controllerName,
  })
  const statusText = syncBlocked ? '同步中 · 暂停战斗操作' : turnStatusText

  return (
    <MultiplayerSessionStatusBar
      room={room}
      label="多人战斗"
      title={syncBlocked ? '同步中' : isMyTurnMP ? '你的回合' : '等待回合'}
      reason={currentTurnLabel}
      focusLabel={statusText}
      tone={!syncBlocked && isMyTurnMP ? 'active' : 'table'}
    >
      <WebSocketStatusPill status={wsStatus} connected={wsConnected} />
    </MultiplayerSessionStatusBar>
  )
}
