import { buildCombatTurnCoach } from '../../utils/combatTurnCoach'
import { buildCombatActionCoach } from '../../utils/combatActionCoach'

export default function TurnBanner({
  roundNumber,
  currentTurnName,
  currentTurnEntry,
  currentTurnEntity,
  controlledCharacter,
  combatOver,
  isPlayerTurn,
  isProcessing,
  syncBlocked,
  room,
  controllerName,
  turnState,
  skillBar,
  selectedTarget,
  selectedTargetEntity,
  prediction,
  moveMode,
  helpMode,
  isRanged,
  selectedWeaponName,
  nextTurnName = '',
  nextTurnTone = 'ally',
  showThreat,
  onToggleThreat,
}) {
  const coach = buildCombatTurnCoach({
    currentTurnEntry,
    currentTurnEntity,
    controlledCharacter,
    isPlayerTurn,
    isProcessing,
    syncBlocked,
    room,
    controllerName,
  })
  const actionCoach = buildCombatActionCoach({
    isPlayerTurn,
    isProcessing,
    syncBlocked,
    turnState,
    skillBar,
    selectedTarget,
    selectedTargetEntity,
    prediction,
    moveMode,
    helpMode,
    isRanged,
    selectedWeaponName,
  })

  return (
    <section className="turn-banner" aria-label="当前回合状态">
      <div className="turn-banner-main">
        <span className="round-tag">R {roundNumber || 1}</span>
        <span className="turn-banner-kicker">轮到</span>
        <span className="active-name" aria-label={`当前行动者 ${currentTurnName || '未知'}`}>{currentTurnName || '—'}</span>
        {combatOver && (
          <span className={`combat-result ${combatOver === 'victory' ? 'victory' : 'defeat'}`} role="status">
            · {combatOver === 'victory' ? '胜利' : '全灭'} ·
          </span>
        )}
        {!combatOver && nextTurnName && (
          <span
          className={`next-turn-chip ${nextTurnTone === 'enemy' ? 'enemy' : 'ally'}`}
          aria-label={`下一位行动 ${nextTurnName}`}
          title={`下一位行动：${nextTurnName}`}
          role="status"
        >
          <span>下个</span>
          <b>{nextTurnName}</b>
          </span>
        )}
        <span className="turn-banner-spacer" />
        <button
          className={`turn-threat-toggle ${showThreat ? 'active' : ''}`}
          onClick={onToggleThreat}
          title="显示/隐藏敌人攻击范围"
          aria-pressed={showThreat}
          aria-label="切换敌人威胁区显示"
        >
          <span className="turn-threat-icon" aria-hidden="true">!</span>
          <span>威胁区</span>
        </button>
      </div>

      <div className={`turn-coach ${coach.tone}`} role="status" aria-live="polite" aria-label="回合状态提示">
        <strong className="turn-coach-label">{coach.label}</strong>
        <span className="turn-coach-detail">{coach.detail}</span>
      </div>

      {actionCoach.visible && (
        <div className="turn-action-coach" role="list" aria-label="回合行动提示">
          {actionCoach.items.map(item => (
            <span
              key={item.key}
              className={`turn-action-step ${item.key} ${item.tone || ''}`}
              role="listitem"
              aria-label={`${item.label}：${item.value}`}
            >
              <b>{item.label}</b>
              <em title={item.value}>{item.value}</em>
            </span>
          ))}
        </div>
      )}
    </section>
  )
}
