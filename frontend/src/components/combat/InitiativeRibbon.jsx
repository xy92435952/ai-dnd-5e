import { formatTacticalRole, getTacticalRoleHint } from '../../utils/combatTacticalContext'
import { buildConditionSummaries } from '../../utils/conditionRules'

export default function InitiativeRibbon({ initiativeChips = [], onSelectTarget = () => {} }) {
  const activeIndex = initiativeChips.findIndex(chip => chip.isCur)
  const nextIndex = getNextLivingIndex(initiativeChips, activeIndex)

  return (
    <section className="init-ribbon" aria-label="先攻顺序">
      <div className="init-ribbon-track" role="list" aria-label="行动顺序">
        {initiativeChips.map(({ ent, t, pct, isCur, dead, low, lifeState }, index) => {
          const name = ent?.name || t.name || '?'
          const isNext = index === nextIndex && !isCur
          const sideLabel = t.is_enemy ? '敌方' : '友方'
          const turnLabel = isCur ? '当前' : isNext ? '下个' : sideLabel
          const conditions = buildConditionSummaries(ent?.conditions || [], ent?.condition_durations || {})
          const tacticalRole = t.is_enemy ? ent?.tactical_role || t.tactical_role : ''
          const roleLabel = tacticalRole ? formatTacticalRole(tacticalRole) : ''
          const roleHint = getTacticalRoleHint(tacticalRole)
          const roleTitle = roleLabel ? `战术定位：${roleLabel}。${roleHint || '观察其行动模式来判断优先级。'}` : ''
          const turnStateLabel = isCur ? '当前回合' : isNext ? '下一位行动' : sideLabel
          const deadLabel = dead ? '，已倒下' : ''
          const lowLabel = low && !dead ? '，生命危急' : ''
          const roleAria = roleLabel ? `，战术定位 ${roleLabel}` : ''
          const conditionAria = conditions.length ? `，状态 ${conditions.map(condition => condition.label).join('、')}` : ''

          return (
            <div
              key={t.character_id}
              className="init-ribbon-item"
              role="listitem"
              aria-label={`${name} 行动顺位`}
            >
              <button
                type="button"
                className={`unit-chip ${t.is_enemy ? 'enemy' : ''} ${isCur ? 'active' : ''} ${isNext ? 'next' : ''} ${dead ? 'dead' : ''} ${low ? 'low' : ''} life-${lifeState || 'alive'}`}
                onClick={() => !dead && onSelectTarget(t.character_id)}
                disabled={dead}
                aria-current={isCur ? 'true' : undefined}
                aria-label={`${name}，先攻 ${t.initiative ?? '?'}，${turnStateLabel}${roleAria}${conditionAria}${lowLabel}${deadLabel}`}
              >
                <div className="init-no" aria-label={`先攻值 ${t.initiative ?? '?'}`}>{t.initiative ?? '?'}</div>
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
                    role="list"
                    aria-label={`${name} 状态：${conditions.map(condition => condition.label).join('、')}`}
                  >
                    {conditions.slice(0, 3).map((condition, conditionIndex) => (
                      <span
                        key={`${condition.key}-${conditionIndex}`}
                        className={condition.tone || ''}
                        role="listitem"
                        aria-label={condition.title}
                        title={condition.title}
                      >
                        {conditionMarker(condition)}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            </div>
          )
        })}
        <div className="init-ribbon-spacer" aria-hidden="true" />
      </div>
    </section>
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
