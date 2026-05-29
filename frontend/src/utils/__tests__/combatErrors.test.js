import { describe, expect, it } from 'vitest'
import { combatErrorMessage, formatCombatError } from '../combatErrors'

describe('combatErrors', () => {
  it.each([
    ['Attack token is stale; refresh combat state', '战斗状态已经更新，请稍等刷新后再操作。'],
    ['not your turn', '现在还不是你的回合，请等待当前行动者完成行动。'],
    ['target is out of range', '目标不在可达范围内，请靠近、换目标，或选择远程/法术行动。'],
    ['本回合行动已用尽', '本回合的动作已经用过了，请选择附赠动作、移动或结束回合。'],
    ['No spell slot available', '可用法术位不足，请改用戏法、低环法术或其他行动。'],
    ['target dead', '这个目标已经倒下，不能再作为该行动的目标。'],
    ['stunned actors cannot act', '当前状态阻止你执行这个行动，请先解除状态或等待队友援助。'],
  ])('maps %s to a player-facing combat message', (raw, expected) => {
    expect(combatErrorMessage(raw)).toBe(expected)
  })

  it('preserves unknown useful backend messages', () => {
    expect(combatErrorMessage('需要先选择一个有效目标')).toBe('需要先选择一个有效目标')
  })

  it('accepts Error objects', () => {
    expect(formatCombatError(new Error('reaction already used'))).toBe(
      '本轮反应已经用过了，等到你的下个回合开始后会恢复。',
    )
  })
})
