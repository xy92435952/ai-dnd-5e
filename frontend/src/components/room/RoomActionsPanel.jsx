export default function RoomActionsPanel({
  isHost,
  busy,
  canStart,
  slotsAvailable,
  claimedCount,
  memberCount = claimedCount,
  startReadyCount = 0,
  isStartReady = false,
  myMember,
  syncBlocked = false,
  syncBlockedReason = '',
  onCreateChar,
  onToggleStartReady,
  onFillAi,
  onStart,
  onLeave,
}) {
  const controlsDisabled = busy || syncBlocked
  const blockReason = syncBlockedReason || '房间正在重新同步，请恢复连接后再调整准备状态。'
  const allMembersClaimed = memberCount > 0 && claimedCount === memberCount
  const startHint = claimedCount <= 0
    ? '至少需要一位玩家创建并认领角色'
    : !allMembersClaimed
      ? `${claimedCount}/${memberCount} 位玩家已认领，所有真人玩家认领后才能开始`
      : `${startReadyCount}/${memberCount} 位玩家已准备，等待全员确认`

  return (
    <div className="room-actions-panel">
      {syncBlocked && (
        <div
          role="status"
          className="multiplayer-sync-guard"
          style={{ margin: '18px auto 0', maxWidth: 560, textAlign: 'left' }}
        >
          <strong>同步暂停</strong>
          <span>{blockReason}</span>
        </div>
      )}

      {myMember && !myMember.character_id && (
        <div style={{ marginTop: 22, textAlign: 'center' }}>
          <button
            onClick={onCreateChar}
            disabled={controlsDisabled}
            title={syncBlocked ? blockReason : '创建你的英雄'}
            className="btn-gold room-action-button"
            style={{ padding: '12px 32px', fontSize: 14 }}
          >
            ✦ 创建你的英雄 ✦
          </button>
        </div>
      )}

      {myMember?.character_id && (
        <div style={{ marginTop: 14, textAlign: 'center' }}>
          <button
            onClick={() => onToggleStartReady?.(!isStartReady)}
            disabled={controlsDisabled}
            title={syncBlocked ? blockReason : isStartReady ? '取消准备' : '确认准备'}
            className={`${isStartReady ? 'btn-ghost' : 'btn-gold'} room-action-button`}
            style={{ padding: '10px 24px', fontSize: 12, letterSpacing: '.14em' }}
          >
            {isStartReady ? '✓ 已准备，取消' : '✦ 确认准备 ✦'}
          </button>
        </div>
      )}

      {isHost && slotsAvailable > 0 && claimedCount >= 1 && (
        <div style={{ marginTop: 14, textAlign: 'center' }}>
          <button
            onClick={onFillAi}
            disabled={controlsDisabled}
            title={syncBlocked ? blockReason : '召唤 AI 队友补位'}
            className="btn-ghost room-action-button"
            style={{ padding: '10px 22px', fontSize: 12, letterSpacing: '.14em' }}
          >
            {busy ? '✦ 召唤中… ✦' : `✦ 召唤 ${slotsAvailable} 位 AI 队友 ✦`}
          </button>
          <div style={{ fontSize: 10, color: 'var(--parchment-dark)', marginTop: 6, fontFamily: 'var(--font-script)', fontStyle: 'italic' }}>
            根据第一位玩家的职业生成互补角色
          </div>
        </div>
      )}

      {isHost && (
        <div style={{ marginTop: 18, textAlign: 'center' }}>
          <button
            onClick={onStart}
            disabled={!canStart || controlsDisabled}
            title={syncBlocked ? blockReason : canStart ? '开启冒险' : startHint}
            className="btn-gold room-action-button"
            style={{ padding: '12px 32px', fontSize: 14, letterSpacing: '.18em', opacity: canStart && !controlsDisabled ? 1 : .5 }}
          >
            {busy ? '✦ 启动中… ✦' : '✦ 开启冒险 ✦'}
          </button>
          {!syncBlocked && !canStart && (
            <div style={{ fontSize: 11, color: 'var(--parchment-dark)', marginTop: 6, fontFamily: 'var(--font-script)', fontStyle: 'italic' }}>
              {startHint}
            </div>
          )}
        </div>
      )}

      {!isHost && (
        <div style={{ textAlign: 'center', marginTop: 22, opacity: 0.7, fontSize: 13, fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)' }}>
          ~ 等待房主开启冒险 ~
        </div>
      )}

      <div style={{ textAlign: 'center', marginTop: 24 }}>
        <button onClick={onLeave} className="btn-ghost room-action-button danger" style={{ fontSize: 12, color: '#ffaaaa', borderColor: 'var(--blood)' }}>
          ⎋ 离开房间
        </button>
      </div>
    </div>
  )
}
