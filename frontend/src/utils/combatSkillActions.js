const SPELL_SHORTCUT_NAMES = {
  bless: '祝福',
  heal: '治愈创伤',
  shield: '护盾',
  firebolt: '火焰射线',
  sacred_flame: '神圣烈焰',
}

export function createCombatSkillClickHandler({
  getIsProcessing,
  getIsPlayerTurn,
  getSelectedTarget,
  setError,
  handleAttack,
  setSpellModalOpen,
  setSpellQuickPick,
  gameApi,
  sessionId,
  setCombat,
  setTurnState,
  addLog,
  setHelpMode,
  handleDash,
  handleDisengage,
  handleDodge,
  handleHealingPotion,
  handleClassFeature,
}) {
  return async function onSkillClick(skill) {
    if (!skill.available || getIsProcessing() || !getIsPlayerTurn()) return

    try {
      switch (skill.k) {
        case 'atk':
        case 'sneak':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          await handleAttack()
          break
        case 'smite':
          setError('神圣斩击将在命中后自动提示')
          break
        case 'spell':
          setSpellQuickPick?.(null)
          setSpellModalOpen(true)
          break
        case 'bless':
        case 'heal':
        case 'shield':
        case 'firebolt':
        case 'sacred_flame':
          setSpellQuickPick?.(SPELL_SHORTCUT_NAMES[skill.k] || null)
          setSpellModalOpen(true)
          break
        case 'shove':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          {
            const result = await gameApi.grappleShove(sessionId, 'shove', getSelectedTarget(), 'prone')
            if (result?.turn_state) setTurnState?.(result.turn_state)
            if (result?.narration) addLog?.({ role: 'player', content: result.narration, log_type: 'combat' })
          }
          setCombat(await gameApi.getCombat(sessionId))
          break
        case 'grapple':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          {
            const result = await gameApi.grappleShove(sessionId, 'grapple', getSelectedTarget(), 'prone')
            if (result?.turn_state) setTurnState?.(result.turn_state)
            if (result?.narration) addLog?.({ role: 'player', content: result.narration, log_type: 'combat' })
          }
          setCombat(await gameApi.getCombat(sessionId))
          break
        case 'off_attack':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          {
            const result = await gameApi.combatAction(sessionId, '副手攻击', getSelectedTarget(), false)
            if (result?.turn_state) setTurnState?.(result.turn_state)
            if (result?.narration) addLog?.({ role: 'player', content: result.narration, log_type: 'combat' })
          }
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
        case 'cunning_action_dash':
          await handleClassFeature?.('cunning_action_dash')
          break
        case 'cunning_action_disengage':
          await handleClassFeature?.('cunning_action_disengage')
          break
        case 'cunning_action_hide':
          await handleClassFeature?.('cunning_action_hide')
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
          await handleHealingPotion?.()
          break
        default:
          break
      }
    } catch (e) {
      setError(e.message)
    }
  }
}
