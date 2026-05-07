export function createCombatSkillClickHandler({
  getIsProcessing,
  getIsPlayerTurn,
  getSelectedTarget,
  setError,
  handleAttack,
  setSpellModalOpen,
  gameApi,
  sessionId,
  setCombat,
  setHelpMode,
  handleDash,
  handleDisengage,
  handleDodge,
  handleClassFeature,
}) {
  return async function onSkillClick(skill) {
    if (!skill.available || getIsProcessing() || !getIsPlayerTurn()) return

    try {
      switch (skill.k) {
        case 'atk':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          await handleAttack()
          break
        case 'smite':
          setError('神圣斩击将在命中后自动提示')
          break
        case 'spell':
        case 'bless':
        case 'heal':
        case 'shield':
        case 'firebolt':
        case 'sacred_flame':
          setSpellModalOpen(true)
          break
        case 'shove':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          await gameApi.combatAction(sessionId, '推撞', getSelectedTarget(), false)
          setCombat(await gameApi.getCombat(sessionId))
          break
        case 'help':
          setHelpMode(true)
          break
        case 'dash':
          await handleDash?.()
          break
        case 'disg':
          await handleDisengage?.()
          break
        case 'dodge':
          await handleDodge?.()
          break
        case 'lay':
          await handleClassFeature?.('lay_on_hands')
          break
        case 'second_wind':
          await handleClassFeature?.('second_wind')
          break
        case 'action_surge':
          await handleClassFeature?.('action_surge')
          break
        case 'rage':
          await handleClassFeature?.('rage')
          break
        case 'cunning_action':
          await handleClassFeature?.('cunning_action_dash')
          break
        case 'portent':
          await handleClassFeature?.('portent')
          break
        case 'ki_flurry':
          await handleClassFeature?.('ki_flurry')
          break
        case 'divine_sense':
          await handleClassFeature?.('divine_sense')
          break
        case 'pot':
        case 'pot_heal':
          await gameApi.combatAction(sessionId, '饮用治疗药剂', null, false)
          setCombat(await gameApi.getCombat(sessionId))
          break
        default:
          break
      }
    } catch (e) {
      setError(e.message)
    }
  }
}
