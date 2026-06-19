import { getCombatLifeState } from '../../utils/combat'
import { getBardicInspiration } from '../../utils/bardicInspiration'

function DeathSaveDots({ count = 0, tone }) {
  return (
    <span className="death-save-dots" role="list" aria-label={`已标记 ${count}/3`}>
      {[0, 1, 2].map(index => (
        <span
          key={index}
          className={index < count ? 'filled' : ''}
          role="listitem"
          aria-label={`第 ${index + 1} 格${index < count ? '已标记' : '未标记'}`}
          style={{ '--death-save-tone': tone }}
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
    <section className="combat-death-save-panel" aria-label="死亡豁免状态">
      <div className="combat-death-save-head">
        <span>{title}</span>
        <div className="combat-death-save-track" role="list" aria-label={`死亡豁免进度：成功 ${successes}/3，失败 ${failures}/3`}>
          <span role="listitem" aria-label={`成功 ${successes}/3`}>
            成功 <DeathSaveDots count={successes} tone="#6ae884" />
          </span>
          <span role="listitem" aria-label={`失败 ${failures}/3`}>
            失败 <DeathSaveDots count={failures} tone="#f04838" />
          </span>
        </div>
      </div>
      <button
        type="button"
        className="btn-danger combat-death-save-action"
        onClick={onDeathSave}
        disabled={!canRoll}
        title={disabledReason || '掷 d20 死亡豁免'}
      >
        {syncBlocked ? '同步中' : lifeState === 'stable' ? '无需检定' : '掷死亡豁免'}
      </button>
      {bardic && lifeState === 'dying' && (
        <button
          type="button"
          className={`${useBardicDeathSave ? 'btn-gold' : 'btn-ghost'} combat-death-save-bardic`}
          onClick={onToggleBardicDeathSave}
          disabled={!canToggleBardic}
          aria-pressed={Boolean(useBardicDeathSave)}
          title={disabledReason || `Bardic Inspiration ${bardic.die}`}
          aria-label={`Bardic Inspiration ${useBardicDeathSave ? '开启' : '关闭'}，${bardic.die}`}
        >
          Bardic {useBardicDeathSave ? 'ON' : 'OFF'} · {bardic.die}
        </button>
      )}
      <div className="combat-death-save-hint" role="status" aria-live="polite">{hint}</div>
    </section>
  )
}
