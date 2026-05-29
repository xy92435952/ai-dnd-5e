import React from 'react'

function getTurnControlReason({ isProcessing, isPlayerTurn, syncBlocked }) {
  if (syncBlocked) return '等待战斗同步恢复'
  if (isProcessing) return '正在结算上一项动作'
  if (!isPlayerTurn) return '等待你的回合'
  return ''
}

export default function CombatHudControls({
  isProcessing,
  isPlayerTurn,
  syncBlocked = false,
  moveMode,
  isRanged,
  onEndTurn,
  onToggleMove,
  onToggleRanged,
  onOpenCharacter,
  onReturnAdventure,
  onForceEndCombat,
}) {
  const disabledReason = getTurnControlReason({ isProcessing, isPlayerTurn, syncBlocked })
  const actionDisabled = Boolean(disabledReason)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <button
        className="end-turn-mega"
        onClick={onEndTurn}
        disabled={actionDisabled}
        title={disabledReason || '结束当前回合'}
      >{syncBlocked ? '☰ 同步中' : '☰ 结束回合'}</button>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
        <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
          onClick={onToggleMove}
          disabled={actionDisabled}
          title={disabledReason || '切换移动模式'}>
          {moveMode ? '✓ 移动' : '► 移动'}
        </button>
        <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
          onClick={onToggleRanged}
          disabled={actionDisabled}
          title={disabledReason || '切换远程攻击'}>
          {isRanged ? '✓ 远程' : '⊙ 远程'}
        </button>
        <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
          onClick={onOpenCharacter}>
          角色卡
        </button>
        <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
          onClick={onReturnAdventure}>
          ⏎ 返回
        </button>
        <button className="btn-danger" style={{ fontSize: 9, padding: '5px 8px' }}
          onClick={onForceEndCombat}>
          终止
        </button>
      </div>
      {disabledReason && (
        <div style={{ color: 'var(--parchment-dark)', fontSize: 10 }}>
          {disabledReason}
        </div>
      )}
    </div>
  )
}
