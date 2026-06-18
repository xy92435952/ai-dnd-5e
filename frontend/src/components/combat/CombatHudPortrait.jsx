import React from 'react'
import { getEquippedWeaponResourceSummary } from '../../utils/combat'
import { buildConditionImpactTags, buildConditionSummaries } from '../../utils/conditionRules'

export default function CombatHudPortrait({ session, character = null, playerClass, playerSubclass, playerLevel, turnState }) {
  const player = character || session?.player
  const hpMax = Math.max(1, player?.hp_max ?? player?.derived?.hp_max ?? 1)
  const hpCurrent = player?.hp_current ?? 0
  const hpRatio = hpCurrent / hpMax
  const hpSegments = 12
  const hpMeterValue = Math.max(0, Math.min(hpMax, hpCurrent))
  const hpFilledSegments = Math.max(0, Math.min(hpSegments, Math.round((hpMeterValue / hpMax) * hpSegments)))
  const movementMax = turnState?.movement_max ?? 6
  const movementRemaining = Math.max(0, movementMax - (turnState?.movement_used ?? 0))
  const playerName = player?.name || '玩家'
  const classLabel = `${playerClass || '?'} ${playerSubclass ? `· ${playerSubclass} ` : ''}· Lv ${playerLevel ?? '?'}`
  const initiative = player?.derived?.initiative ?? 0
  const weaponResource = getEquippedWeaponResourceSummary(player)
  const conditionSummaries = buildConditionSummaries(player?.conditions || [], player?.condition_durations || {})
  const conditionImpactTags = buildConditionImpactTags(player?.conditions || [], player?.condition_durations || {})

  return (
    <section className="hud-portrait" aria-label={`当前战斗角色 ${playerName}`}>
      <div className="hud-avatar big" aria-hidden="true">
        {playerName.slice(0, 1)}
        {hpCurrent > 0 && hpRatio <= 0.25 ? <span className="avatar-crack" /> : null}
      </div>
      <div className="stats">
        <div className="name">{playerName}</div>
        <div className="sub">{classLabel}</div>
        <div
          className={`hp-segmented ${hpRatio < .34 ? 'low' : hpRatio < .67 ? 'mid' : ''}`}
          role="meter"
          aria-label={`生命值 ${hpCurrent}/${hpMax}`}
          aria-valuemin={0}
          aria-valuemax={hpMax}
          aria-valuenow={hpMeterValue}
        >
          {Array.from({ length: hpSegments }).map((_, i) => (
            <div key={i} className={`seg ${i >= hpFilledSegments ? 'empty' : ''}`} />
          ))}
        </div>
        <div className="hp-text">
          <span>
            <span className="cur">{hpCurrent}</span> / {hpMax}
            {player?.wild_shape_hp > 0 ? ` WS ${player.wild_shape_hp}` : ''}
            {player?.temporary_hp > 0 ? ` +${player.temporary_hp}` : ''}
          </span>
          <span className="hud-movement">移动 <b>{movementRemaining}/{movementMax}</b></span>
        </div>
        <div className="stat-line" role="list" aria-label="角色战斗数据">
          <span role="listitem">AC <span className="v">{player?.derived?.ac ?? player?.ac ?? 10}</span></span>
          <span role="listitem">先攻 <span className="v">{(initiative >= 0 ? '+' : '') + initiative}</span></span>
          {player?.derived?.spell_save_dc && (
            <span role="listitem">DC <span className="v">{player.derived.spell_save_dc}</span></span>
          )}
        </div>
        {weaponResource && (
          <div className="stat-line hud-resource-line">
            <span
              className="hud-resource"
              title={weaponResource.label}
              aria-label={`武器资源 ${weaponResource.label} ${weaponResource.value}`}
            >
              {weaponResource.label} <span className="v">{weaponResource.value}</span>
            </span>
          </div>
        )}
        {conditionSummaries.length > 0 && (
          <div className="conditions" role="list" aria-label="当前状态规则">
            {conditionSummaries.slice(0, 6).map(condition => (
              <span
                key={condition.key}
                className={`cond-icon ${condition.tone}`}
                title={condition.title}
                role="listitem"
                aria-label={condition.title}
              >
                {condition.label}
                {condition.duration ? <b>{condition.duration}</b> : null}
              </span>
            ))}
          </div>
        )}
        {conditionImpactTags.length > 0 && (
          <div className="condition-impact-tags" role="list" aria-label="当前状态影响">
            {conditionImpactTags.map(tag => (
              <span
                key={tag.key}
                className={tag.tone || ''}
                title={tag.title}
                role="listitem"
                aria-label={tag.title}
              >
                {tag.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
