import { formatConditionLabel } from './conditionRules'

export function formatDelayedTurnLog(delayed = {}) {
  const actor = delayed.actor_name || delayed.actor_id || '\u5f53\u524d\u89d2\u8272'
  const afterTarget = delayed.after_entity_name || delayed.after_entity_id
  if (afterTarget) {
    return `${actor} \u5ef6\u8fdf\u884c\u52a8\uff0c\u5c06\u56de\u5408\u79fb\u5230 ${afterTarget} \u4e4b\u540e\u3002`
  }
  return `${actor} \u5ef6\u8fdf\u884c\u52a8\uff0c\u5c06\u56de\u5408\u79fb\u5230\u672c\u8f6e\u672b\u5c3e\u3002`
}

export function formatReadyActionExpiryLog(expiry = {}) {
  const actor = expiry.actor_name || expiry.actor || '\u76ee\u6807'
  const target = expiry.target_name || expiry.target || '\u76ee\u6807'
  const actionType = expiry.action_type || expiry.actionType
  const conditionText = expiry.condition_text || expiry.conditionText
  const actionText = actionType === 'spell'
    ? `\u51c6\u5907\u6cd5\u672f ${expiry.spell_name || expiry.spellName || '\u6cd5\u672f'}`
    : actionType === 'move'
      ? '\u51c6\u5907\u79fb\u52a8'
      : '\u51c6\u5907\u653b\u51fb'
  if (conditionText) {
    return `${actor} \u7684${actionText}\u6761\u4ef6\u300c${conditionText}\u300d\u672a\u89e6\u53d1\uff0c\u5230\u4e0b\u4e2a\u56de\u5408\u5f00\u59cb\u65f6\u5931\u6548\u3002`
  }
  return `${actor} \u7684${actionText}\u6ca1\u6709\u5728 ${target} \u79fb\u52a8\u65f6\u89e6\u53d1\uff0c\u5230\u4e0b\u4e2a\u56de\u5408\u5f00\u59cb\u65f6\u5931\u6548\u3002`
}

export function formatConditionEndSaveLog(save = {}) {
  const actor = save.actor_name || save.target_state?.target_name || save.actor_id || '\u76ee\u6807'
  const detail = save.save || {}
  const total = detail.total ?? '\u2014'
  const dc = detail.dc ?? '\u2014'
  const spell = save.spell_name || (save.type === 'confusion_end_save' ? '\u6df7\u4e71\u672f' : '\u72b6\u6001')
  const condition = formatConditionLabel(save.condition || (save.type === 'confusion_end_save' ? 'confused' : ''))
  return save.ended
    ? `${actor} \u901a\u8fc7${spell}\u56de\u5408\u7ed3\u675f\u8c41\u514d\uff08${total} vs DC${dc}\uff09\uff0c\u89e3\u9664${condition}\u3002`
    : `${actor} \u672a\u901a\u8fc7${spell}\u56de\u5408\u7ed3\u675f\u8c41\u514d\uff08${total} vs DC${dc}\uff09\uff0c\u4fdd\u7559${condition}\u3002`
}
