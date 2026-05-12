import { getCombatTurnControllerStatus, getCombatTurnStatusText } from '../../utils/multiplayerStatus'
import MultiplayerSessionStatusBar from '../multiplayer/MultiplayerSessionStatusBar'

export default function MultiplayerTurnBar({ room, currentTurnLabel, isMyTurnMP, controllerName = '', currentTurnCharacterId = null }) {
  if (!room?.is_multiplayer || !currentTurnLabel) return null
  const controllerStatus = getCombatTurnControllerStatus({ room, currentTurnCharacterId, isMyTurnMP })
  const statusText = controllerStatus.label || getCombatTurnStatusText({
    isMyTurnMP,
    controllerName: controllerStatus.controllerName || controllerName,
  })

  return (
    <MultiplayerSessionStatusBar
      room={room}
      label="多人战斗"
      title={isMyTurnMP ? '你的回合' : '等待回合'}
      reason={currentTurnLabel}
      focusLabel={statusText}
      tone={isMyTurnMP ? 'active' : 'table'}
    />
  )
}
