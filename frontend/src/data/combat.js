/**
 * data/combat.js — 战斗相关的静态数据表。
 *
 * 从 pages/Combat.jsx 抽出来，避免在一个大文件里混杂数据与 UI。
 */

// 技能描述查表（用于技能栏 tooltip），按 skillBar 条目的 k 键匹配。
export const SKILL_INFO = {
  atk:   { desc: '用主手武器发起一次近战或远程攻击。命中后掷伤害骰。' },
  spell: { desc: '打开法术列表选择法术；施法消耗对应环级法术位。' },
  shove: { desc: '推倒或推开对手。对方进行力量(运动) vs 力量/敏捷(特技)对抗。' },
  grapple: { desc: '尝试擒抱目标。双方进行力量(运动)对抗，成功后目标速度降为0。' },
  help:  { desc: '辅助相邻盟友。其下一次攻击或检定获得优势。' },
  dash:  { desc: '冲刺——本回合移动力翻倍，但消耗你的动作。' },
  disg:  { desc: '脱离接战——移动时不触发敌方的借机攻击。' },
  dodge: { desc: '闪避——对你的攻击骰劣势；敏捷豁免优势。' },
  pot:   { desc: '服用治疗药剂（2d4+2 HP）。消耗一次附赠行动。' },
  death: { desc: '濒死——每回合自动进行死亡豁免。无需手动触发。' },
}

// 默认技能栏：后端 /skill-bar 不可用或返回空列表时的本地兜底。
export const DEFAULT_SKILL_BAR = [
  { k: 'atk',   label: '攻击', glyph: '⚔', cost: '动作', key: '1', kind: 'attack', available: true },
  { k: 'spell', label: '法术', glyph: '✧', cost: '动作', key: '2', kind: 'spell', available: true },
  { k: 'shove', label: '推撞', glyph: '↦', cost: '动作', key: '3', kind: 'attack', available: true },
  { k: 'help',  label: '协助', glyph: '☉', cost: '动作', key: '4', kind: 'bonus', available: true },
  { k: 'dash',  label: '冲刺', glyph: '»', cost: '动作', key: '5', kind: 'move', available: true },
  { k: 'disg',  label: '脱离', glyph: '↶', cost: '动作', key: '6', kind: 'move', available: true },
  { k: 'dodge', label: '闪避', glyph: '⊙', cost: '动作', key: '7', kind: 'bonus', available: true },
  { k: 'death', label: '濒死', glyph: '☠', cost: '—', key: '8', kind: 'empty', available: false },
  { k: 'grapple', label: '擒抱', glyph: '⛓', cost: '动作', key: '9', kind: 'attack', available: true },
  { k: 'pot',   label: '药剂', glyph: '⚱', cost: '动作', key: '0', kind: 'bonus', available: true },
]

// 战斗宗师战技列表（Battle Master Maneuvers）
export const MANEUVERS = [
  { id: 'precision', name: '精准攻击', desc: '将优越骰加到攻击检定上', icon: '🎯', needsTarget: false },
  { id: 'trip',      name: '绊摔',     desc: '目标力量豁免失败则倒地 + 优越骰伤害', icon: '🦶', needsTarget: true  },
  { id: 'disarm',    name: '缴械',     desc: '目标力量豁免失败则掉落武器 + 优越骰伤害', icon: '🤚', needsTarget: true  },
  { id: 'riposte',   name: '反击',     desc: '敌人攻击未中时用反应攻击 + 优越骰伤害', icon: '⚔️', needsTarget: false },
  { id: 'menacing',  name: '威慑攻击', desc: '目标感知豁免失败则恐惧 + 优越骰伤害', icon: '😱', needsTarget: true  },
  { id: 'pushing',   name: '推力攻击', desc: '将目标推开15尺 + 优越骰伤害', icon: '💨', needsTarget: true  },
  { id: 'goading',   name: '引诱攻击', desc: '目标攻击你以外的生物有劣势 + 优越骰伤害', icon: '🤬', needsTarget: true  },
]
