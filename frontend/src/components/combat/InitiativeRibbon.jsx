import { formatTacticalRole, getTacticalRoleHint } from '../../utils/combatTacticalContext'
import { buildConditionSummaries } from '../../utils/conditionRules'

export default function InitiativeRibbon({ initiativeChips = [], onSelectTarget = () => {} }) {
  const activeIndex = initiativeChips.findIndex(chip => chip.isCur)
  const nextIndex = getNextLivingIndex(initiativeChips, activeIndex)

  return (
    <div className="init-ribbon" aria-label="Initiative order">
      {initiativeChips.map(({ ent, t, pct, isCur, dead, low, lifeState }, index) => {
        const name = ent?.name || t.name || '?'
        const isNext = index === nextIndex && !isCur
        const sideLabel = t.is_enemy ? 'FOE' : 'ALLY'
        const turnLabel = isCur ? 'NOW' : isNext ? 'NEXT' : sideLabel
        const conditions = buildConditionSummaries(ent?.conditions || [], ent?.condition_durations || {})
        const tacticalRole = t.is_enemy ? ent?.tactical_role || t.tactical_role : ''
        const roleLabel = tacticalRole ? formatTacticalRole(tacticalRole) : ''
        const roleHint = getTacticalRoleHint(tacticalRole)
        const roleTitle = roleLabel ? `战术定位：${roleLabel}。${roleHint || '观察其行动模式来判断优先级。'}` : ''
        const ariaRole = roleLabel ? `, tactical role ${roleLabel}` : ''

        return (
          <button
            key={t.character_id}
            type="button"
            className={`unit-chip ${t.is_enemy ? 'enemy' : ''} ${isCur ? 'active' : ''} ${isNext ? 'next' : ''} ${dead ? 'dead' : ''} ${low ? 'low' : ''} life-${lifeState || 'alive'}`}
            onClick={() => !dead && onSelectTarget(t.character_id)}
            disabled={dead}
            aria-label={`${name}, initiative ${t.initiative ?? '?'}, ${isCur ? 'current turn' : isNext ? 'next turn' : sideLabel.toLowerCase()}${ariaRole}`}
          >
            <div className="init-no">{t.initiative ?? '?'}</div>
            <div className="turn-order-meta">
              <span className={`turn-order-badge ${isCur ? 'now' : isNext ? 'next' : ''}`}>{turnLabel}</span>
              {roleLabel && <span className="turn-order-role" title={roleTitle}>{roleLabel}</span>}
            </div>
            <div className="avatar">
              {(name || '?').slice(0, 1)}{dead && 'x'}
              {low && !dead && <span className="avatar-crack" />}
            </div>
            <div className="unit-name">{name.slice(0, 4)}</div>
            <div className="hp-tick"><div className="fill" style={{ width: `${pct}%` }} /></div>
            {conditions.length > 0 && (
              <div
                className="condition-dots"
                aria-label={`${name} conditions: ${conditions.map(condition => condition.label).join(', ')}`}
              >
                {conditions.slice(0, 3).map((condition, conditionIndex) => (
                  <span
                    key={`${condition.key}-${conditionIndex}`}
                    className={condition.tone || ''}
                    title={condition.title}
                  >
                    {conditionMarker(condition)}
                  </span>
                ))}
              </div>
            )}
          </button>
        )
      })}
      <div style={{ flex: 1 }} />
    </div>
  )
}

function getNextLivingIndex(chips, activeIndex) {
  if (!chips.length || activeIndex < 0) return -1
  for (let offset = 1; offset <= chips.length; offset += 1) {
    const index = (activeIndex + offset) % chips.length
    if (!chips[index]?.dead) return index
  }
  return -1
}

function conditionMarker(condition = {}) {
  return String(condition.label || condition.key || '!').slice(0, 1) || '!'
}
