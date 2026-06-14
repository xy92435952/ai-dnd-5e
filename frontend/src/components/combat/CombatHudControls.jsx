import React from 'react'
import { getAttackWeaponOptions } from '../../utils/combatWeapons'
import { getLuckyPointsRemaining } from '../../utils/lucky'
import { getBardicInspiration } from '../../utils/bardicInspiration'

function getTurnControlReason({ isProcessing, isPlayerTurn, syncBlocked }) {
  if (syncBlocked) return '等待战斗同步恢复'
  if (isProcessing) return '正在结算上一项动作'
  if (!isPlayerTurn) return '等待你的回合'
  return ''
}

function getDelaySpentReason(turnState = {}) {
  if (!turnState) return ''
  if (turnState.action_used) return '已花费本回合动作，不能延迟'
  if (turnState.bonus_action_used) return '已花费本回合附赠动作，不能延迟'
  if (Number(turnState.movement_used || 0) > 0) return '已移动，不能延迟'
  if (Number(turnState.attacks_made || 0) > 0) return '已攻击，不能延迟'
  return ''
}

export default function CombatHudControls({
  isProcessing,
  isPlayerTurn,
  canDelayTurn = isPlayerTurn,
  syncBlocked = false,
  moveMode,
  isRanged,
  selectedWeaponName = '',
  classResources = {},
  useLuckyAttack = false,
  useBardicAttack = false,
  character,
  turnState,
  onEndTurn,
  onDelayTurn = () => {},
  delayTurnOptions = [],
  delayAfterEntityId = '',
  onDelayAfterEntityChange = () => {},
  onToggleMove,
  onToggleRanged,
  onSelectedWeaponChange,
  onToggleLuckyAttack,
  onToggleBardicAttack,
  onOpenCharacter,
  onReturnAdventure,
  onForceEndCombat,
}) {
  const disabledReason = getTurnControlReason({ isProcessing, isPlayerTurn, syncBlocked })
  const delaySpentReason = canDelayTurn ? getDelaySpentReason(turnState) : ''
  const delayDisabledReason = getTurnControlReason({ isProcessing, isPlayerTurn: canDelayTurn, syncBlocked }) || delaySpentReason
  const actionDisabled = Boolean(disabledReason)
  const delayDisabled = Boolean(delayDisabledReason)
  const weaponOptions = getAttackWeaponOptions(character, isRanged)
  const luckyRemaining = getLuckyPointsRemaining(classResources)
  const canToggleLuckyAttack = luckyRemaining > 0 && !actionDisabled && typeof onToggleLuckyAttack === 'function'
  const bardic = getBardicInspiration(classResources)
  const canToggleBardicAttack = Boolean(bardic) && !actionDisabled && typeof onToggleBardicAttack === 'function'
  const hasDelayTargets = delayTurnOptions.length > 0
  const delayTitle = hasDelayTargets
    ? '按所选位置延迟当前回合'
    : '将当前回合延迟到本轮末尾'
  const statusNotice = disabledReason || delaySpentReason

  return (
    <div className="combat-turn-controls">
      <button
        className="end-turn-mega"
        onClick={onEndTurn}
        disabled={actionDisabled}
        title={disabledReason || '结束当前回合'}
      >{syncBlocked ? '☰ 同步中' : '☰ 结束回合'}</button>

      <div className="combat-turn-action-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
        <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}
          onClick={() => onDelayTurn(delayAfterEntityId || null)}
          disabled={delayDisabled}
          title={delayDisabledReason || delayTitle}>
          延迟
        </button>
        {hasDelayTargets && (
          <select
            aria-label="延迟位置"
            value={delayAfterEntityId || ''}
            onChange={(event) => onDelayAfterEntityChange?.(event.target.value)}
            disabled={delayDisabled}
            title={delayDisabledReason || '选择延迟到哪个战斗者之后'}
            style={{
              background: 'rgba(10,6,2,0.65)',
              border: '1px solid var(--wood-light)',
              color: 'var(--parchment)',
              borderRadius: 4,
              fontSize: 10,
              padding: '5px 8px',
              minWidth: 0,
            }}
          >
            <option value="">本轮末尾</option>
            {delayTurnOptions.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
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
        {luckyRemaining > 0 && (
          <button
            className={useLuckyAttack ? 'btn-gold' : 'btn-ghost'}
            style={{ fontSize: 10, padding: '5px 8px' }}
            onClick={onToggleLuckyAttack}
            disabled={!canToggleLuckyAttack}
            aria-pressed={Boolean(useLuckyAttack)}
            title={disabledReason || `Lucky points remaining: ${luckyRemaining}`}
          >
            Lucky {useLuckyAttack ? 'ON' : 'OFF'} · {luckyRemaining}
          </button>
        )}
        {bardic && (
          <button
            className={useBardicAttack ? 'btn-gold' : 'btn-ghost'}
            style={{ fontSize: 10, padding: '5px 8px' }}
            onClick={onToggleBardicAttack}
            disabled={!canToggleBardicAttack}
            aria-pressed={Boolean(useBardicAttack)}
            title={disabledReason || `Bardic Inspiration ${bardic.die}`}
          >
            Bardic {useBardicAttack ? 'ON' : 'OFF'} · {bardic.die}
          </button>
        )}
        <select
          aria-label="攻击武器"
          value={weaponOptions.some(weapon => weapon.name === selectedWeaponName) ? selectedWeaponName : ''}
          onChange={(event) => onSelectedWeaponChange?.(event.target.value)}
          disabled={actionDisabled || weaponOptions.length === 0}
          title={disabledReason || '选择本次普通攻击使用的武器'}
          style={{
            gridColumn: '1 / -1',
            background: 'rgba(10,6,2,0.65)',
            border: '1px solid var(--wood-light)',
            color: 'var(--parchment)',
            borderRadius: 4,
            fontSize: 10,
            padding: '5px 8px',
            minWidth: 0,
          }}
        >
          <option value="">{weaponOptions.length ? '自动选择武器' : '无可用武器'}</option>
          {weaponOptions.map(weapon => {
            const suffix = weapon.ammo != null
              ? ` · 弹药 ${weapon.ammo}`
              : weapon.count > 1
                ? ` ×${weapon.count}`
                : ''
            return (
              <option key={weapon.name} value={weapon.name}>
                {weapon.label}{suffix}
              </option>
            )
          })}
        </select>
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
      {statusNotice && (
        <div style={{ color: 'var(--parchment-dark)', fontSize: 10 }}>
          {statusNotice}
        </div>
      )}
    </div>
  )
}
