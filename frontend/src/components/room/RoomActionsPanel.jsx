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
  onCreateChar,
  onToggleStartReady,
  onFillAi,
  onStart,
  onLeave,
}) {
  const allMembersClaimed = memberCount > 0 && claimedCount === memberCount
  const startHint = claimedCount <= 0
    ? '至少需要一位玩家创建并认领角色'
    : !allMembersClaimed
      ? `${claimedCount}/${memberCount} 位玩家已认领，所有真人玩家认领后才能开始`
      : `${startReadyCount}/${memberCount} 位玩家已准备，等待全员确认`

  return (
    <>
      {myMember && !myMember.character_id && (
        <div style={{ marginTop: 22, textAlign: 'center' }}>
          <button onClick={onCreateChar} disabled={busy} className="btn-gold" style={{ padding: '12px 32px', fontSize: 14 }}>
            ✦ 创建你的英雄 ✦
          </button>
        </div>
      )}

      {myMember?.character_id && (
        <div style={{ marginTop: 14, textAlign: 'center' }}>
          <button
            onClick={() => onToggleStartReady?.(!isStartReady)}
            disabled={busy}
            className={isStartReady ? 'btn-ghost' : 'btn-gold'}
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
            disabled={busy}
            className="btn-ghost"
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
            disabled={!canStart || busy}
            className="btn-gold"
            style={{ padding: '12px 32px', fontSize: 14, letterSpacing: '.18em', opacity: canStart ? 1 : .5 }}
          >
            {busy ? '✦ 启动中… ✦' : '✦ 开启冒险 ✦'}
          </button>
          {!canStart && (
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
        <button onClick={onLeave} className="btn-ghost" style={{ fontSize: 12, color: '#ffaaaa', borderColor: 'var(--blood)' }}>
          ⎋ 离开房间
        </button>
      </div>
    </>
  )
}
