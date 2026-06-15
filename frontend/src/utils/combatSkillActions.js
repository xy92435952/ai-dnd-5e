import { formatCombatError } from './combatErrors'
import { buildCombatStateChangeSummary } from './combatLog'

function parseDieFaces(die) {
  const text = String(die || 'd6').trim().toLowerCase().replace(/^d/, '')
  const faces = Number.parseInt(text, 10)
  return [6, 8, 10, 12].includes(faces) ? faces : 6
}

export function getCuttingWordsAbilityCheckOption(actor = {}) {
  const cls = String(actor?.char_class || actor?.class || '').trim().toLowerCase()
  if (cls !== 'bard') return null
  if (Number(actor?.level || 1) < 3) return null
  const resources = actor?.class_resources || {}
  if (Number(resources.bardic_inspiration_remaining || 0) <= 0) return null
  const turnState = actor?.turn_state || actor?.turnState || {}
  if (turnState.reaction_used) return null
  const subclassEffects = actor?.derived?.subclass_effects || {}
  const subclass = String(actor?.subclass || '').trim().toLowerCase()
  if (!subclassEffects.cutting_words && !subclassEffects.lore_bard && !subclass.includes('lore')) {
    return null
  }
  const die = String(subclassEffects.inspiration_die || 'd6').trim().toLowerCase()
  return {
    die: /^d(6|8|10|12)$/.test(die) ? die : 'd6',
    faces: parseDieFaces(die),
  }
}

const SPELL_SHORTCUT_NAMES = {
  bless: '祝福',
  heal: '治愈创伤',
  firebolt: '火焰射线',
  sacred_flame: '神圣烈焰',
}

export function createCombatSkillClickHandler({
  getIsProcessing,
  getIsPlayerTurn,
  getUnavailableReason = () => '',
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
  getTurnToken = () => null,
  getCuttingWordsAbilityCheckOption: getCuttingWordsOption = () => null,
  confirmCuttingWordsAbilityCheck = null,
  rollCuttingWordsDie = null,
  showDice = null,
}) {
  async function buildCuttingWordsOptions(actionType, targetId) {
    const option = getCuttingWordsOption?.({ actionType, targetId })
    if (!option) return {}
    const confirmed = confirmCuttingWordsAbilityCheck
      ? await confirmCuttingWordsAbilityCheck({ ...option, actionType, targetId })
      : false
    if (!confirmed) return {}
    const faces = option.faces || parseDieFaces(option.die)
    const rollResult = rollCuttingWordsDie
      ? await rollCuttingWordsDie(faces, { actionType, targetId, die: option.die })
      : null
    const total = Number(rollResult?.total ?? rollResult)
    if (!Number.isFinite(total)) return {}
    showDice?.({ faces, result: total, label: `Cutting Words d${faces}`, count: 1 })
    return { useCuttingWords: true, cuttingWordsRoll: total }
  }

  return async function onSkillClick(skill) {
    const blockedReason = getUnavailableReason(skill)
    if (blockedReason) {
      setError(blockedReason)
      return
    }
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
        case 'firebolt':
        case 'sacred_flame':
          setSpellQuickPick?.(SPELL_SHORTCUT_NAMES[skill.k] || null)
          setSpellModalOpen(true)
          break
        case 'shield':
          setError('护盾术是反应法术，会在被攻击命中时自动提示')
          break
        case 'shove':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          {
            const targetId = getSelectedTarget()
            const cuttingWordsOptions = await buildCuttingWordsOptions('shove', targetId)
            const result = await gameApi.grappleShove(sessionId, 'shove', targetId, 'prone', cuttingWordsOptions)
            if (result?.turn_state) setTurnState?.(result.turn_state)
            if (result?.narration) addLog?.({
              role: 'player',
              content: result.narration,
              log_type: 'combat',
              state_changes: buildCombatStateChangeSummary(result, { targetName: targetId }),
            })
          }
          setCombat(await gameApi.getCombat(sessionId))
          break
        case 'grapple':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          {
            const targetId = getSelectedTarget()
            const cuttingWordsOptions = await buildCuttingWordsOptions('grapple', targetId)
            const result = await gameApi.grappleShove(sessionId, 'grapple', targetId, 'prone', cuttingWordsOptions)
            if (result?.turn_state) setTurnState?.(result.turn_state)
            if (result?.narration) addLog?.({
              role: 'player',
              content: result.narration,
              log_type: 'combat',
              state_changes: buildCombatStateChangeSummary(result, { targetName: targetId }),
            })
          }
          setCombat(await gameApi.getCombat(sessionId))
          break
        case 'off_attack':
          if (!getSelectedTarget()) { setError('请先选择目标'); return }
          {
            const result = await gameApi.combatAction(sessionId, '副手攻击', getSelectedTarget(), false, false, getTurnToken?.())
            if (result?.turn_state) setTurnState?.(result.turn_state)
            if (result?.narration) addLog?.({
              role: 'player',
              content: result.narration,
              log_type: 'combat',
              state_changes: buildCombatStateChangeSummary(result, { targetName: getSelectedTarget() }),
            })
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
        case 'lay_on_hands_cure_poison':
          await handleClassFeature?.('lay_on_hands_cure_poison')
          break
        case 'lay_on_hands_cure_disease':
          await handleClassFeature?.('lay_on_hands_cure_disease')
          break
        case 'bardic_inspiration':
          await handleClassFeature?.('bardic_inspiration', { target_id: getSelectedTarget() })
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
        case 'ki_patient_defense':
          await handleClassFeature?.('ki_patient_defense')
          break
        case 'ki_step_of_the_wind_dash':
          await handleClassFeature?.('ki_step_of_the_wind_dash')
          break
        case 'ki_step_of_the_wind_disengage':
          await handleClassFeature?.('ki_step_of_the_wind_disengage')
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
      setError(formatCombatError(e))
    }
  }
}
