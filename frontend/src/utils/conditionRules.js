const CONDITION_LABELS = {
  blinded: '目盲',
  charmed: '魅惑',
  deafened: '耳聋',
  frightened: '恐慌',
  grappled: '被擒抱',
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
  hexed: '诅咒',
  slowed: '迟缓',
  marked: '标记',
  burning: '燃烧',
  webbed: '蛛网束缚',
  blessed: '祝福',
  bless: '祝福',
  fire_resistance: '火焰抗性',
  cold_resistance: '寒冷抗性',
  acid_resistance: '强酸抗性',
  lightning_resistance: '闪电抗性',
  thunder_resistance: '雷鸣抗性',
  rage: '狂暴',
  concentrating: '专注',
}

const CONDITION_RULES = {
  blinded: '无法看见；攻击它的攻击具有优势，它的攻击具有劣势。',
  charmed: '不能攻击魅惑者；魅惑者对它进行社交检定有优势。',
  deafened: '无法听见，且自动失败基于听觉的检定。',
  frightened: '来源可见时攻击骰和属性检定处于劣势；不能主动靠近来源。',
  grappled: '速度变为 0，直到擒抱结束。',
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
  hexed: '受到敌对诅咒；查看战斗日志确认被影响的属性。',
  slowed: '速度和动作选项减少；敏捷豁免可能受罚。',
  marked: '被敌对效果标记；攻击或后续效果可能优先锁定它。',
  burning: '受到持续火焰或高热压力；查看战斗日志确认伤害时机。',
  webbed: '被蛛网或黏性地形束缚，直到挣脱。',
}

const BENEFICIAL_RULES = {
  blessed: '激活期间，攻击和豁免获得额外骰。',
  bless: '激活期间，攻击和豁免获得额外骰。',
  fire_resistance: '此防护持续期间，火焰伤害降低。',
  cold_resistance: '此防护持续期间，寒冷伤害降低。',
  acid_resistance: '此防护持续期间，强酸伤害降低。',
  lightning_resistance: '此防护持续期间，闪电伤害降低。',
  thunder_resistance: '此防护持续期间，雷鸣伤害降低。',
  rage: '狂暴类防护生效；查看日志确认伤害和动作限制。',
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
  frightened: [
    impact('attack_disadv', '攻击劣势', '来源可见时，攻击骰和检定处于劣势。'),
    impact('move_block', '移动受限', '不能主动靠近恐惧来源。'),
  ],
  grappled: [
    impact('speed_0', '速度 0', '移动速度降为 0。'),
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
  hexed: [
    impact('check_disadv', '检定劣势', '被选定的属性检定可能处于劣势。'),
  ],
  slowed: [
    impact('action_limit', '动作受限', '可用动作选项减少。'),
    impact('dex_disadv', '敏捷劣势', '敏捷豁免可能处于劣势。'),
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
    const impacts = conditionImpacts(key)
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

function conditionSummary(condition, durations = {}) {
  const key = conditionKey(condition)
  if (!key) return null
  const duration = durations?.[key] ?? durations?.[condition] ?? null
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

function conditionImpacts(key) {
  if (CONDITION_IMPACTS[key]) return CONDITION_IMPACTS[key]
  if (key.endsWith('_resistance')) {
    return [impact('resist', '抗性', '伤害抗性已生效。', 'good')]
  }
  if (Object.prototype.hasOwnProperty.call(BENEFICIAL_RULES, key)) {
    return [impact('buff_active', '增益', BENEFICIAL_RULES[key], 'good')]
  }
  return []
}

function impact(key, label, title, tone = 'bad') {
  return { key, label, title, tone }
}

function conditionImpactSourceLabel(condition, key, durations = {}) {
  const label = conditionLabel(key)
  const duration = conditionDuration(condition, key, durations)
  return duration ? `${label} (${formatShortDuration(duration)})` : label
}

function conditionDuration(condition, key, durations = {}) {
  const raw = typeof condition === 'string'
    ? condition
    : condition?.name || condition?.condition || condition?.type || condition?.id || ''
  return durations?.[key] ?? durations?.[raw] ?? null
}

function formatShortDuration(duration) {
  const numeric = Number(duration)
  if (!Number.isNaN(numeric)) return `${duration}轮`
  return String(duration)
}

function conditionKey(condition) {
  if (typeof condition === 'string') return normalize(condition)
  if (!condition || typeof condition !== 'object') return ''
  return normalize(condition.name || condition.condition || condition.type || condition.id || '')
}

function normalize(value) {
  return String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
}

function conditionLabel(key) {
  if (CONDITION_LABELS[key]) return CONDITION_LABELS[key]
  return key
    .split('_')
    .filter(Boolean)
    .map(part => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(' ')
}
