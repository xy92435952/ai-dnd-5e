/**
 * utils/skillCheck.js — 技能检定相关静态映射 + 选项预测函数。
 *
 * 从 Adventure.jsx 抽出来；computeChoicePreview 给"选项 hover tooltip"用，
 * 把 DC + 玩家修正值 → 成功率百分比，让玩家选选项时能看到风险预估。
 */

/** kind → 6 种属性的映射（兜底 wis）。 */
export const KIND_TO_ABILITY = {
  insight: 'wis', perception: 'wis', wisdom: 'wis',
  persuade: 'cha', intim: 'cha', deception: 'cha', performance: 'cha', charisma: 'cha',
  athletic: 'str', strength: 'str',
  acrobat: 'dex', stealth: 'dex', sleight: 'dex', dex: 'dex',
  arcana: 'int', investigate: 'int', history: 'int', nature: 'int', religion: 'int',
  check: 'wis',  // 兜底
}

/** kind → 中文技能名（用于熟练匹配 + UI 显示）。 */
export const KIND_TO_SKILL_ZH = {
  insight: '洞察', persuade: '劝说', intim: '威吓',
  perception: '察觉', athletic: '运动', acrobat: '特技',
  stealth: '隐匿', arcana: '奥秘', investigate: '调查',
  history: '历史', nature: '自然', religion: '宗教',
  deception: '欺瞒', performance: '表演', sleight: '巧手',
}

/**
 * 给一个对话选项 + 当前玩家，估算它的检定成功率与提示。
 * 没有 skill_check 标记或缺 dc 的选项返回 null（纯角色扮演选项）。
 *
 * @param {{ tags?: Array<{dc?:number, kind?:string, label?:string}>,
 *           skill_check?: boolean, ended?: boolean, action?: boolean }} choice
 * @param {{ derived?: object, proficient_skills?: string[] } | null} player
 * @returns {{ rows: Array<{label:string, value:string|number}>,
 *             hint: string|null } | null}
 */
export function computeChoicePreview(choice, player) {
  // 没有检定需求就不预告（纯角色扮演选项）
  const tag = (choice.tags || []).find(t => t.dc != null) || null
  if (!tag || !choice.skill_check || !player) return null

  const dc = Number(tag.dc)
  if (!Number.isFinite(dc)) return null

  const kind = (tag.kind || 'check').toLowerCase()
  const ability = KIND_TO_ABILITY[kind] || 'wis'
  const skillZh = KIND_TO_SKILL_ZH[kind] || tag.label || '检定'

  const mods = player.derived?.ability_modifiers || {}
  const abilMod = mods[ability] ?? 0
  const profBonus = player.derived?.proficiency_bonus ?? 2
  const proficient = (player.proficient_skills || []).includes(skillZh)
  const totalMod = abilMod + (proficient ? profBonus : 0)

  // 成功率 = P(d20 >= dc - totalMod)，d20 均匀，结果取值 [5%, 95%]
  const needed = dc - totalMod
  let successPct
  if (needed <= 1)       successPct = 95
  else if (needed >= 20) successPct = 5
  else                   successPct = Math.max(5, Math.min(95, (21 - needed) * 5))

  const sign = totalMod >= 0 ? '+' : ''
  const rows = [
    { label: '目标难度', value: `DC ${dc}` },
    { label: `${skillZh}修正`, value: `${sign}${totalMod}${proficient ? ' (熟)' : ''}` },
    { label: '成功率', value: `${successPct}%` },
  ]

  let hint = null
  if (choice.ended)      hint = '⚠ 此选项将结束当前场景'
  else if (choice.action) hint = '⚔ 攻击性行动 —— 可能触发战斗'
  else if (successPct >= 80) hint = '胜券在握'
  else if (successPct <= 30) hint = '九死一生'

  return { rows, hint }
}
