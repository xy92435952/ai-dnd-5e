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
          className="multiplayer-sync-guard room-actions-sync-guard"
        >
          <strong>同步暂停</strong>
          <span>{blockReason}</span>
        </div>
      )}

      {myMember && !myMember.character_id && (
        <div className="room-action-row room-action-row-create">
          <button
            onClick={onCreateChar}
            disabled={controlsDisabled}
            title={syncBlocked ? blockReason : '创建你的英雄'}
            className="btn-gold room-action-button room-action-button-primary"
          >
            ✦ 创建你的英雄 ✦
          </button>
        </div>
      )}

      {myMember?.character_id && (
        <div className="room-action-row room-action-row-ready">
          <button
            onClick={() => onToggleStartReady?.(!isStartReady)}
            disabled={controlsDisabled}
            title={syncBlocked ? blockReason : isStartReady ? '取消准备' : '确认准备'}
            className={`${isStartReady ? 'btn-ghost' : 'btn-gold'} room-action-button room-action-button-ready`}
            data-ready={isStartReady ? 'true' : 'false'}
          >
            {isStartReady ? '✓ 已准备，取消' : '✦ 确认准备 ✦'}
          </button>
        </div>
      )}

      {isHost && slotsAvailable > 0 && claimedCount >= 1 && (
        <div className="room-action-row room-action-row-fill-ai">
          <button
            onClick={onFillAi}
            disabled={controlsDisabled}
            title={syncBlocked ? blockReason : '召唤 AI 队友补位'}
            className="btn-ghost room-action-button room-action-button-secondary"
          >
            {busy ? '✦ 召唤中… ✦' : `✦ 召唤 ${slotsAvailable} 位 AI 队友 ✦`}
          </button>
          <div className="room-action-hint">
            根据第一位玩家的职业生成互补角色
          </div>
        </div>
      )}

      {isHost && (
        <div className="room-action-row room-action-row-start">
          <button
            onClick={onStart}
            disabled={!canStart || controlsDisabled}
            title={syncBlocked ? blockReason : canStart ? '开启冒险' : startHint}
            className="btn-gold room-action-button room-action-button-start"
            data-can-start={canStart && !controlsDisabled ? 'true' : 'false'}
          >
            {busy ? '✦ 启动中… ✦' : '✦ 开启冒险 ✦'}
          </button>
          {!syncBlocked && !canStart && (
            <div className="room-action-hint room-action-start-hint">
              {startHint}
            </div>
          )}
        </div>
      )}

      {!isHost && (
        <div className="room-action-waiting-host">
          ~ 等待房主开启冒险 ~
        </div>
      )}

      <div className="room-action-row room-action-row-leave">
        <button onClick={onLeave} className="btn-ghost room-action-button room-action-button-leave danger">
          ⎋ 离开房间
        </button>
      </div>
    </div>
  )
}
