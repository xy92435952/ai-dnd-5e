/**
 * MultiplayerSpeakBar — Adventure 顶部多人发言权提示条。
 *
 * 只负责展示和把按钮动作交还给页面；AI 代演、WS 消息发送等业务仍在
 * Adventure.jsx 中，避免展示组件知道 API 细节。
 */
export default function MultiplayerSpeakBar({
  room,
  isMySpeakTurn,
  currentSpeakerUid,
  currentSpeakerName,
  onSkipTurn,
  onAiTakeover,
}) {
  if (!room) return null

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
      <span>{isMySpeakTurn ? '✦ 轮到你了 · 说一句你的行动，DM 会回应并自动轮到下一位' : `等待 ${currentSpeakerName || '其他玩家'} 发言…`}</span>
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
            title="若该玩家长时间没动作（≥30 秒无心跳），让 AI 据其人设代演一句"
            style={{ padding: '3px 10px', fontSize: 11, background: 'transparent', color: 'var(--arcane-light)', border: '1px solid var(--arcane-light)', borderRadius: 3, cursor: 'pointer' }}>
            ⚙ 代他出招
          </button>
        )}
        <span style={{ fontSize: 11, opacity: 0.8 }}>房间码 {room.room_code}</span>
      </span>
    </div>
  )
}
