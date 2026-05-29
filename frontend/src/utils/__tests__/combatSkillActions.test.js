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
    setSpellQuickPick: vi.fn(),
    handleDash: vi.fn(),
    handleDisengage: vi.fn(),
    handleDodge: vi.fn(),
    handleHealingPotion: vi.fn(),
    handleClassFeature: vi.fn(),
    getTurnToken: vi.fn(() => '1:0:char-1'),
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

  it('opens spell shortcuts with a matching quick pick', async () => {
    const { handler, fns } = makeHandler()

    await handler({ k: 'firebolt', available: true })
    await handler({ k: 'spell', available: true })

    expect(fns.setSpellQuickPick).toHaveBeenNthCalledWith(1, '火焰射线')
    expect(fns.setSpellQuickPick).toHaveBeenNthCalledWith(2, null)
    expect(fns.setSpellModalOpen).toHaveBeenCalledTimes(2)
    expect(fns.setSpellModalOpen).toHaveBeenCalledWith(true)
  })

  it('routes class skill keys to existing class feature names', async () => {
    const { handler, fns } = makeHandler()

    await handler({ k: 'second_wind', available: true })
    await handler({ k: 'rage', available: true })
    await handler({ k: 'cunning_action_dash', available: true })
    await handler({ k: 'cunning_action_disengage', available: true })
    await handler({ k: 'cunning_action_hide', available: true })

    expect(fns.handleClassFeature).toHaveBeenNthCalledWith(1, 'second_wind')
    expect(fns.handleClassFeature).toHaveBeenNthCalledWith(2, 'rage')
    expect(fns.handleClassFeature).toHaveBeenNthCalledWith(3, 'cunning_action_dash')
    expect(fns.handleClassFeature).toHaveBeenNthCalledWith(4, 'cunning_action_disengage')
    expect(fns.handleClassFeature).toHaveBeenNthCalledWith(5, 'cunning_action_hide')
  })

  it('routes potion skills through the inventory use handler', async () => {
    const { handler, fns, api } = makeHandler()

    await handler({ k: 'pot_heal', available: true })

    expect(fns.handleHealingPotion).toHaveBeenCalledTimes(1)
    expect(api.combatAction).not.toHaveBeenCalled()
    expect(api.getCombat).not.toHaveBeenCalled()
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
      state_changes: ['动作已用'],
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

    expect(api.combatAction).toHaveBeenCalledWith('sess-1', '副手攻击', 'enemy-1', false, false, '1:0:char-1')
    expect(api.grappleShove).not.toHaveBeenCalled()
    expect(fns.setTurnState).toHaveBeenCalledWith(offhandTurnState)
    expect(fns.addLog).toHaveBeenCalledWith({
      role: 'player',
      content: 'Tester 使用副手攻击命中训练假人',
      log_type: 'combat',
      state_changes: ['动作已用，附赠动作已用'],
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

  it('reports computed unavailable reasons before routing a skill', async () => {
    const { handler, fns, api } = makeHandler({
      getUnavailableReason: vi.fn(() => '本回合动作已使用'),
    })

    await handler({ k: 'dodge', available: true })

    expect(fns.setError).toHaveBeenCalledWith('本回合动作已使用')
    expect(fns.handleDodge).not.toHaveBeenCalled()
    expect(api.combatAction).not.toHaveBeenCalled()
  })
})
