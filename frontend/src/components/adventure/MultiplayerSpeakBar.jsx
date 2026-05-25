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

export default function MultiplayerSpeakBar({
  room,
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
  const canTakeover = takeoverStatus.canTakeover

  return (
    <div style={{
      background: isMySpeakTurn
        ? 'linear-gradient(90deg, rgba(74,138,74,0.4), rgba(74,138,74,0.15))'
        : 'linear-gradient(90deg, rgba(58,122,170,0.3), rgba(58,122,170,0.1))',
      borderBottom: '1px solid var(--amber)',
      padding: '5px 16px', color: 'var(--amber)',
      fontSize: 12, fontWeight: 'bold',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      zIndex: 5,
    }}>
      <span>{isMySpeakTurn ? `✦ ${statusText}` : statusText}</span>
      <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        {isMySpeakTurn && currentSpeakerUid && (
          <button onClick={onSkipTurn}
            title="跳过本轮，不说话也不发起行动"
            style={{ padding: '3px 10px', fontSize: 11, background: 'transparent', color: 'var(--amber)', border: '1px solid var(--amber)', borderRadius: 3, cursor: 'pointer' }}>
            跳过本轮 ↷
          </button>
        )}
        {!isMySpeakTurn && currentSpeakerUid && (
          <button
            onClick={onAiTakeover}
            disabled={!canTakeover}
            title={takeoverStatus.label || (canTakeover ? '该玩家离线，可让 AI 据其人设代演一句' : '当前发言者仍在线，暂不能代演')}
            style={{
              padding: '3px 10px', fontSize: 11, background: 'transparent',
              color: canTakeover ? 'var(--arcane-light)' : 'var(--text-dim)',
              border: `1px solid ${canTakeover ? 'var(--arcane-light)' : 'var(--wood-light)'}`,
              borderRadius: 3, cursor: canTakeover ? 'pointer' : 'not-allowed',
              opacity: canTakeover ? 1 : 0.65,
            }}>
            ⚙ {canTakeover ? 'AI 代演' : (takeoverStatus.label || `玩家${speakerStatus.label}`)}
          </button>
        )}
        <span style={{ fontSize: 11, opacity: 0.8 }}>房间码 {room.room_code}</span>
      </span>
    </div>
  )
}
