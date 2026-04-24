/**
 * CombatLogEntry — 战斗日志中的单条显示。
 *
 * 根据 log.role 分色（player/enemy/companion_X/system），
 * 当 log.dice_result.attack 存在时额外显示一行简明 d20 结果。
 *
 * Props:
 *   log - { role, content, dice_result: {attack?, damage?} }
 */
import { ShieldIcon, SwordIcon, SkullIcon, DiceD20Icon } from '../Icons'

export default function CombatLogEntry({ log }) {
  const isPlayer    = log.role === 'player'
  const isEnemy     = log.role === 'enemy'
  const isCompanion = log.role?.startsWith('companion_')
  const color = isPlayer
    ? 'var(--blue-light)'
    : isEnemy
      ? 'var(--red-light)'
      : isCompanion
        ? 'var(--green-light)'
        : 'var(--text-dim)'

  const atk      = log.dice_result?.attack
  const dmg      = log.dice_result?.damage
  const dmgTotal = dmg ? (typeof dmg === 'object' ? dmg.total : dmg) : null

  return (
    <div style={{
      padding: '6px 8px', marginBottom: 4, borderRadius: 6,
      background: isPlayer
        ? 'rgba(58,122,170,0.08)'
        : isEnemy
          ? 'rgba(196,64,64,0.08)'
          : isCompanion
            ? 'rgba(74,138,74,0.08)'
            : 'transparent',
      borderLeft: `2px solid ${color}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
        <span style={{ flexShrink: 0, marginTop: 2, display: 'flex' }}>
          {isPlayer
            ? <ShieldIcon size={12} color="var(--blue-light)" />
            : isEnemy
              ? <SkullIcon size={12} color="var(--red-light)" />
              : isCompanion
                ? <SwordIcon size={12} color="var(--green-light)" />
                : <DiceD20Icon size={12} color="var(--text-dim)" />}
        </span>
        <p style={{ color, lineHeight: 1.6, fontSize: '0.8rem', fontStyle: 'normal' }}>{log.content}</p>
      </div>
      {atk?.d20 !== undefined && (
        <p style={{
          paddingLeft: 20, marginTop: 2,
          color: 'var(--parchment-dark)', opacity: 0.6, fontSize: '0.7rem',
          fontFamily: 'var(--font-mono, monospace)',
        }}>
          d20({atk.d20})+{atk.attack_bonus}={atk.attack_total} vs AC{atk.target_ac}
          {atk.hit
            ? ` → 命中${dmgTotal ? ` (${dmgTotal}伤害)` : ''}`
            : ' → 未命中'}
          {atk.is_crit ? ' 暴击！' : ''}{atk.is_fumble ? ' 大失手' : ''}
        </p>
      )}
    </div>
  )
}
