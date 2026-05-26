import Sprite from '../Sprite'
import { getCombatLifeState, getSpriteKind, isCombatEntityDead } from '../../utils/combat'

export default function IsoUnit({ ent, entId, playerId, isCurTurn, isTarget, isHelpTarget = false }) {
  const lifeState = getCombatLifeState(ent)
  const dead = isCombatEntityDead(ent)
  return (
    <div
      className={`iso-unit ${ent.is_enemy ? 'enemy' : (entId === playerId ? 'player' : 'ally')} ${isCurTurn ? 'active' : ''} ${isHelpTarget ? 'help-target' : ''} ${(ent.hp_current / (ent.hp_max || 1)) < .34 ? 'low' : ''} life-${lifeState}`}
      style={{
        '--c-light': ent.is_enemy ? '#f04848' : (entId === playerId ? '#6ae884' : '#7fc8f8'),
        '--c-dark': ent.is_enemy ? '#3a0a0a' : (entId === playerId ? '#1a4a28' : '#143a5e'),
        '--c-glow': ent.is_enemy ? '#f04848' : (entId === playerId ? '#6ae884' : '#5fb8f8'),
      }}
    >
      <div className="base" />
      <div className="sprite-wrap">
        <Sprite kind={getSpriteKind(ent)} size={44} dead={dead} dim={lifeState === 'dying' || lifeState === 'stable'} />
      </div>
      <div className="micro-hp">
        <div
          className="fill"
          style={{ width: `${Math.max(0, Math.min(100, (ent.hp_current / (ent.hp_max || 1)) * 100))}%` }}
        />
      </div>
      {isTarget && <div className="target-ring" />}
      {isHelpTarget && <div className="target-ring help-ring" />}
    </div>
  )
}
