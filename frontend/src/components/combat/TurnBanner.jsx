import { buildCombatTurnCoach } from '../../utils/combatTurnCoach'

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

  return (
    <div className="turn-banner">
      <div className="turn-banner-main">
        <span className="round-tag">R {roundNumber || 1}</span>
        <span className="turn-banner-kicker">轮到</span>
        <span className="active-name">{currentTurnName || '—'}</span>
        {combatOver && (
          <span className={`combat-result ${combatOver === 'victory' ? 'victory' : 'defeat'}`}>
            · {combatOver === 'victory' ? '胜利' : '全灭'} ·
          </span>
        )}
        <span className="turn-banner-spacer" />
        <button
          className={`turn-threat-toggle ${showThreat ? 'active' : ''}`}
          onClick={onToggleThreat}
          title="显示/隐藏敌人攻击范围"
        >
          <span className="turn-threat-icon" aria-hidden="true">!</span>
          <span>威胁区</span>
        </button>
      </div>

      <div className={`turn-coach ${coach.tone}`}>
        <strong className="turn-coach-label">{coach.label}</strong>
        <span className="turn-coach-detail">{coach.detail}</span>
      </div>
    </div>
  )
}
