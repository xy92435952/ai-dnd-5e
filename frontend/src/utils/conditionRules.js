const CONDITION_LABELS = {
  blinded: '目盲',
  charmed: '魅惑',
  deafened: '耳聋',
  dodging: '闪避',
  frightened: '恐慌',
  grappled: '被擒抱',
  hidden: '隐藏',
  incapacitated: '失能',
  invisible: '隐形',
  paralyzed: '麻痹',
  petrified: '石化',
  poisoned: '中毒',
  prone: '倒地',
  restrained: '束缚',
  stunned: '震慑',
  unconscious: '失去意识',
  exhaustion: '力竭',
  faerie_fire: '妖火',
  guiding_bolt: '神力打击标记',
  hexed: '诡异诅咒',
  hunters_marked: '猎手印记',
  divine_favor: '天界印记',
  slowed: '迟缓',
  confused: '\u56f0\u60d1',
  commanded: '\u547d\u4ee4',
  marked: '标记',
  burning: '燃烧',
  webbed: '蛛网束缚',
  blessed: '祝福',
  bless: '祝福',
  baned: '灾祸术',
  bane: '灾祸术',
  resistance: '抵抗',
  resistant: '抵抗',
  guided: '引导',
  guidance: '引导',
  fire_resistance: '火焰抗性',
  cold_resistance: '寒冷抗性',
  acid_resistance: '强酸抗性',
  lightning_resistance: '闪电抗性',
  thunder_resistance: '雷鸣抗性',
  rage: '狂暴',
  concentrating: '专注',
}

const CONDITION_ALIASES = {
  倒地: 'prone',
  倒伏: 'prone',
  隐藏: 'hidden',
  隐匿: 'hidden',
  妖火: 'faerie_fire',
  鬼火: 'faerie_fire',
  神力打击标记: 'guiding_bolt',
  引导箭标记: 'guiding_bolt',
  诅咒: 'hexed',
  妖术: 'hexed',
  诡异诅咒: 'hexed',
  hex: 'hexed',
  猎手印记: 'hunters_marked',
  hunters_mark: 'hunters_marked',
  "hunter's_mark": 'hunters_marked',
  天界印记: 'divine_favor',
  divine_favor: 'divine_favor',
  '\u547d\u4ee4': 'commanded',
  '\u547d\u4ee4\u672f': 'commanded',
  command: 'commanded',
  祝福: 'blessed',
  灾祸: 'baned',
  灾祸术: 'baned',
  抵抗: 'resistance',
  抗力: 'resistance',
  神导术: 'guided',
  引导: 'guided',
  困惑: 'confused',
  混乱: 'confused',
}

const CONDITION_RULES = {
  blinded: '无法看见；攻击它的攻击具有优势，它的攻击具有劣势。',
  charmed: '不能攻击魅惑者；魅惑者对它进行社交检定有优势。',
  deafened: '无法听见，且自动失败基于听觉的检定。',
  dodging: '专注于躲避攻击；攻击它的攻击骰具有劣势。',
  frightened: '来源可见时攻击骰和属性检定处于劣势；不能主动靠近来源。',
  grappled: '速度变为 0，直到擒抱结束。',
  hidden: '位置未被可靠掌握；不能被普通单体攻击直接指定。',
  incapacitated: '不能采取动作或反应。',
  invisible: '未被看见；它的攻击有优势，攻击它的攻击有劣势。',
  paralyzed: '失能；近战命中可能变为重击。',
  petrified: '失能并获得伤害抗性；许多豁免或检定自动失败。',
  poisoned: '攻击骰和属性检定处于劣势。',
  prone: '自身攻击处于劣势；近身近战攻击它有优势。',
  restrained: '速度为 0；攻击它有优势；它的攻击和敏捷豁免有劣势。',
  stunned: '失能；攻击它有优势；力量和敏捷豁免自动失败。',
  unconscious: '失能、倒地且无意识；近身命中可能变为重击。',
  exhaustion: '力竭惩罚生效；等级决定严重程度。',
  faerie_fire: '发出微光；攻击它具有优势，且它不能从隐形受益。',
  guiding_bolt: '被神力打击的光辉标记；下一次攻击它的攻击具有优势，触发后移除。',
  baned: '攻击检定和豁免检定额外减 1d4。',
  bane: '攻击检定和豁免检定额外减 1d4。',
  hexed: '受到诡异诅咒；施法者命中它时额外造成 1d6 坏死伤害，被选属性检定劣势。',
  hunters_marked: '被猎手印记标记；施法者武器命中它时额外造成 1d6 伤害，并利于追踪。',
  slowed: '速度和动作选项减少；敏捷豁免可能受罚。',
  confused: '\u884c\u52a8\u53d7\u6df7\u4e71\u5f71\u54cd\uff1b\u56de\u5408\u5185\u53ef\u80fd\u65e0\u6cd5\u884c\u52a8\u3001\u4e71\u8d70\u6216\u968f\u673a\u653b\u51fb\u3002',
  commanded: '\u53d7\u547d\u4ee4\u672f\u5f71\u54cd\uff1b\u4e0b\u4e00\u56de\u5408\u884c\u52a8\u53d7\u9650\uff0c\u67e5\u770b\u65e5\u5fd7\u786e\u8ba4\u5177\u4f53\u547d\u4ee4\u3002',
  marked: '被敌对效果标记；攻击或后续效果可能优先锁定它。',
  burning: '受到持续火焰或高热压力；查看战斗日志确认伤害时机。',
  webbed: '被蛛网或黏性地形束缚，直到挣脱。',
}

const BENEFICIAL_RULES = {
  blessed: '激活期间，攻击和豁免获得额外骰。',
  bless: '激活期间，攻击和豁免获得额外骰。',
  resistance: '激活期间，豁免检定获得额外骰。',
  resistant: '激活期间，豁免检定获得额外骰。',
  guided: '激活期间，能力检定获得额外骰。',
  guidance: '激活期间，能力检定获得额外骰。',
  fire_resistance: '此防护持续期间，火焰伤害降低。',
  cold_resistance: '此防护持续期间，寒冷伤害降低。',
  acid_resistance: '此防护持续期间，强酸伤害降低。',
  lightning_resistance: '此防护持续期间，闪电伤害降低。',
  thunder_resistance: '此防护持续期间，雷鸣伤害降低。',
  rage: '狂暴类防护生效；查看日志确认伤害和动作限制。',
  divine_favor: '武器命中额外造成 1d4 光耀伤害，维持专注。',
  concentrating: '正在维持专注；受到伤害可能触发专注检定。',
}

const CONDITION_IMPACTS = {
  blinded: [
    impact('hit_adv', '受击优势', '攻击此生物具有优势。'),
    impact('attack_disadv', '攻击劣势', '该生物攻击具有劣势。'),
  ],
  charmed: [
    impact('social_adv', '社交优势', '魅惑者对该生物进行社交检定有优势。', 'warning'),
  ],
  deafened: [
    impact('hearing_fail', '听觉失败', '基于听觉的检定会失败或被阻断。', 'warning'),
  ],
  dodging: [
    impact('hit_disadv', '受击劣势', '攻击此生物具有劣势。', 'good'),
  ],
  frightened: [
    impact('attack_disadv', '攻击劣势', '来源可见时，攻击骰和检定处于劣势。'),
    impact('move_block', '移动受限', '不能主动靠近恐惧来源。'),
  ],
  grappled: [
    impact('speed_0', '速度 0', '移动速度降为 0。'),
  ],
  hidden: [
    impact('target_blocked', '不能直指', '普通单体攻击不能直接指定这个隐藏目标。', 'good'),
  ],
  incapacitated: [
    impact('no_actions', '无法行动', '不能采取动作或反应。'),
  ],
  invisible: [
    impact('attack_adv', '攻击优势', '未被看见时，该生物攻击具有优势。', 'good'),
    impact('hit_disadv', '受击劣势', '攻击此生物具有劣势。', 'good'),
  ],
  paralyzed: [
    impact('no_actions', '无法行动', '不能采取动作或反应。'),
    impact('speed_0', '速度 0', '移动速度降为 0。'),
    impact('hit_adv', '受击优势', '攻击此生物具有优势。'),
    impact('crit_risk', '重击风险', '近身命中可能变为重击。'),
    impact('save_fail', '豁免失败', '力量和敏捷豁免自动失败。'),
  ],
  petrified: [
    impact('no_actions', '无法行动', '不能采取动作或反应。'),
    impact('speed_0', '速度 0', '移动速度降为 0。'),
    impact('hit_adv', '受击优势', '攻击此生物具有优势。'),
    impact('save_fail', '豁免失败', '力量和敏捷豁免自动失败。'),
    impact('resist', '抗性', '伤害抗性已生效。', 'good'),
  ],
  poisoned: [
    impact('attack_disadv', '攻击劣势', '攻击骰和属性检定处于劣势。'),
  ],
  prone: [
    impact('attack_disadv', '攻击劣势', '该生物攻击具有劣势。'),
    impact('melee_hit_adv', '近战优势', '近身近战攻击此生物具有优势。'),
  ],
  restrained: [
    impact('speed_0', '速度 0', '移动速度降为 0。'),
    impact('hit_adv', '受击优势', '攻击此生物具有优势。'),
    impact('attack_disadv', '攻击劣势', '该生物攻击具有劣势。'),
    impact('dex_disadv', '敏捷劣势', '敏捷豁免处于劣势。'),
  ],
  stunned: [
    impact('no_actions', '无法行动', '不能采取动作或反应。'),
    impact('speed_0', '速度 0', '移动速度降为 0。'),
    impact('hit_adv', '受击优势', '攻击此生物具有优势。'),
    impact('save_fail', '豁免失败', '力量和敏捷豁免自动失败。'),
  ],
  unconscious: [
    impact('no_actions', '无法行动', '不能采取动作或反应。'),
    impact('speed_0', '速度 0', '移动速度降为 0。'),
    impact('hit_adv', '受击优势', '攻击此生物具有优势。'),
    impact('crit_risk', '重击风险', '近身命中可能变为重击。'),
  ],
  exhaustion: [
    impact('penalty', '惩罚', '力竭等级决定当前惩罚。', 'warning'),
  ],
  faerie_fire: [
    impact('hit_adv', '受击优势', '攻击此生物具有优势。'),
    impact('reveal_invisible', '显形', '此生物不能从隐形受益。'),
  ],
  guiding_bolt: [
    impact('hit_adv', '受击优势', '下一次攻击此生物具有优势；触发后移除。'),
  ],
  blessed: [
    impact('roll_bonus', '攻击/豁免 +d4', '攻击检定和豁免检定额外加 1d4。', 'good'),
  ],
  bless: [
    impact('roll_bonus', '攻击/豁免 +d4', '攻击检定和豁免检定额外加 1d4。', 'good'),
  ],
  baned: [
    impact('roll_penalty', '攻击/豁免 -d4', '攻击检定和豁免检定额外减 1d4。'),
  ],
  bane: [
    impact('roll_penalty', '攻击/豁免 -d4', '攻击检定和豁免检定额外减 1d4。'),
  ],
  hexed: [
    impact('extra_hit_damage', '命中 +1d6', '施法者命中该目标时额外造成 1d6 坏死伤害。'),
    impact('check_disadv', '检定劣势', '被选定的属性检定可能处于劣势。'),
  ],
  hunters_marked: [
    impact('extra_hit_damage', '命中 +1d6', '施法者武器命中该目标时额外造成 1d6 伤害。'),
  ],
  divine_favor: [
    impact('weapon_damage_bonus', '武器 +1d4', '武器命中额外造成 1d4 光耀伤害。', 'good'),
  ],
  slowed: [
    impact('action_limit', '动作受限', '可用动作选项减少。'),
    impact('dex_disadv', '敏捷劣势', '敏捷豁免可能处于劣势。'),
  ],
  confused: [
    impact('random_action', '\u968f\u673a\u884c\u52a8', '\u56de\u5408\u5f00\u59cb\u65f6\u53ef\u80fd\u968f\u673a\u51b3\u5b9a\u884c\u52a8\u7ed3\u679c\u3002'),
    impact('reaction_block', '\u4e0d\u80fd\u53cd\u5e94', '\u6df7\u4e71\u671f\u95f4\u4e0d\u80fd\u91c7\u53d6\u53cd\u5e94\u3002'),
  ],
  commanded: [
    impact('limited_action', '\u884c\u52a8\u53d7\u9650', '\u53d7\u547d\u4ee4\u672f\u5f71\u54cd\uff1b\u4e0b\u4e00\u56de\u5408\u884c\u52a8\u53d7\u9650\uff0c\u67e5\u770b\u65e5\u5fd7\u786e\u8ba4\u5177\u4f53\u547d\u4ee4\u3002'),
  ],
  marked: [
    impact('focus_fire', '集火标记', '该目标被标记，后续压制或追击会优先关注它。', 'warning'),
  ],
  burning: [
    impact('ongoing_damage', '持续伤害', '可能承受持续伤害或环境压力。'),
  ],
  webbed: [
    impact('speed_0', '速度 0', '移动速度降为 0。'),
    impact('hit_adv', '受击优势', '攻击此生物具有优势。'),
    impact('attack_disadv', '攻击劣势', '该生物攻击具有劣势。'),
  ],
}

export function buildConditionSummaries(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return []

  return conditions
    .map(condition => conditionSummary(condition, durations))
    .filter(Boolean)
}

export function buildConditionImpactTags(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return []

  const tagsByKey = new Map()
  for (const condition of conditions) {
    const key = conditionKey(condition)
    if (!key) continue
    const label = conditionImpactSourceLabel(condition, key, durations)
    const impacts = conditionImpacts(key, condition, durations)
    for (const item of impacts) {
      const existing = tagsByKey.get(item.key)
      if (existing) {
        existing.sources.push(label)
        continue
      }
      tagsByKey.set(item.key, {
        ...item,
        sources: [label],
      })
    }
  }

  return Array.from(tagsByKey.values())
    .map(tag => ({
      key: tag.key,
      label: tag.label,
      tone: tag.tone,
      title: `${tag.title} 来源：${tag.sources.join(' / ')}。`,
    }))
    .slice(0, 6)
}

export function getEndOfTurnRepeatSaveConditions(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return []

  return conditions
    .map(condition => {
      const key = conditionKey(condition)
      if (!key) return null
      const metadata = repeatSaveMetadata(key, condition, durations)
      if (!metadata) return null
      const timing = metadata.repeat_save || metadata.repeatSave || 'end_of_turn'
      if (timing !== 'end_of_turn') return null
      const ability = String(metadata.save_ability || metadata.saveAbility || '').trim().toLowerCase()
      const dc = metadata.save_dc ?? metadata.saveDc ?? metadata.dc ?? null
      return {
        key,
        label: conditionLabel(key),
        ability,
        dc,
        requires: metadata.repeat_save_requires || metadata.repeatSaveRequires || metadata.requires || null,
      }
    })
    .filter(Boolean)
}

export function buildConditionActionLockReason(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return ''

  const blockers = collectConditionImpactSources(conditions, durations, 'no_actions')
  if (!blockers.length) return ''
  const shown = blockers.slice(0, 2).join(' / ')
  const more = blockers.length > 2 ? ` 等 ${blockers.length} 项状态` : ''
  return `${shown}${more} · 不能采取动作或反应`
}

export function buildConditionSpeedLockReason(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return ''

  const blockers = collectConditionImpactSources(conditions, durations, 'speed_0')
  if (!blockers.length) return ''
  const shown = blockers.slice(0, 2).join(' / ')
  const more = blockers.length > 2 ? ` 等 ${blockers.length} 项状态` : ''
  return `${shown}${more} · 移动速度为 0`
}

export function buildConditionReactionLockReason(conditions = [], durations = {}) {
  if (!Array.isArray(conditions)) return ''

  const blockers = collectConditionImpactSources(conditions, durations, 'reaction_block')
  if (!blockers.length) return ''
  const shown = blockers.slice(0, 2).join(' / ')
  const more = blockers.length > 2 ? ` +${blockers.length - 2}` : ''
  return `${shown}${more} \u00b7 \u4e0d\u80fd\u91c7\u53d6\u53cd\u5e94`
}

export function buildConditionStandUpMoveNotice({ conditions = [], durations = {}, turnState = {} } = {}) {
  if (!Array.isArray(conditions)) return null

  const proneSource = collectConditionSources(conditions, durations, 'prone')[0]
  if (!proneSource) return null

  const movementMax = readMovementNumber(turnState?.movement_max, 6)
  const baseMovementMax = readMovementNumber(turnState?.base_movement_max, movementMax)
  const movementUsed = readMovementNumber(turnState?.movement_used, 0)
  const remaining = Math.max(0, movementMax - movementUsed)
  const cost = baseMovementMax > 0 ? Math.max(1, Math.floor(baseMovementMax / 2)) : 0
  const blocksMovement = cost <= 0 || remaining < cost
  const reason = cost <= 0
    ? `${proneSource} · 起身需要移动力，当前剩余 ${remaining} 格`
    : `${proneSource} · 起身需要 ${cost} 格移动力，当前剩余 ${remaining} 格`

  return {
    sourceLabel: proneSource,
    cost,
    remaining,
    blocksMovement,
    reason: blocksMovement ? reason : '',
    title: blocksMovement ? reason : `${proneSource} · 移动前会先起身，消耗 ${cost} 格`,
  }
}

export function buildConditionFrightenedMoveBlockedReason({
  conditions = [],
  durations = {},
  from = null,
  to = null,
  entityPositions = {},
} = {}) {
  if (!Array.isArray(conditions)) return ''
  if (!conditions.some(condition => conditionKey(condition) === 'frightened')) return ''
  if (!from || !to) return ''

  const sources = collectFrightenedSourcePositions(durations, entityPositions)
  for (const source of sources) {
    const oldDistance = gridDistance(from, source)
    const newDistance = gridDistance(to, source)
    if (oldDistance != null && newDistance != null && newDistance < oldDistance) {
      return `${formatConditionLabel('frightened')} · 不能主动靠近恐惧来源`
    }
  }
  return ''
}

export function buildConditionCharmedTargetBlockedReason({
  conditions = [],
  durations = {},
  targetId = null,
} = {}) {
  if (!Array.isArray(conditions)) return ''
  if (!targetId) return ''
  if (!conditions.some(condition => conditionKey(condition) === 'charmed')) return ''

  const sourceIds = collectConditionSourceIds(durations, 'charmed', [
    'charmed_source',
    'charmed_source_id',
    'charmed_source_ids',
    'charmer',
    'charmer_id',
    'charmer_ids',
  ])
  if (sourceIds.has(String(targetId))) {
    return `${formatConditionLabel('charmed')} · 不能攻击魅惑者`
  }
  return ''
}

export function buildConditionCharmedHarmfulTargetBlockedReason({
  conditions = [],
  durations = {},
  targetId = null,
  targetIds = null,
} = {}) {
  if (!Array.isArray(conditions)) return ''
  if (!conditions.some(condition => conditionKey(condition) === 'charmed')) return ''

  const ids = Array.isArray(targetIds)
    ? targetIds
    : targetId ? [targetId] : []
  if (!ids.length) return ''

  const sourceIds = collectConditionSourceIds(durations, 'charmed', [
    'charmed_source',
    'charmed_source_id',
    'charmed_source_ids',
    'charmer',
    'charmer_id',
    'charmer_ids',
  ])
  if (ids.some(id => sourceIds.has(String(id)))) {
    return `${formatConditionLabel('charmed')} · 不能以有害法术指定魅惑者`
  }
  return ''
}

export function buildConditionHiddenTargetBlockedReason(conditions = []) {
  if (!Array.isArray(conditions)) return ''
  if (conditions.some(condition => conditionKey(condition) === 'hidden')) {
    return `${formatConditionLabel('hidden')} · 不能直接指定攻击`
  }
  return ''
}

export function formatConditionLabel(condition) {
  return conditionLabel(conditionKey(condition))
}

export function formatConditionWithDuration(condition, durations = {}) {
  const key = conditionKey(condition)
  if (!key) return ''
  if (key === 'exhaustion') {
    const level = exhaustionLevel(condition, durations)
    return level ? `${conditionLabel(key)} ${level}` : conditionLabel(key)
  }
  const label = conditionLabel(key)
  const duration = conditionDuration(condition, key, durations)
  return duration ? `${label} (${formatShortDuration(duration)})` : label
}

export function formatConditionExpiryLog(message = '') {
  const text = String(message || '')
  return text.replace(/【([^】]+)】/g, (_, condition) => `【${formatConditionLabel(condition)}】`)
}

function collectConditionImpactSources(conditions = [], durations = {}, impactKey) {
  const blockers = []
  const seen = new Set()
  for (const condition of conditions) {
    const key = conditionKey(condition)
    if (!key || seen.has(key)) continue
    const hasImpact = conditionImpacts(key, condition, durations).some(item => item.key === impactKey)
    if (!hasImpact) continue
    seen.add(key)
    blockers.push(conditionImpactSourceLabel(condition, key, durations))
  }
  return blockers
}

function collectConditionSources(conditions = [], durations = {}, targetKey) {
  const sources = []
  const seen = new Set()
  for (const condition of conditions) {
    const key = conditionKey(condition)
    if (!key || key !== targetKey || seen.has(key)) continue
    seen.add(key)
    sources.push(conditionImpactSourceLabel(condition, key, durations))
  }
  return sources
}

function collectFrightenedSourcePositions(durations = {}, entityPositions = {}) {
  const entries = [durationEntry(durations, 'frightened')]
  ;['frightened_source', 'frightened_source_position', 'frightened_source_id'].forEach(key => {
    if (Object.prototype.hasOwnProperty.call(durations || {}, key)) entries.push(durations[key])
  })

  const sources = []
  entries.forEach(entry => {
    if (!entry) return
    if (typeof entry === 'object' && !Array.isArray(entry)) {
      const sourcePosition = positionFrom(entry.source_position || entry.sourcePosition)
      if (sourcePosition) sources.push(sourcePosition)
      const sourceIds = Array.isArray(entry.source_ids || entry.sourceIds)
        ? (entry.source_ids || entry.sourceIds)
        : [entry.source_id || entry.sourceId]
      sourceIds.filter(Boolean).forEach(id => {
        const position = positionFrom(entityPositions?.[String(id)])
        if (position) sources.push(position)
      })
      return
    }
    const position = positionFrom(entityPositions?.[String(entry)])
    if (position) sources.push(position)
  })

  const seen = new Set()
  return sources.filter(source => {
    const key = `${source.x}_${source.y}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function collectConditionSourceIds(durations = {}, condition, extraKeys = []) {
  const entries = [durationEntry(durations, condition)]
  extraKeys.forEach(key => {
    if (Object.prototype.hasOwnProperty.call(durations || {}, key)) entries.push(durations[key])
  })

  const sourceIds = new Set()
  entries.forEach(entry => {
    sourceIdsFrom(entry).forEach(id => sourceIds.add(id))
  })
  return sourceIds
}

function sourceIdsFrom(entry) {
  if (entry == null) return []
  if (Array.isArray(entry)) return entry.flatMap(item => sourceIdsFrom(item))
  if (typeof entry === 'object') {
    const ids = []
    ;['source_ids', 'sourceIds', 'charmer_ids', 'charmerIds', 'caster_ids', 'casterIds'].forEach(key => {
      ids.push(...sourceIdsFrom(entry[key]))
    })
    ;[
      'source_id',
      'sourceId',
      'source',
      'charmer_id',
      'charmerId',
      'charmer',
      'caster_id',
      'casterId',
      'source_entity_id',
      'sourceEntityId',
    ].forEach(key => {
      const value = entry[key]
      if (value != null && typeof value !== 'object') ids.push(String(value))
    })
    return ids
  }
  return [String(entry)]
}

function durationEntry(durations = {}, condition) {
  const canonical = conditionKey(condition)
  for (const [key, value] of Object.entries(durations || {})) {
    if (conditionKey(key) === canonical) return value
  }
  return null
}

function positionFrom(value) {
  if (!value || typeof value !== 'object') return null
  const x = Number(value.x)
  const y = Number(value.y)
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  return { x, y }
}

function gridDistance(a, b) {
  const from = positionFrom(a)
  const to = positionFrom(b)
  if (!from || !to) return null
  return Math.max(Math.abs(from.x - to.x), Math.abs(from.y - to.y))
}

function conditionSummary(condition, durations = {}) {
  const key = conditionKey(condition)
  if (!key) return null
  if (key === 'exhaustion') return exhaustionSummary(condition, durations)
  const duration = conditionDuration(condition, key, durations)
  const beneficial = Object.prototype.hasOwnProperty.call(BENEFICIAL_RULES, key)
  const label = conditionLabel(key)
  const rule = BENEFICIAL_RULES[key] || CONDITION_RULES[key] || '状态已生效；查看日志确认具体来源和持续时间。'
  const durationText = duration ? ` 持续：${duration} 轮。` : ''

  return {
    key,
    label,
    tone: beneficial ? 'buff' : 'harm',
    summary: rule,
    title: `${label}：${rule}${durationText}`,
    duration,
  }
}

function conditionImpacts(key, condition = null, durations = {}) {
  if (key === 'exhaustion') return exhaustionImpacts(condition, durations)
  if (CONDITION_IMPACTS[key]) return [...CONDITION_IMPACTS[key], ...repeatSaveImpacts(key, condition, durations)]
  if (key.endsWith('_resistance')) {
    return [impact('resist', '抗性', '伤害抗性已生效。', 'good')]
  }
  if (Object.prototype.hasOwnProperty.call(BENEFICIAL_RULES, key)) {
    return [impact('buff_active', '增益', BENEFICIAL_RULES[key], 'good')]
  }
  return repeatSaveImpacts(key, condition, durations)
}

function repeatSaveImpacts(key, condition = null, durations = {}) {
  const metadata = repeatSaveMetadata(key, condition, durations)
  if (!metadata) return []

  const requires = metadata.repeat_save_requires || metadata.requires || metadata.repeatSaveRequires
  if (key === 'frightened' || requires === 'no_line_of_sight_to_source') {
    return [
      impact('repeat_save_los', '\u4e0d\u53ef\u89c1\u8c41\u514d', '\u770b\u4e0d\u5230\u6050\u60e7\u6765\u6e90\u65f6\uff0c\u56de\u5408\u672b\u53ef\u91cd\u590d\u611f\u77e5\u8c41\u514d\u3002', 'warning'),
    ]
  }

  const ability = String(metadata.save_ability || metadata.saveAbility || '').trim().toUpperCase()
  const dc = metadata.save_dc ?? metadata.saveDc ?? metadata.dc
  const detail = ability && dc ? ` ${ability} DC ${dc}` : ''
  return [
    impact('repeat_save', '\u56de\u5408\u672b\u8c41\u514d', `\u56de\u5408\u672b\u53ef\u91cd\u590d${detail}\u8c41\u514d\uff1b\u6210\u529f\u65f6\u89e3\u9664\u72b6\u6001\u3002`, 'warning'),
  ]
}

function repeatSaveMetadata(key, condition = null, durations = {}) {
  const entry = durationEntry(durations, key)
  const candidates = [
    entry,
    condition && typeof condition === 'object' ? condition : null,
  ].filter(value => value && typeof value === 'object' && !Array.isArray(value))

  for (const item of candidates) {
    if (
      item.repeat_save === 'end_of_turn'
      || item.repeatSave === 'end_of_turn'
      || item.save_dc != null
      || item.saveDc != null
      || item.dc != null
    ) {
      return item
    }
  }
  return null
}

function impact(key, label, title, tone = 'bad') {
  return { key, label, title, tone }
}

function conditionImpactSourceLabel(condition, key, durations = {}) {
  const label = conditionLabel(key)
  if (key === 'exhaustion') {
    const level = exhaustionLevel(condition, durations)
    return level ? `${label} ${level}` : label
  }
  const duration = conditionDuration(condition, key, durations)
  return duration ? `${label} (${formatShortDuration(duration)})` : label
}

function exhaustionSummary(condition, durations = {}) {
  const level = exhaustionLevel(condition, durations)
  const label = level ? `力竭 ${level}` : '力竭'
  const summary = exhaustionRuleSummary(level)
  return {
    key: 'exhaustion',
    label,
    tone: 'harm',
    summary,
    title: `${label}：${summary}`,
    duration: null,
    level,
  }
}

function exhaustionImpacts(condition = null, durations = {}) {
  const level = exhaustionLevel(condition, durations)
  if (level <= 0) return CONDITION_IMPACTS.exhaustion

  const impacts = []
  if (level >= 6) {
    impacts.push(
      impact('death', '死亡', '力竭 6 级会导致死亡。'),
      impact('no_actions', '无法行动', '力竭 6 级：死亡，不能采取动作或反应。'),
    )
  }
  if (level >= 5) {
    impacts.push(impact('speed_0', '速度 0', `力竭 ${level} 级：移动速度降为 0。`))
  } else if (level >= 2) {
    impacts.push(impact('speed_halved', '速度减半', `力竭 ${level} 级：移动速度减半。`, 'warning'))
  }
  if (level >= 4) {
    impacts.push(impact('hp_max_halved', 'HP上限减半', `力竭 ${level} 级：生命值上限减半。`))
  }
  if (level >= 3) {
    impacts.push(
      impact('attack_disadv', '攻击劣势', `力竭 ${level} 级：攻击骰处于劣势。`),
      impact('save_disadv', '豁免劣势', `力竭 ${level} 级：豁免处于劣势。`),
    )
  }
  impacts.push(impact('check_disadv', '检定劣势', `力竭 ${level} 级：属性检定处于劣势。`))
  return impacts
}

function exhaustionRuleSummary(level = 0) {
  const safeLevel = clampExhaustionLevel(level)
  if (safeLevel <= 0) return '力竭惩罚生效；等级决定严重程度。'
  const rules = [
    '能力检定劣势',
    '速度减半',
    '攻击和豁免劣势',
    'HP上限减半',
    '速度降为 0',
    '死亡',
  ]
  return `${rules.slice(0, safeLevel).join('；')}。`
}

function exhaustionLevel(condition = null, durations = {}) {
  const raw = typeof condition === 'object' && condition
    ? condition.exhaustion_level ?? condition.exhaustionLevel ?? condition.level ?? condition.value
    : null
  const value = durations?.exhaustion_level
    ?? durations?.exhaustionLevel
    ?? durations?.exhaustion
    ?? raw
  return clampExhaustionLevel(value)
}

function clampExhaustionLevel(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 0
  return Math.max(0, Math.min(6, Math.floor(number)))
}

function conditionDuration(condition, key, durations = {}) {
  const raw = typeof condition === 'string'
    ? condition
    : condition?.name || condition?.condition || condition?.type || condition?.id || ''
  return normalizedDurationValue(durations?.[key] ?? durations?.[raw] ?? null)
}

function formatShortDuration(duration) {
  const value = normalizedDurationValue(duration)
  const numeric = Number(value)
  if (!Number.isNaN(numeric)) return `${value}轮`
  return String(value)
}

function normalizedDurationValue(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return value
  return value.duration
    ?? value.duration_rounds
    ?? value.durationRounds
    ?? value.rounds
    ?? value.turns
    ?? null
}

function readMovementNumber(value, fallback = 0) {
  const number = Number(value)
  if (!Number.isFinite(number)) return fallback
  return Math.max(0, Math.floor(number))
}

function conditionKey(condition) {
  if (typeof condition === 'string') return normalize(condition)
  if (!condition || typeof condition !== 'object') return ''
  return normalize(condition.name || condition.condition || condition.type || condition.id || '')
}

function normalize(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
  return CONDITION_ALIASES[normalized] || normalized
}

function conditionLabel(key) {
  if (CONDITION_LABELS[key]) return CONDITION_LABELS[key]
  return key
    .split('_')
    .filter(Boolean)
    .map(part => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(' ')
}
