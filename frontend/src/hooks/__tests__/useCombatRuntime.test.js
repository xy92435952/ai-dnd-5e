import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { captures } = vi.hoisted(() => ({
  captures: {
    pageActionsArgs: null,
  },
}))

vi.mock('../useWebSocket', () => ({
  useWebSocket: () => ({ connected: true, status: 'connected' }),
}))

vi.mock('../useCombatSkillBar', () => ({
  useCombatSkillBar: () => ({ skills: [] }),
}))

vi.mock('../useCombatSpells', () => ({
  useCombatSpells: () => ({ spells: [] }),
}))

vi.mock('../useCombatDerivedState', () => ({
  useCombatDerivedState: () => ({
    canActThisTurn: true,
    entities: {},
    entityPositions: {},
    playerPos: null,
  }),
}))

vi.mock('../useCombatFlowHandlers', () => ({
  useCombatFlowHandlers: () => ({
    loadCombat: vi.fn(),
    handleEndTurn: vi.fn(),
    handleDelayTurn: vi.fn(),
    handleAttack: vi.fn(),
    handleCastSpell: vi.fn(),
    handleEndConcentration: vi.fn(),
    handleDeathSave: vi.fn(),
    handleSmite: vi.fn(),
    handleReaction: vi.fn(),
    handleCancelReaction: vi.fn(),
    handleLegendaryAction: vi.fn(),
    handleSkipLegendaryAction: vi.fn(),
    handleLairAction: vi.fn(),
    handleSkipLairAction: vi.fn(),
    handleManeuver: vi.fn(),
    handleClassFeature: vi.fn(),
    handleHealingPotion: vi.fn(),
    handleDodge: vi.fn(),
    handleDash: vi.fn(),
    handleDisengage: vi.fn(),
  }),
}))

vi.mock('../useCombatPrediction', () => ({
  useCombatPrediction: () => null,
}))

vi.mock('../useCombatPageActions', () => ({
  useCombatPageActions: (args) => {
    captures.pageActionsArgs = args
    return {
      onWsEvent: vi.fn(),
      onSkillClick: vi.fn(),
      handleMoveTo: vi.fn(),
      handleHelpTarget: vi.fn(),
      handleInspectTarget: vi.fn(),
      handleSpellHover: vi.fn(),
    }
  },
}))

vi.mock('../useCombatReconnectRefresh', () => ({
  useCombatReconnectRefresh: vi.fn(),
}))

import { useCombatRuntime } from '../useCombatRuntime'

describe('useCombatRuntime', () => {
  beforeEach(() => {
    captures.pageActionsArgs = null
  })

  function renderRuntime(overrides = {}) {
    const page = {
      combat: {
        current_turn_index: 0,
        turn_order: [{ character_id: 'hero-1', is_player: true }],
      },
      setCombat: vi.fn(),
      isProcessing: false,
      setIsProcessing: vi.fn(),
      combatOver: null,
      setCombatOver: vi.fn(),
      spellModalOpen: false,
      setSpellModalOpen: vi.fn(),
      spellQuickPick: null,
      setSpellQuickPick: vi.fn(),
      playerSpellSlots: {},
      playerKnownSpells: [],
      playerCantrips: [],
      playerId: 'hero-1',
      turnState: {},
      setTurnState: vi.fn(),
      smitePrompt: null,
      setSmitePrompt: vi.fn(),
      playerClass: 'Fighter',
      playerLevel: 5,
      classResources: {},
      useLuckyAttack: false,
      setUseLuckyAttack: vi.fn(),
      useBardicAttack: false,
      setUseBardicAttack: vi.fn(),
      useBardicDeathSave: false,
      setUseBardicDeathSave: vi.fn(),
      useBardicEndSave: false,
      setUseBardicEndSave: vi.fn(),
      useBardicSpellSave: false,
      setUseBardicSpellSave: vi.fn(),
      playerSubclass: '',
      playerSubclassEffects: {},
      maneuverModalOpen: false,
      setManeuverModalOpen: vi.fn(),
      reactionPrompt: null,
      setReactionPrompt: vi.fn(),
      legendaryActionPrompt: null,
      setLegendaryActionPrompt: vi.fn(),
      lairActionPrompt: null,
      setLairActionPrompt: vi.fn(),
      session: {},
      setSession: vi.fn(),
      setError: vi.fn(),
      aiTimer: { current: null },
      processingRef: { current: false },
      ...overrides.page,
    }
    const targeting = {
      selectedTarget: null,
      setSelectedTarget: vi.fn(),
      moveMode: false,
      setMoveMode: vi.fn(),
      helpMode: false,
      isRanged: false,
      showThreat: false,
      aoePreview: null,
      setAoePreview: vi.fn(),
      aoeHover: null,
      setAoeHover: vi.fn(),
      aoeLockedCenter: null,
      setAoeLockedCenter: vi.fn(),
      setHelpMode: vi.fn(),
      clearAoePreview: vi.fn(),
      ...overrides.targeting,
    }
    const log = {
      logs: [],
      logsEndRef: { current: null },
      addLog: vi.fn(),
      ...overrides.log,
    }

    return {
      page,
      targeting,
      log,
      ...renderHook(() => useCombatRuntime({
        sessionId: 'sess-1',
        room: null,
        setRoom: vi.fn(),
        refreshRoom: vi.fn(),
        myUserId: 'user-1',
        myCharacterId: null,
        showDice: vi.fn(),
        page,
        targeting,
        log,
        navigate: vi.fn(),
      })),
    }
  }

  it('passes boss control prompt setters into websocket page actions', () => {
    const { page } = renderRuntime()

    expect(captures.pageActionsArgs).toMatchObject({
      setReactionPrompt: page.setReactionPrompt,
      setLairActionPrompt: page.setLairActionPrompt,
      setLegendaryActionPrompt: page.setLegendaryActionPrompt,
    })
  })
})
