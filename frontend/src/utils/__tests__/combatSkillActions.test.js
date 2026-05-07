import { describe, expect, it, vi } from 'vitest'
import { createCombatSkillClickHandler } from '../combatSkillActions'

function makeHandler(overrides = {}) {
  const api = {
    combatAction: vi.fn().mockResolvedValue({}),
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
})
