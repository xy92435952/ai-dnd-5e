/**
 * utils/combat.js — 战斗场景下用到的纯工具函数。
 *
 * 原先散落在 pages/Combat.jsx 顶部和底部的 computeSkillStats /
 * aoeRadiusCells / applyHpUpdate 三个纯函数抽到这里，Combat.jsx 只管
 * render + state。
 */

/**
 * 根据玩家角色 + 目标估算某技能的命中率 / 伤害。
 * 用于技能栏 hover tooltip。
 *
 * @param {object} skill        - skillBar entry，含 kind ('attack' | 'spell' | 'move' | 'bonus') 和 k ('atk' | 'spell' | ...)
 * @param {object} player       - 当前玩家 Character（derived 字段会被读）
 * @param {object|null} target  - 锁定目标实体（有 ac 字段）
 * @param {object|null} hover   - 鼠标悬停的临时目标
 * @returns {Array<{label:string, value:string|number}>|null}
 */
export function computeSkillStats(skill, player, target, hoverTarget) {
  if (!player) return null
  const d = player.derived || {}
  const atkBonus = d.attack_bonus ?? (d.proficiency_bonus || 2) + (d.ability_modifiers?.str || 0)
  const targetAc = (hoverTarget || target)?.ac ?? target?.ac ?? null

  const stats = []
  if (skill.kind === 'attack') {
    if (targetAc != null) {
      // 命中率 = P(d20 + atkBonus >= targetAc)
      const needed = targetAc - atkBonus
      const pct = needed <= 1 ? 95 : needed >= 20 ? 5 : Math.max(5, Math.min(95, (21 - needed) * 5))
      stats.push({ label: '命中率', value: `${pct}%` })
      stats.push({ label: '攻击加值', value: `+${atkBonus}` })
    } else {
      stats.push({ label: '命中率', value: '需选目标' })
      stats.push({ label: '攻击加值', value: `+${atkBonus}` })
    }
  } else if (skill.kind === 'spell') {
    stats.push({ label: '法术 DC', value: d.spell_save_dc ?? '—' })
    stats.push({ label: '施法加值', value: `+${(d.proficiency_bonus || 2) + (d.ability_modifiers?.cha || 0)}` })
  } else if (skill.kind === 'move') {
    stats.push({ label: '移动力', value: `${d.speed ?? 30} 尺` })
  } else if (skill.kind === 'bonus' && skill.k === 'pot') {
    stats.push({ label: '恢复', value: '2d4+2' })
  }
  return stats
}

/**
 * 粗略估算 AoE 法术的格子半径：从描述里抓 "N尺"，5尺/格。
 *
 * @param {object} spell
 * @returns {number} 格子数；非 AoE 法术返回 0；抓不到描述则默认 3（15ft）
 */
export function aoeRadiusCells(spell) {
  if (!spell || !spell.aoe) return 0
  const m = (spell.desc || '').match(/(\d+)\s*尺/)
  if (m) return Math.max(1, Math.round(parseInt(m[1]) / 5))
  return 3
}

/**
 * 不可变地更新 combat.entities[targetId].hp_current。
 * HP 下限 0。调用方无需 structuredClone。
 *
 * @param {object} combat
 * @param {string|null} targetId
 * @param {number|null|undefined} newHp
 * @returns {object} 新的 combat 对象（未命中时返回原对象）
 */
export function applyHpUpdate(combat, targetId, newHp) {
  if (!targetId || newHp === null || newHp === undefined) return combat
  const entities = { ...combat.entities }
  if (entities[targetId]) {
    entities[targetId] = { ...entities[targetId], hp_current: Math.max(0, newHp) }
  }
  return { ...combat, entities }
}
