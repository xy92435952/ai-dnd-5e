/**
 * utils/skillCheck.js - static skill-check mappings and choice preview helpers.
 *
 * Adventure choice buttons use this to show the likely check, DC, ability,
 * modifier, success chance, and risk before the player clicks.
 */

export const KIND_TO_ABILITY = {
  insight: 'wis', perception: 'wis', wisdom: 'wis',
  persuade: 'cha', intim: 'cha', deception: 'cha', performance: 'cha', charisma: 'cha',
  athletic: 'str', strength: 'str',
  acrobat: 'dex', stealth: 'dex', sleight: 'dex', dex: 'dex',
  arcana: 'int', investigate: 'int', history: 'int', nature: 'int', religion: 'int',
  洞察: 'wis', 察觉: 'wis',
  劝说: 'cha', 威吓: 'cha', 欺瞒: 'cha', 表演: 'cha',
  运动: 'str',
  特技: 'dex', 隐匿: 'dex', 巧手: 'dex',
  奥秘: 'int', 调查: 'int', 历史: 'int', 自然: 'int', 宗教: 'int',
  check: 'wis',
}

const ABILITY_LABELS = {
  str: 'STR',
  dex: 'DEX',
  con: 'CON',
  int: 'INT',
  wis: 'WIS',
  cha: 'CHA',
}

export const KIND_TO_SKILL_ZH = {
  insight: '洞察', persuade: '劝说', intim: '威吓',
  perception: '察觉', athletic: '运动', acrobat: '特技',
  stealth: '隐匿', arcana: '奥秘', investigate: '调查',
  history: '历史', nature: '自然', religion: '宗教',
  deception: '欺瞒', performance: '表演', sleight: '巧手',
}

export function getChoiceCheckTag(choice = {}) {
  if (!choice?.skill_check) return null
  const taggedCheck = Array.isArray(choice.tags)
    ? choice.tags.find(tag => tag?.dc != null)
    : null
  const dc = taggedCheck?.dc ?? choice.dc
  if (dc === null || dc === undefined) return null

  return {
    ...(taggedCheck || {}),
    dc,
    kind: taggedCheck?.kind || choice.kind || choice.check_type || 'check',
    label: taggedCheck?.label || choice.label || choice.check_type || null,
  }
}

/**
 * Estimate the check preview for a generated dialogue choice.
 *
 * Choices without `skill_check` or a usable DC return null.
 */
export function computeChoicePreview(choice, player) {
  const tag = getChoiceCheckTag(choice)
  if (!tag || !player) return null

  const dc = Number(tag.dc)
  if (!Number.isFinite(dc)) return null

  const kind = String(tag.kind || 'check').toLowerCase()
  const ability = KIND_TO_ABILITY[kind] || 'wis'
  const abilityLabel = ABILITY_LABELS[ability] || ability.toUpperCase()
  const skillZh = KIND_TO_SKILL_ZH[kind] || tag.label || '检定'

  const mods = player.derived?.ability_modifiers || {}
  const abilMod = mods[ability] ?? 0
  const profBonus = player.derived?.proficiency_bonus ?? 2
  const proficient = (player.proficient_skills || []).includes(skillZh)
  const totalMod = abilMod + (proficient ? profBonus : 0)

  const needed = dc - totalMod
  let successPct
  if (needed <= 1) successPct = 95
  else if (needed >= 20) successPct = 5
  else successPct = Math.max(5, Math.min(95, (21 - needed) * 5))

  const sign = totalMod >= 0 ? '+' : ''
  const riskTone = successPct >= 80 ? 'low' : successPct <= 30 ? 'high' : 'medium'
  const riskLabel = riskTone === 'low' ? '低风险' : riskTone === 'high' ? '高风险' : '中风险'
  const summary = {
    skill: skillZh,
    ability: abilityLabel,
    dc,
    modifier: `${sign}${totalMod}`,
    success: `${successPct}%`,
    successPct,
    risk: riskLabel,
    riskTone,
  }
  const rows = [
    { label: '目标难度', value: `DC ${dc}` },
    { label: '对应属性', value: abilityLabel },
    { label: `${skillZh}修正`, value: `${sign}${totalMod}${proficient ? ' (熟练)' : ''}` },
    { label: '成功率', value: `${successPct}%` },
    { label: '风险', value: `${riskLabel} · ${successPct}%` },
  ]

  let hint = null
  if (choice.ended) hint = '此选项将结束当前场景'
  else if (choice.action) hint = '攻击性行动，可能触发战斗'
  else if (successPct >= 80) hint = '胜券在握'
  else if (successPct <= 30) hint = '九死一生'

  return { rows, hint, summary }
}
