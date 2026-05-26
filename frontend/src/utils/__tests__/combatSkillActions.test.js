import { describe, expect, it, vi } from 'vitest'
import { createCombatSkillClickHandler } from '../combatSkillActions'

function makeHandler(overrides = {}) {
  const api = {
    combatAction: vi.fn().mockResolvedValue({}),
    grappleShove: vi.fn().mockResolvedValue({
      narration: 'Tester 推倒训练假人',
      turn_state: { action_used: true },
    }),
    getCombat: vi.fn().mockResolvedValue({ current_turn_index: 0 }),
  }
  const fns = {
    getIsProcessing: vi.fn(() => false),
    getIsPlayerTurn: vi.fn(() => true),
    getSelectedTarget: vi.fn(() => 'enemy-1'),
    setError: vi.fn(),
    handleAttack: vi.fn(),
    setSpellModalOpen: vi.fn(),
    gameApi: api,
    sessionId: 'sess-1',
    setCombat: vi.fn(),
    setTurnState: vi.fn(),
    addLog: vi.fn(),
    setHelpMode: vi.fn(),
    handleDash: vi.fn(),
    handleDisengage: vi.fn(),
    handleDodge: vi.fn(),
    handleClassFeature: vi.fn(),
    ...overrides,
  }
  return {
    fns,
    api,
    handler: createCombatSkillClickHandler(fns),
  }
}

describe('createCombatSkillClickHandler', () => {
  it('runs attacks only when a target is selected', async () => {
    const { handler, fns } = makeHandler({ getSelectedTarget: vi.fn(() => null) })

    await handler({ k: 'atk', available: true })

    expect(fns.setError).toHaveBeenCalledWith('请先选择目标')
    expect(fns.handleAttack).not.toHaveBeenCalled()
  })

  it('routes sneak attack through the normal attack flow', async () => {
    const { handler, fns } = makeHandler()

    await handler({ k: 'sneak', available: true })

    expect(fns.handleAttack).toHaveBeenCalledTimes(1)
    expect(fns.setSpellModalOpen).not.toHaveBeenCalled()
  })

  it('routes class skill keys to existing class feature names', async () => {
    const { handler, fns } = makeHandler()

    await handler({ k: 'second_wind', available: true })
    await handler({ k: 'rage', available: true })

    expect(fns.handleClassFeature).toHaveBeenNthCalledWith(1, 'second_wind')
    expect(fns.handleClassFeature).toHaveBeenNthCalledWith(2, 'rage')
  })

  it('keeps potion behavior on the legacy combat action endpoint', async () => {
    const { handler, fns, api } = makeHandler()

    await handler({ k: 'pot_heal', available: true })

    expect(api.combatAction).toHaveBeenCalledWith('sess-1', '饮用治疗药剂', null, false)
    expect(api.getCombat).toHaveBeenCalledWith('sess-1')
    expect(fns.setCombat).toHaveBeenCalledWith({ current_turn_index: 0 })
  })

  it('routes shove and grapple through the dedicated contested-check endpoint', async () => {
    const { handler, fns, api } = makeHandler()

    await handler({ k: 'shove', available: true })
    await handler({ k: 'grapple', available: true })

    expect(api.grappleShove).toHaveBeenNthCalledWith(1, 'sess-1', 'shove', 'enemy-1', 'prone')
    expect(api.grappleShove).toHaveBeenNthCalledWith(2, 'sess-1', 'grapple', 'enemy-1', 'prone')
    expect(api.combatAction).not.toHaveBeenCalled()
    expect(api.getCombat).toHaveBeenCalledTimes(2)
    expect(fns.setTurnState).toHaveBeenCalledWith({ action_used: true })
    expect(fns.addLog).toHaveBeenCalledWith({
      role: 'player',
      content: 'Tester 推倒训练假人',
      log_type: 'combat',
    })
    expect(fns.setCombat).toHaveBeenCalledWith({ current_turn_index: 0 })
  })

  it('routes offhand attacks through the combat action endpoint', async () => {
    const offhandTurnState = { action_used: true, bonus_action_used: true }
    const { handler, fns, api } = makeHandler()
    api.combatAction.mockResolvedValueOnce({
      narration: 'Tester 使用副手攻击命中训练假人',
      turn_state: offhandTurnState,
    })

    await handler({ k: 'off_attack', available: true })

    expect(api.combatAction).toHaveBeenCalledWith('sess-1', '副手攻击', 'enemy-1', false)
    expect(api.grappleShove).not.toHaveBeenCalled()
    expect(fns.setTurnState).toHaveBeenCalledWith(offhandTurnState)
    expect(fns.addLog).toHaveBeenCalledWith({
      role: 'player',
      content: 'Tester 使用副手攻击命中训练假人',
      log_type: 'combat',
    })
    expect(api.getCombat).toHaveBeenCalledWith('sess-1')
    expect(fns.setCombat).toHaveBeenCalledWith({ current_turn_index: 0 })
  })

  it('requires a selected target before shove or grapple', async () => {
    const { handler, fns, api } = makeHandler({ getSelectedTarget: vi.fn(() => null) })

    await handler({ k: 'shove', available: true })
    await handler({ k: 'grapple', available: true })

    expect(fns.setError).toHaveBeenCalledTimes(2)
    expect(fns.setError).toHaveBeenCalledWith('请先选择目标')
    expect(api.grappleShove).not.toHaveBeenCalled()
  })

  it('requires a selected target before offhand attack', async () => {
    const { handler, fns, api } = makeHandler({ getSelectedTarget: vi.fn(() => null) })

    await handler({ k: 'off_attack', available: true })

    expect(fns.setError).toHaveBeenCalledWith('请先选择目标')
    expect(api.combatAction).not.toHaveBeenCalled()
    expect(api.getCombat).not.toHaveBeenCalled()
  })
})
