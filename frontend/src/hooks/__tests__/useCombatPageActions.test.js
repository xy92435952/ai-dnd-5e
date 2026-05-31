import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { roomsGetMock } = vi.hoisted(() => ({
  roomsGetMock: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  gameApi: {
    combatAction: vi.fn(),
    getCombat: vi.fn(),
    move: vi.fn(),
  },
  roomsApi: {
    get: roomsGetMock,
  },
}))

import { gameApi } from '../../api/client'
import { useCombatPageActions } from '../useCombatPageActions'

describe('useCombatPageActions websocket sync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function renderActions(overrides = {}) {
    const deps = {
      sessionId: 'sess-1',
      setRoom: vi.fn(),
      myCharacterId: 'guest-char',
      playerId: 'guest-char',
      moveMode: false,
      isProcessing: false,
      canActThisTurn: true,
      selectedTarget: 'enemy-1',
      entities: {},
      entityPositions: {},
      playerPos: null,
      setError: vi.fn(),
      setCombat: vi.fn(),
      setTurnState: vi.fn(),
      setReactionPrompt: vi.fn(),
      setSpellModalOpen: vi.fn(),
      setHelpMode: vi.fn(),
      handleAttack: vi.fn(),
      handleDash: vi.fn(),
      handleDisengage: vi.fn(),
      handleDodge: vi.fn(),
      handleClassFeature: vi.fn(),
      setMoveMode: vi.fn(),
      setAoePreview: vi.fn(),
      setAoeHover: vi.fn(),
      setAoeLockedCenter: vi.fn(),
      clearAoePreview: vi.fn(),
      onLoadCombat: vi.fn(),
      setCombatOver: vi.fn(),
      onCombatEnded: vi.fn(),
      combat: {
        round_number: 1,
        current_turn_index: 0,
        turn_order: [{ character_id: 'guest-char', id: 'guest-char' }],
      },
      ...overrides,
    }
    return { deps, ...renderHook(() => useCombatPageActions(deps)) }
  }

  it('applies combat_update payloads and reloads the fresh combat snapshot', () => {
    const combat = {
      current_turn_index: 1,
      turn_order: [
        { character_id: 'host-char', is_player: true },
        { character_id: 'guest-char', is_player: true },
      ],
      turn_states: {
        'guest-char': { action_used: false, movement_used: 2 },
      },
    }
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        combat,
        combat_over: true,
        outcome: { result: 'victory' },
      })
    })

    expect(deps.setCombat).toHaveBeenCalledWith(combat)
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: false, movement_used: 2 })
    expect(deps.setCombatOver).toHaveBeenCalledWith({ result: 'victory' })
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('builds shaped AoE previews from hovered spells', () => {
    const { result, deps } = renderActions({
      selectedTarget: 'enemy-1',
      entityPositions: {
        'enemy-1': { x: 7, y: 4 },
      },
      playerPos: { x: 2, y: 2 },
    })

    act(() => {
      result.current.handleSpellHover({
        name: 'Burning Hands',
        aoe: true,
        desc: '15尺锥形区域喷射火焰',
      })
    })

    expect(deps.setAoePreview).toHaveBeenCalledWith({
      radius: 3,
      template: 'cone',
      spellName: 'Burning Hands',
    })
    expect(deps.setAoeHover).toHaveBeenCalledWith('7_4')

    act(() => {
      result.current.handleSpellHover({
        name: 'Spirit Guardians',
        aoe: true,
        desc: '15尺内敌人减速',
      })
    })

    expect(deps.setAoePreview).toHaveBeenLastCalledWith({
      radius: 3,
      template: 'aura',
      spellName: 'Spirit Guardians',
    })
    expect(deps.setAoeHover).toHaveBeenLastCalledWith('2_2')
  })

  it('uses returned combat snapshot and logs hazard damage after movement', async () => {
    const addLog = vi.fn()
    const combatSnapshot = {
      entity_positions: {
        'guest-char': { x: 4, y: 5 },
      },
      entities: {
        'guest-char': { id: 'guest-char', hp_current: 6 },
      },
    }
    gameApi.move.mockResolvedValue({
      combat: combatSnapshot,
      turn_state: { movement_used: 1, movement_max: 6 },
      hazard_result: {
        triggered: true,
        target_name: 'Hero',
        label: 'sparking conduit',
        final_damage: 4,
        damage_type: 'lightning',
        hp_before: 10,
        hp_after: 6,
      },
    })
    const { result, deps } = renderActions({
      moveMode: true,
      addLog,
    })

    await act(async () => {
      await result.current.handleMoveTo(4, 5)
    })

    expect(gameApi.move).toHaveBeenCalledWith('sess-1', 'guest-char', 4, 5, '1:0:guest-char')
    expect(deps.setCombat).toHaveBeenCalledWith(combatSnapshot)
    expect(deps.setTurnState).toHaveBeenCalledWith({ movement_used: 1, movement_max: 6 })
    expect(addLog).toHaveBeenCalledWith(expect.objectContaining({
      role: 'system',
      log_type: 'combat',
      content: expect.stringContaining('4 lightning'),
    }))
    expect(deps.setMoveMode).toHaveBeenCalledWith(false)
  })

  it('keeps websocket reaction prompts so non-reactors can see a non-blocking notice', () => {
    const { result, deps } = renderActions()
    const prompt = {
      trigger: 'spell_cast',
      reactor_character_id: 'guest-char',
      options: [{ type: 'counterspell' }],
    }

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        player_can_react: true,
        reaction_prompt: prompt,
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith(prompt)

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        player_can_react: true,
        reaction_prompt: {
          ...prompt,
          reactor_character_id: 'host-char',
        },
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenLastCalledWith({
      ...prompt,
      reactor_character_id: 'host-char',
    })
    expect(deps.setReactionPrompt).toHaveBeenCalledTimes(2)
  })

  it('clears stale reaction prompts when a combat update has no active prompt', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        player_can_react: false,
        reaction_prompt: null,
      })
    })

    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.onLoadCombat).toHaveBeenCalledTimes(1)
  })

  it('cleans local combat state and skips reload when websocket says combat ended', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({
        type: 'combat_update',
        combat: null,
        combat_over: true,
        outcome: 'victory',
      })
    })

    expect(deps.setCombatOver).toHaveBeenCalledWith('victory')
    expect(deps.setReactionPrompt).toHaveBeenCalledWith(null)
    expect(deps.setTurnState).toHaveBeenCalledWith(null)
    expect(deps.setCombat).toHaveBeenCalledWith(null)
    expect(deps.onCombatEnded).toHaveBeenCalledWith('victory')
    expect(deps.onLoadCombat).not.toHaveBeenCalled()
  })

  it('reloads combat for turn, movement, and dm response realtime events', () => {
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({ type: 'turn_changed' })
      result.current.onWsEvent({ type: 'entity_moved' })
      result.current.onWsEvent({ type: 'dm_responded' })
    })

    expect(deps.onLoadCombat).toHaveBeenCalledTimes(3)
  })

  it('merges room_state_updated and online member snapshots without a room refetch', () => {
    const { result, deps } = renderActions()
    const prevRoom = {
      is_multiplayer: true,
      current_speaker_user_id: 'host',
      members: [{ user_id: 'host', character_id: 'host-char', is_online: true }],
    }
    const updatedRoom = {
      is_multiplayer: true,
      current_speaker_user_id: 'guest',
      members: [{ user_id: 'guest', character_id: 'guest-char', is_online: true }],
    }
    const onlineMembers = [
      { user_id: 'host', character_id: 'host-char', is_online: true },
      { user_id: 'guest', character_id: 'guest-char', is_online: true },
    ]

    act(() => {
      result.current.onWsEvent({ type: 'room_state_updated', room: updatedRoom })
    })
    expect(deps.setRoom).toHaveBeenCalledTimes(1)
    expect(deps.setRoom.mock.calls[0][0](prevRoom)).toMatchObject({
      current_speaker_user_id: 'guest',
      _currentSpeaker: 'guest',
      members: updatedRoom.members,
    })

    act(() => {
      result.current.onWsEvent({ type: 'member_online', members: onlineMembers })
    })
    expect(deps.setRoom).toHaveBeenCalledTimes(2)
    expect(deps.setRoom.mock.calls[1][0](prevRoom).members).toEqual(onlineMembers)
    expect(roomsGetMock).not.toHaveBeenCalled()
  })

  it('refetches the room when online events do not include members', async () => {
    roomsGetMock.mockResolvedValue({
      is_multiplayer: true,
      members: [{ user_id: 'guest', is_online: true }],
    })
    const { result, deps } = renderActions()

    act(() => {
      result.current.onWsEvent({ type: 'member_offline', user_id: 'guest' })
    })

    await waitFor(() => {
      expect(roomsGetMock).toHaveBeenCalledWith('sess-1')
      expect(deps.setRoom).toHaveBeenCalledWith({
        is_multiplayer: true,
        members: [{ user_id: 'guest', is_online: true }],
      })
    })
  })

  it('submits Help on an allied target, refreshes combat, and exits help mode', async () => {
    gameApi.combatAction.mockResolvedValue({
      action: 'help',
      turn_state: { action_used: true },
    })
    gameApi.getCombat.mockResolvedValue({
      turn_states: {
        'ally-1': { being_helped: true },
      },
    })
    const { result, deps } = renderActions({
      helpMode: true,
      entities: {
        'ally-1': { id: 'ally-1', is_enemy: false, name: 'Ally' },
      },
    })

    let ok
    await act(async () => {
      ok = await result.current.handleHelpTarget('ally-1')
    })

    expect(ok).toBe(true)
    expect(gameApi.combatAction).toHaveBeenCalledWith('sess-1', '协助', 'ally-1', false, false, '1:0:guest-char')
    expect(gameApi.getCombat).toHaveBeenCalledWith('sess-1')
    expect(deps.setTurnState).toHaveBeenCalledWith({ action_used: true })
    expect(deps.setCombat).toHaveBeenCalledWith({
      turn_states: {
        'ally-1': { being_helped: true },
      },
    })
    expect(deps.setHelpMode).toHaveBeenCalledWith(false)
    expect(deps.setError).not.toHaveBeenCalled()
  })

  it('rejects enemy and self Help targets without sending an action', async () => {
    const { result, deps } = renderActions({
      helpMode: true,
      entities: {
        'enemy-1': { id: 'enemy-1', is_enemy: true, name: 'Enemy' },
      },
    })

    await act(async () => {
      expect(await result.current.handleHelpTarget('enemy-1')).toBe(false)
      expect(await result.current.handleHelpTarget('guest-char')).toBe(false)
    })

    expect(gameApi.combatAction).not.toHaveBeenCalled()
    expect(deps.setError).toHaveBeenCalledWith('请选择一名队友作为协助目标')
  })
})
