import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  smiteMock,
  useReactionMock,
  getCombatMock,
  maneuverMock,
  rollDice3DMock,
} = vi.hoisted(() => ({
  smiteMock: vi.fn(),
  useReactionMock: vi.fn(),
  getCombatMock: vi.fn(),
  maneuverMock: vi.fn(),
  rollDice3DMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    smite: smiteMock,
    useReaction: useReactionMock,
    getCombat: getCombatMock,
    maneuver: maneuverMock,
  },
}))

vi.mock('../../components/DiceRollerOverlay', () => ({
  rollDice3D: rollDice3DMock,
}))

import { useCombatSpecialActions } from '../useCombatSpecialActions'

describe('useCombatSpecialActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    rollDice3DMock.mockResolvedValue({ total: 9, rolls: [4, 5] })
    smiteMock.mockResolvedValue({
      narration: '神圣能量爆发',
      remaining_slots: { '1st': 0 },
      target_id: 'enemy-1',
      target_new_hp: 2,
    })
    useReactionMock.mockResolvedValue({
      narration: '地狱斥责命中',
      turn_state: { reaction_used: true },
    })
    getCombatMock.mockResolvedValue({
      turn_states: {},
    })
    maneuverMock.mockResolvedValue({
      narration: '战技命中',
      turn_state: { action_used: true },
      class_resources: { superiority_dice_remaining: 2 },
      target_new_hp: 3,
      superiority_die_roll: 6,
      superiority_die: 'd8',
    })
  })

  function renderActions(overrides = {}) {
    const processingRef = { current: false }
    const deps = {
      sessionId: 'sess-1',
      selectedTarget: 'enemy-1',
      isProcessing: false,
      smitePrompt: { show: true, targetId: 'enemy-1' },
      playerSubclassEffects: { superiority_die: 'd8' },
      processingRef,
      setIsProcessing: vi.fn(),
      setError: vi.fn(),
      setSmitePrompt: vi.fn(),
      setPlayerSpellSlots: vi.fn(),
      setTurnState: vi.fn(),
      setClassResources: vi.fn(),
      setCombat: vi.fn(),
      setReactionPrompt: vi.fn(),
      setCombatOver: vi.fn(),
      triggerAiTurn: vi.fn(),
      showDice: vi.fn(),
      addLog: vi.fn(),
      ...overrides,
    }
    return { deps, processingRef, ...renderHook(() => useCombatSpecialActions(deps)) }
  }

  it('rolls smite dice and applies target hp', async () => {
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleSmite(1)
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8, 2)
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 8, result: 9, label: '神圣斩击', count: 2 })
    expect(smiteMock).toHaveBeenCalledWith('sess-1', 1, false, [4, 5], 'enemy-1', false)
    expect(deps.setSmitePrompt).toHaveBeenCalledWith(null)

    const hpUpdater = deps.setCombat.mock.calls[0][0]
    expect(hpUpdater({
      entities: {
        'enemy-1': { id: 'enemy-1', hp_current: 8 },
      },
    }).entities['enemy-1'].hp_current).toBe(2)
  })

  it('doubles smite dice after a critical hit', async () => {
    rollDice3DMock.mockResolvedValueOnce({ total: 18, rolls: [4, 5, 4, 5] })
    const { result, deps } = renderActions({
      smitePrompt: { show: true, targetId: 'enemy-1', isCrit: true },
    })

    await act(async () => {
      await result.current.handleSmite(1)
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8, 4)
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 8, result: 18, label: '神圣斩击', count: 4 })
    expect(smiteMock).toHaveBeenCalledWith('sess-1', 1, false, [4, 5, 4, 5], 'enemy-1', true)
  })

  it('uses reaction and resumes ai turns', async () => {
    useReactionMock.mockResolvedValueOnce({
      narration: '护盾术让攻击落空',
      turn_state: { reaction_used: true },
      reaction_effect: {
        hp_before_reaction: 3,
        hp_after_reaction: 12,
        hp_restored: 9,
      },
      target_state: {
        target_id: 'char-2',
        target_name: 'Smoke Sentinel',
        hp_current: 12,
        conditions: ['shield_spell'],
        life_state: 'alive',
      },
      remaining_slots: { '1st': 0 },
    })
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleReaction('shield', 'enemy-1', 'char-2')
    })

    expect(rollDice3DMock).not.toHaveBeenCalled()
    expect(useReactionMock).toHaveBeenCalledWith('sess-1', 'shield', 'enemy-1', 'char-2')
    expect(deps.addLog).toHaveBeenCalledWith({
      role: 'player',
      content: '护盾术让攻击落空',
      log_type: 'combat',
      reaction_effect: {
        hp_before_reaction: 3,
        hp_after_reaction: 12,
        hp_restored: 9,
      },
      dice_result: {
        type: 'reaction',
        reaction_type: 'shield',
        hp_before_reaction: 3,
        hp_after_reaction: 12,
        hp_restored: 9,
      },
      state_changes: expect.arrayContaining([
        'Smoke Sentinel HP 3 -> 12（反应恢复 9）',
        '反应已用',
      ]),
    })
    expect(deps.setTurnState).toHaveBeenCalledWith({ reaction_used: true })
    expect(deps.setPlayerSpellSlots).toHaveBeenCalledWith({ '1st': 0 })
    const hpUpdater = deps.setCombat.mock.calls[0][0]
    expect(hpUpdater({
      entities: {
        'char-2': { id: 'char-2', hp_current: 3, conditions: [] },
      },
    }).entities['char-2']).toMatchObject({
      hp_current: 12,
      conditions: ['shield_spell'],
      life_state: 'alive',
    })
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('rolls Cutting Words and submits the rolled die value with the reaction', async () => {
    rollDice3DMock.mockResolvedValueOnce({ total: 6, rolls: [6] })
    useReactionMock.mockResolvedValueOnce({
      narration: 'Cutting Words turns the strike aside.',
      turn_state: { reaction_used: true },
      reaction_effect: {
        cutting_words: { die: 'd8', roll: 6, uses_remaining: 1 },
        damage_prevented: 8,
        hp_restored: 8,
        class_resources: { bardic_inspiration_remaining: 1 },
      },
      target_state: {
        target_id: 'char-2',
        target_name: 'Lore Bard',
        hp_current: 20,
        class_resources: { bardic_inspiration_remaining: 1 },
      },
    })
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleReaction(
        'cutting_words',
        'enemy-1',
        'char-2',
        { die: 'd8' },
      )
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8, 1)
    expect(deps.showDice).toHaveBeenCalledWith({
      faces: 8,
      result: 6,
      label: 'Cutting Words d8',
      count: 1,
    })
    expect(useReactionMock).toHaveBeenCalledWith(
      'sess-1',
      'cutting_words',
      'enemy-1',
      'char-2',
      { cuttingWordsRoll: 6 },
    )
    expect(deps.setClassResources).toHaveBeenCalledWith({ bardic_inspiration_remaining: 1 })
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('rolls Cutting Words for damage reduction reactions', async () => {
    rollDice3DMock.mockResolvedValueOnce({ total: 3, rolls: [3] })
    useReactionMock.mockResolvedValueOnce({
      narration: 'Cutting Words reduces the damage roll.',
      turn_state: { reaction_used: true },
      reaction_effect: {
        cutting_words: { die: 'd8', roll: 3, uses_remaining: 1 },
        damage_roll_before: 8,
        damage_roll_after: 5,
        damage_prevented: 3,
        hp_restored: 3,
        class_resources: { bardic_inspiration_remaining: 1 },
      },
      target_state: {
        target_id: 'char-2',
        target_name: 'Lore Bard',
        hp_current: 15,
        class_resources: { bardic_inspiration_remaining: 1 },
      },
    })
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleReaction(
        'cutting_words_damage',
        'enemy-1',
        'char-2',
        { die: 'd8' },
      )
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8, 1)
    expect(deps.showDice).toHaveBeenCalledWith({
      faces: 8,
      result: 3,
      label: 'Cutting Words d8',
      count: 1,
    })
    expect(useReactionMock).toHaveBeenCalledWith(
      'sess-1',
      'cutting_words_damage',
      'enemy-1',
      'char-2',
      { cuttingWordsRoll: 3 },
    )
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      reaction_effect: expect.objectContaining({
        damage_roll_before: 8,
        damage_roll_after: 5,
        damage_prevented: 3,
      }),
      dice_result: expect.objectContaining({
        type: 'reaction',
        reaction_type: 'cutting_words_damage',
        damage_roll_before: 8,
        damage_roll_after: 5,
        damage_prevented: 3,
      }),
      state_changes: expect.not.arrayContaining([
        'Cutting Words d8=3: damage 8 -> 5; prevented 3',
      ]),
    }))
    expect(deps.setClassResources).toHaveBeenCalledWith({ bardic_inspiration_remaining: 1 })
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('rolls Bardic Inspiration and submits the die value for spell-save prompts without auto-advancing', async () => {
    rollDice3DMock.mockResolvedValueOnce({ total: 4, rolls: [4] })
    useReactionMock.mockResolvedValueOnce({
      action: 'spell',
      reaction_type: 'bardic_spell_save',
      narration: 'Sacred Flame resolves after Bardic Inspiration.',
      turn_state: {},
      target_state: {
        target_id: 'char-2',
        target_name: 'Bardic Target',
        class_resources: { bardic_inspiration: { die: 'd8', uses_remaining: 0 } },
      },
    })
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleReaction(
        'bardic_spell_save',
        'char-2',
        'char-2',
        { die: 'd8' },
      )
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8, 1)
    expect(deps.showDice).toHaveBeenCalledWith({
      faces: 8,
      result: 4,
      label: 'Bardic Inspiration d8',
      count: 1,
    })
    expect(useReactionMock).toHaveBeenCalledWith(
      'sess-1',
      'bardic_spell_save',
      'char-2',
      'char-2',
      { bardicInspirationRoll: 4 },
    )
    expect(deps.setClassResources).toHaveBeenCalledWith({
      bardic_inspiration: { die: 'd8', uses_remaining: 0 },
    })
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('ignores duplicate reaction clicks while one is in flight', async () => {
    const { result, deps, processingRef } = renderActions()
    processingRef.current = true

    await act(async () => {
      await result.current.handleReaction('hellish_rebuke', 'enemy-1', 'char-2')
    })

    expect(useReactionMock).not.toHaveBeenCalled()
    expect(rollDice3DMock).not.toHaveBeenCalled()
    expect(deps.setReactionPrompt).not.toHaveBeenCalledWith(null)
  })

  it('restores a combat reaction prompt from the latest snapshot after submit failure', async () => {
    const pendingReaction = {
      trigger: 'incoming_attack',
      attacker_id: 'enemy-1',
      attacker_name: 'Ogre',
      incoming_damage: 9,
      target_hp_before_damage: 12,
      available_reactions: [{ type: 'shield', name: 'Shield' }],
    }
    const freshCombat = {
      turn_states: {
        'char-2': {
          reaction_used: false,
          pending_attack_reaction: pendingReaction,
        },
      },
    }
    useReactionMock.mockRejectedValueOnce(new Error('Reaction failed'))
    getCombatMock.mockResolvedValueOnce(freshCombat)
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleReaction('shield', 'enemy-1', 'char-2')
    })

    expect(useReactionMock).toHaveBeenCalledWith('sess-1', 'shield', 'enemy-1', 'char-2')
    expect(getCombatMock).toHaveBeenCalledWith('sess-1')
    expect(deps.setCombat).toHaveBeenCalledWith(freshCombat)
    expect(deps.setTurnState).toHaveBeenCalledWith(freshCombat.turn_states['char-2'])
    expect(deps.setReactionPrompt).toHaveBeenLastCalledWith({
      ...pendingReaction,
      reactor_character_id: 'char-2',
    })
    expect(deps.setError).toHaveBeenCalledWith('本轮反应已经用过了，等到你的下个回合开始后会恢复。')
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('declines spell reactions on the server before resuming ai turns', async () => {
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleCancelReaction({
        trigger: 'spell_cast',
        target_id: 'enemy-mage',
        reactor_character_id: 'char-2',
      })
    })

    expect(useReactionMock).toHaveBeenCalledWith('sess-1', 'decline', 'enemy-mage', 'char-2')
    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('restores a combat reaction prompt from the latest snapshot after decline failure', async () => {
    const pendingReaction = {
      trigger: 'incoming_attack',
      attacker_id: 'enemy-1',
      incoming_damage: 6,
      available_reactions: [{ type: 'shield', name: 'Shield' }],
    }
    const freshCombat = {
      turn_states: {
        'char-2': {
          reaction_used: false,
          pending_attack_reaction: pendingReaction,
        },
      },
    }
    useReactionMock.mockRejectedValueOnce(new Error('Network down'))
    getCombatMock.mockResolvedValueOnce(freshCombat)
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleCancelReaction({
        trigger: 'incoming_attack',
        attacker_id: 'enemy-1',
        reactor_character_id: 'char-2',
      })
    })

    expect(useReactionMock).toHaveBeenCalledWith('sess-1', 'decline', 'enemy-1', 'char-2')
    expect(getCombatMock).toHaveBeenCalledWith('sess-1')
    expect(deps.setReactionPrompt).toHaveBeenLastCalledWith({
      ...pendingReaction,
      reactor_character_id: 'char-2',
    })
    expect(deps.setError).toHaveBeenCalledWith('Network down')
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('declines Bardic spell-save prompts and applies the resolved spell result locally', async () => {
    useReactionMock.mockResolvedValueOnce({
      action: 'spell',
      reaction_type: 'bardic_spell_save',
      narration: 'The spell resolves without Bardic Inspiration.',
      turn_state: {},
      target_state: {
        target_id: 'char-2',
        target_name: 'Bardic Target',
        hp_current: 5,
        class_resources: { bardic_inspiration: { die: 'd8', uses_remaining: 1 } },
      },
    })
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleCancelReaction({
        trigger: 'spell_save',
        target_id: 'char-2',
        reactor_character_id: 'char-2',
      })
    })

    expect(useReactionMock).toHaveBeenCalledWith('sess-1', 'decline', 'char-2', 'char-2')
    expect(deps.addLog).toHaveBeenCalledWith(expect.objectContaining({
      content: 'The spell resolves without Bardic Inspiration.',
      log_type: 'combat',
    }))
    expect(deps.setClassResources).toHaveBeenCalledWith({
      bardic_inspiration: { die: 'd8', uses_remaining: 1 },
    })
    expect(deps.setTurnState).toHaveBeenCalledWith({})
    expect(deps.triggerAiTurn).not.toHaveBeenCalled()
  })

  it('declines attack reactions on the server so refresh does not restore stale prompts', async () => {
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleCancelReaction({
        trigger: 'incoming_attack',
        attacker_id: 'enemy-1',
        reactor_character_id: 'char-2',
      })
    })

    expect(useReactionMock).toHaveBeenCalledWith('sess-1', 'decline', 'enemy-1', 'char-2')
    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.triggerAiTurn).toHaveBeenCalled()
  })

  it('runs maneuver against the selected target', async () => {
    const { result, deps } = renderActions()

    await act(async () => {
      await result.current.handleManeuver('trip_attack')
    })

    expect(rollDice3DMock).toHaveBeenCalledWith(8)
    expect(deps.showDice).toHaveBeenCalledWith({ faces: 8, result: 9, label: '战技·trip_attack' })
    expect(maneuverMock).toHaveBeenCalledWith('sess-1', 'trip_attack', 'enemy-1')
    expect(deps.setClassResources).toHaveBeenCalledWith({ superiority_dice_remaining: 2 })
  })
})
