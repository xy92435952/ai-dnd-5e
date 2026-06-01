export const CHOICE_INTENTS = {
  roleplay: { type: 'roleplay', label: '扮演' },
  dialogue: { type: 'dialogue', label: '对话' },
  movement: { type: 'movement', label: '移动' },
  investigation: { type: 'investigation', label: '调查' },
  rest: { type: 'rest', label: '休整' },
  lore: { type: 'lore', label: '知识' },
  danger: { type: 'danger', label: '危险' },
}

const INTENT_ALIASES = {
  roleplay: 'roleplay',
  rp: 'roleplay',
  social: 'dialogue',
  talk: 'dialogue',
  dialogue: 'dialogue',
  dialog: 'dialogue',
  conversation: 'dialogue',
  move: 'movement',
  movement: 'movement',
  travel: 'movement',
  navigation: 'movement',
  route: 'movement',
  exit: 'movement',
  location_exit: 'movement',
  investigate: 'investigation',
  investigation: 'investigation',
  inspect: 'investigation',
  search: 'investigation',
  rest: 'rest',
  short_rest: 'rest',
  long_rest: 'rest',
  lore: 'lore',
  knowledge: 'lore',
  danger: 'danger',
  attack: 'danger',
  combat: 'danger',
  hostile: 'danger',
}

const SKILL_KIND_TO_INTENT = {
  insight: 'dialogue',
  persuade: 'dialogue',
  persuasion: 'dialogue',
  intim: 'dialogue',
  intimidation: 'dialogue',
  deception: 'dialogue',
  performance: 'dialogue',
  perception: 'investigation',
  investigate: 'investigation',
  investigation: 'investigation',
  sleight: 'investigation',
  athletic: 'movement',
  acrobat: 'movement',
  stealth: 'movement',
  arcana: 'lore',
  history: 'lore',
  nature: 'lore',
  religion: 'lore',
  洞察: 'dialogue',
  劝说: 'dialogue',
  威吓: 'dialogue',
  欺瞒: 'dialogue',
  表演: 'dialogue',
  察觉: 'investigation',
  调查: 'investigation',
  巧手: 'investigation',
  运动: 'movement',
  特技: 'movement',
  隐匿: 'movement',
  奥秘: 'lore',
  历史: 'lore',
  自然: 'lore',
  宗教: 'lore',
}

const TEXT_PATTERNS = [
  { type: 'danger', pattern: /(攻击|拔剑|威胁|冲锋|伏击|战斗|开火|strike|attack|fight|threaten|ambush)/i },
  { type: 'rest', pattern: /(休息|短休|长休|扎营|睡|营地|rest|camp|sleep)/i },
  { type: 'dialogue', pattern: /(询问|交谈|说服|威吓|欺骗|谈判|聊天|ask|talk|persuade|negotiate|question)/i },
  { type: 'movement', pattern: /(前往|进入|离开|穿过|靠近|跟随|攀爬|跳|潜行|move|go to|enter|leave|follow|climb|sneak)/i },
  { type: 'investigation', pattern: /(检查|调查|搜查|观察|聆听|寻找|inspect|search|examine|look for|listen)/i },
  { type: 'lore', pattern: /(回忆|辨认|研究|阅读|符文|传说|历史|recall|identify|study|read|rune|legend|history)/i },
]

function normalizeIntentType(value) {
  const key = String(value || '').trim().toLowerCase()
  return INTENT_ALIASES[key] || null
}

function intentFromTags(tags = []) {
  if (!Array.isArray(tags)) return null

  for (const tag of tags) {
    const kind = String(tag?.kind || '').trim()
    const label = String(tag?.label || '').trim()
    const normalized = normalizeIntentType(kind) || normalizeIntentType(label)
    if (normalized) return normalized
    if (SKILL_KIND_TO_INTENT[kind]) return SKILL_KIND_TO_INTENT[kind]
    if (SKILL_KIND_TO_INTENT[label]) return SKILL_KIND_TO_INTENT[label]
  }
  return null
}

function intentFromText(text = '') {
  const value = String(text || '')
  const match = TEXT_PATTERNS.find(item => item.pattern.test(value))
  return match?.type || null
}

export function getChoiceIntent(choice = {}) {
  const obj = typeof choice === 'string' ? { text: choice } : (choice || {})
  if (obj.action) return CHOICE_INTENTS.danger
  if (obj.location_exit && typeof obj.location_exit === 'object' && !obj.location_exit.hidden) {
    return CHOICE_INTENTS.movement
  }

  const explicit = normalizeIntentType(obj.choice_type || obj.action_type || obj.type || obj.intent)
  const fromTags = intentFromTags(obj.tags)
  const fromSkill = obj.skill_check
    ? (SKILL_KIND_TO_INTENT[String(obj.kind || obj.check_type || '').trim()] || fromTags)
    : null
  const fromText = intentFromText(obj.text)
  const type = explicit || fromSkill || fromTags || fromText || 'roleplay'

  return CHOICE_INTENTS[type] || CHOICE_INTENTS.roleplay
}

export function getChoiceLocationExit(choice = {}) {
  const obj = typeof choice === 'string' ? { text: choice } : (choice || {})
  const exit = obj.location_exit
  if (!exit || typeof exit !== 'object' || exit.hidden) return null

  const destination = String(exit.target_location_name || exit.name || exit.target_location_id || '').trim()
  const routeType = String(exit.route_type || exit.type || '').trim()
  const flags = []
  if (exit.locked) flags.push('锁定')
  if (exit.one_way) flags.push('单向')
  const normalizedRouteType = routeType.toLowerCase()
  if (routeType && !['route', 'movement', 'locked', 'hidden', 'one_way', 'one-way'].includes(normalizedRouteType)) {
    flags.push(routeType)
  }

  return {
    destination: destination || '未知地点',
    flags,
    tone: exit.locked ? 'locked' : exit.one_way ? 'one-way' : 'route',
  }
}
