/**
 * MultiplayerSpeakBar — Adventure 顶部多人发言权提示条。
 *
 * 只负责展示和把按钮动作交还给页面；AI 代演、WS 消息发送等业务仍在
 * Adventure.jsx 中，避免展示组件知道 API 细节。
 */
import {
  getAiTakeoverStatus,
  getSpeakTurnStatusText,
  getSpeakerOnlineStatus,
} from '../../utils/multiplayerStatus'
import WebSocketStatusPill from '../multiplayer/WebSocketStatusPill'

export default function MultiplayerSpeakBar({
  room,
  wsConnected = false,
  wsStatus = null,
  syncNotice = '',
  myUserId = null,
  player = null,
  isMySpeakTurn,
  currentSpeakerUid,
  currentSpeakerName,
  onSkipTurn,
  onAiTakeover,
}) {
  if (!room) return null
  const statusText = getSpeakTurnStatusText({ isMySpeakTurn, currentSpeakerName })
  const speakerStatus = getSpeakerOnlineStatus(room, currentSpeakerUid)
  const takeoverStatus = getAiTakeoverStatus({ room, currentSpeakerUid, isMySpeakTurn })
  const canTakeover = takeoverStatus.canTakeover && wsConnected
  const takeoverTitle = !wsConnected
    ? '房间正在重新同步，请恢复连接后再使用 AI 代演'
    : takeoverStatus.label || (canTakeover ? '该玩家离线，可让 AI 据其人设代演一句' : '当前发言者仍在线，暂不能代演')
  const takeoverButtonLabel = takeoverStatus.canTakeover
    ? 'AI 代演'
    : takeoverStatus.label || `玩家${speakerStatus.label}`
  const takeoverHint = !isMySpeakTurn && currentSpeakerUid
    ? !wsConnected && takeoverStatus.canTakeover
      ? '同步恢复后可代演'
      : takeoverStatus.canTakeover
        ? 'AI 可接管'
        : !speakerStatus.isOnline && takeoverStatus.secondsRemaining > 0
          ? `${takeoverStatus.secondsRemaining}秒后可代演`
          : ''
    : ''
  const myMember = (room.members || []).find(member => member.user_id === myUserId)
  const speakerMember = (room.members || []).find(member => member.user_id === currentSpeakerUid)
  const myCharacterName = myMember?.character_name || player?.name || (myMember?.character_id ? '已绑定角色' : '未绑定角色')
  const speakerLabel = currentSpeakerName || '等待同步'
  const speakerCharacterName = speakerMember?.character_name || (speakerMember?.character_id ? '已绑定角色' : '')
  const speakerIdentity = speakerCharacterName ? `${speakerLabel} / ${speakerCharacterName}` : speakerLabel
  const speakerStatusTitle = speakerCharacterName
    ? `当前发言者：${speakerLabel}，角色：${speakerCharacterName}`
    : '当前发言者状态'

  return (
    <section
      className={`multiplayer-speak-bar${isMySpeakTurn ? ' mine' : ''}`}
      aria-label="多人发言权状态"
    >
      <span className="multiplayer-speak-status" role="status" aria-live="polite">
        {isMySpeakTurn ? `✦ ${statusText}` : statusText}
      </span>
      <span className="multiplayer-speak-meta" role="group" aria-label="联机同步与发言者信息">
        <WebSocketStatusPill status={wsStatus} connected={wsConnected} />
        {syncNotice && (
          <span
            title="最近一次重连后的补漏刷新已完成"
            className="multiplayer-speak-chip sync"
          >
            {syncNotice}
          </span>
        )}
        <span title="你当前控制的角色" className="multiplayer-speak-chip character">
          角色 {myCharacterName}
        </span>
        {currentSpeakerUid && (
          <span
            title={speakerStatusTitle}
            className={`multiplayer-speak-chip speaker${speakerStatus.isOnline ? ' online' : ' offline'}`}
          >
            发言 {speakerIdentity} · {speakerStatus.label}
          </span>
        )}
        {takeoverHint && (
          <span
            title={takeoverStatus.label}
            className={`multiplayer-speak-chip takeover${takeoverStatus.canTakeover && wsConnected ? ' ready' : ''}`}
          >
            {takeoverHint}
          </span>
        )}
        {isMySpeakTurn && currentSpeakerUid && (
          <button
            onClick={onSkipTurn}
            title="跳过本轮，不说话也不发起行动"
            disabled={!wsConnected}
            className="multiplayer-speak-action skip"
          >
            跳过本轮 ↷
          </button>
        )}
        {!isMySpeakTurn && currentSpeakerUid && (
          <button
            onClick={onAiTakeover}
            disabled={!canTakeover}
            title={takeoverTitle}
            className={`multiplayer-speak-action takeover${canTakeover ? ' ready' : ''}`}
          >
            ⚙ {takeoverButtonLabel}
          </button>
        )}
        <span className="multiplayer-speak-room-code">房间码 {room.room_code}</span>
      </span>
    </section>
  )
}
