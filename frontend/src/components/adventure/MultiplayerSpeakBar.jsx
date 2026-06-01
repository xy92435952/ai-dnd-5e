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
  const myMember = (room.members || []).find(member => member.user_id === myUserId)
  const myCharacterName = myMember?.character_name || player?.name || (myMember?.character_id ? '已绑定角色' : '未绑定角色')
  const speakerLabel = currentSpeakerName || '等待同步'

  return (
    <div style={{
      background: isMySpeakTurn
        ? 'linear-gradient(90deg, rgba(74,138,74,0.4), rgba(74,138,74,0.15))'
        : 'linear-gradient(90deg, rgba(58,122,170,0.3), rgba(58,122,170,0.1))',
      borderBottom: '1px solid var(--amber)',
      padding: '5px 16px', color: 'var(--amber)',
      fontSize: 12, fontWeight: 'bold',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      gap: 12,
      zIndex: 5,
    }}>
      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {isMySpeakTurn ? `✦ ${statusText}` : statusText}
      </span>
      <span style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
        <WebSocketStatusPill status={wsStatus} connected={wsConnected} />
        {syncNotice && (
          <span title="最近一次重连后的补漏刷新已完成" style={{
            padding: '2px 7px',
            border: '1px solid rgba(127,232,248,.5)',
            color: 'var(--arcane-light)',
            borderRadius: 3,
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            whiteSpace: 'nowrap',
          }}>
            {syncNotice}
          </span>
        )}
        <span title="你当前控制的角色" style={{
          padding: '2px 7px',
          border: '1px solid rgba(240,208,96,.45)',
          color: 'var(--parchment)',
          borderRadius: 3,
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
          whiteSpace: 'nowrap',
        }}>
          角色 {myCharacterName}
        </span>
        {currentSpeakerUid && (
          <span title="当前发言者状态" style={{
            padding: '2px 7px',
            border: `1px solid ${speakerStatus.isOnline ? 'var(--emerald-light)' : 'var(--blood)'}`,
            color: speakerStatus.isOnline ? 'var(--emerald-light)' : '#ffaaaa',
            borderRadius: 3,
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            whiteSpace: 'nowrap',
          }}>
            发言 {speakerLabel} · {speakerStatus.label}
          </span>
        )}
        {isMySpeakTurn && currentSpeakerUid && (
          <button onClick={onSkipTurn}
            title="跳过本轮，不说话也不发起行动"
            disabled={!wsConnected}
            style={{
              padding: '3px 10px', fontSize: 11, background: 'transparent',
              color: wsConnected ? 'var(--amber)' : 'var(--text-dim)',
              border: `1px solid ${wsConnected ? 'var(--amber)' : 'var(--wood-light)'}`,
              borderRadius: 3, cursor: wsConnected ? 'pointer' : 'not-allowed',
              opacity: wsConnected ? 1 : 0.65,
            }}>
            跳过本轮 ↷
          </button>
        )}
        {!isMySpeakTurn && currentSpeakerUid && (
          <button
            onClick={onAiTakeover}
            disabled={!canTakeover}
            title={takeoverTitle}
            style={{
              padding: '3px 10px', fontSize: 11, background: 'transparent',
              color: canTakeover ? 'var(--arcane-light)' : 'var(--text-dim)',
              border: `1px solid ${canTakeover ? 'var(--arcane-light)' : 'var(--wood-light)'}`,
              borderRadius: 3, cursor: canTakeover ? 'pointer' : 'not-allowed',
              opacity: canTakeover ? 1 : 0.65,
            }}>
            ⚙ {takeoverButtonLabel}
          </button>
        )}
        <span style={{ fontSize: 11, opacity: 0.8 }}>房间码 {room.room_code}</span>
      </span>
    </div>
  )
}
