import React from 'react'

export default function CombatHudControls({
  isProcessing,
  isPlayerTurn,
  moveMode,
  isRanged,
  onEndTurn,
  onToggleMove,
  onToggleRanged,
  onOpenCharacter,
  onReturnAdventure,
  onForceEndCombat,
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <button
        className="end-turn-mega"
        data-testid="combat-end-turn"
        onClick={onEndTurn}
        disabled={isProcessing || !isPlayerTurn}
      >☰ 结束回合</button>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
        <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
          data-testid="combat-move-toggle"
          onClick={onToggleMove}
          disabled={isProcessing || !isPlayerTurn}>
          {moveMode ? '✓ 移动' : '► 移动'}
        </button>
        <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
          onClick={onToggleRanged}
          disabled={isProcessing || !isPlayerTurn}>
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
    </div>
  )
}
