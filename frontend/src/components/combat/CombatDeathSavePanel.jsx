import { getCombatLifeState } from '../../utils/combat'
import { getBardicInspiration } from '../../utils/bardicInspiration'

function DeathSaveDots({ count = 0, tone }) {
  return (
    <span style={{ display: 'inline-flex', gap: 3 }}>
      {[0, 1, 2].map(index => (
        <span
          key={index}
          style={{
            width: 7,
            height: 7,
            border: `1px solid ${tone}`,
            background: index < count ? tone : 'transparent',
            display: 'inline-block',
          }}
        />
      ))}
    </span>
  )
}

export default function CombatDeathSavePanel({
  character,
  isPlayerTurn,
  isProcessing,
  syncBlocked = false,
  classResources = {},
  useBardicDeathSave = false,
  onToggleBardicDeathSave = null,
  onDeathSave,
}) {
  const lifeState = getCombatLifeState(character)
  if (lifeState !== 'dying' && lifeState !== 'stable') return null

  const saves = character?.death_saves || {}
  const successes = saves.successes || 0
  const failures = saves.failures || 0
  const canRoll = lifeState === 'dying' && isPlayerTurn && !isProcessing && !syncBlocked
  const bardic = getBardicInspiration(classResources || character)
  const canToggleBardic = Boolean(bardic) && canRoll && typeof onToggleBardicDeathSave === 'function'
  const title = lifeState === 'stable' ? '已稳定' : '濒死豁免'
  const disabledReason = lifeState === 'stable'
    ? '角色已稳定'
    : syncBlocked
      ? '等待战斗同步恢复'
      : isProcessing
        ? '正在结算上一项动作'
        : !isPlayerTurn
          ? '等待你的回合'
          : ''
  const hint = lifeState === 'stable'
    ? '角色已稳定，等待治疗或战斗结束。'
    : disabledReason
      ? `${disabledReason}后进行死亡豁免。`
      : '轮到你时进行 d20 死亡豁免。'

  return (
    <div style={{
      padding: '8px',
      border: '1px solid rgba(240,72,56,.38)',
      background: 'rgba(46,8,8,.42)',
      display: 'grid',
      gap: 6,
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 8,
        color: 'var(--red-light)',
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        letterSpacing: '.12em',
        textTransform: 'uppercase',
      }}>
        <span>{title}</span>
        <span style={{ color: 'var(--parchment-dark)', letterSpacing: 0 }}>
          成功 <DeathSaveDots count={successes} tone="#6ae884" /> 失败 <DeathSaveDots count={failures} tone="#f04838" />
        </span>
      </div>
      <button
        type="button"
        className="btn-danger"
        onClick={onDeathSave}
        disabled={!canRoll}
        title={disabledReason || '掷 d20 死亡豁免'}
        style={{ fontSize: 10, padding: '6px 8px' }}
      >
        {syncBlocked ? '同步中' : lifeState === 'stable' ? '无需检定' : '掷死亡豁免'}
      </button>
      {bardic && lifeState === 'dying' && (
        <button
          type="button"
          className={useBardicDeathSave ? 'btn-gold' : 'btn-ghost'}
          onClick={onToggleBardicDeathSave}
          disabled={!canToggleBardic}
          aria-pressed={Boolean(useBardicDeathSave)}
          title={disabledReason || `Bardic Inspiration ${bardic.die}`}
          style={{ fontSize: 10, padding: '5px 8px' }}
        >
          Bardic {useBardicDeathSave ? 'ON' : 'OFF'} · {bardic.die}
        </button>
      )}
      <div style={{ color: 'var(--parchment-dark)', fontSize: 10 }}>{hint}</div>
    </div>
  )
}
