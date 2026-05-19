import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useCharacterCreateFlow } from '../useCharacterCreateFlow'

const baseFlowState = () => ({
  setModule: vi.fn(),
  setSelectedModule: vi.fn(),
  setOptions: vi.fn(),
  setForm: vi.fn(),
  setPartySize: vi.fn(),
  setError: vi.fn(),
  setSaving: vi.fn(),
  setSavedCharId: vi.fn(),
  setPlayerCharacter: vi.fn(),
  setStep: vi.fn(),
  setGeneratingParty: vi.fn(),
  setLocalCompanions: vi.fn(),
  setCompanions: vi.fn(),
  setForgeTargetPath: vi.fn(),
  setForgeOpen: vi.fn(),
})

const baseCharacterDraft = {
  moduleId: 'module-1',
  roomSessionId: null,
  isMultiplayerCreate: false,
  form: {
    name: '艾拉',
    race: '人类',
    char_class: '法师',
    subclass: '防护学派',
    level: 2,
    background: '学者',
    alignment: '中立善良',
    multiclassEnabled: false,
    multiclass_class: '',
    multiclass_level: 1,
  },
  baseScores: { str: 8, dex: 14, con: 12, int: 15, wis: 10, cha: 10 },
  chosenSkills: ['奥秘', '调查'],
  chosenSpells: ['魔法飞弹'],
  chosenCantrips: ['光亮术'],
  fightingStyle: '',
  equipChoice: 0,
  bonusLanguages: ['精灵语'],
  chosenFeats: [],
  narrative: {
    personality: '谨慎',
    backstory: '来自灰岩镇',
    speech_style: '低声',
    combat_preference: '保持距离',
    catchphrase: '让我先看看。',
  },
  partySize: 4,
  partyStep: 5,
  savedCharId: 'char-1',
  companions: [{ id: 'companion-1' }],
}

function renderFlow(overrides = {}) {
  const state = { ...baseFlowState(), ...(overrides.state || {}) }
  const apis = {
    modulesApi: { get: vi.fn().mockResolvedValue({ id: 'module-1', level_min: 3, recommended_party_size: 5 }) },
    charactersApi: {
      options: vi.fn().mockResolvedValue({ racial_ability_bonuses: { 人类: { int: 1 } } }),
      create: vi.fn().mockResolvedValue({ id: 'char-1', name: '艾拉' }),
      generateParty: vi.fn().mockResolvedValue({ companions: [{ id: 'companion-1' }] }),
    },
    roomsApi: { claimChar: vi.fn().mockResolvedValue({}) },
    gameApi: { createSession: vi.fn().mockResolvedValue({ session_id: 'session-1' }) },
    ...(overrides.apis || {}),
  }
  const navigate = overrides.navigate || vi.fn()
  const draft = { ...baseCharacterDraft, ...(overrides.draft || {}) }

  const hook = renderHook((props) => useCharacterCreateFlow(props), {
    initialProps: {
      ...draft,
      ...state,
      navigate,
      ...apis,
    },
  })

  return { ...hook, state, apis, navigate }
}

describe('useCharacterCreateFlow', () => {
  it('loads module and options into CharacterCreate state', async () => {
    const { state, apis } = renderFlow()

    await waitFor(() => {
      expect(apis.modulesApi.get).toHaveBeenCalledWith('module-1')
      expect(apis.charactersApi.options).toHaveBeenCalled()
    })

    expect(state.setModule).toHaveBeenCalledWith({ id: 'module-1', level_min: 3, recommended_party_size: 5 })
    expect(state.setSelectedModule).toHaveBeenCalledWith({ id: 'module-1', level_min: 3, recommended_party_size: 5 })
    expect(state.setForm).toHaveBeenCalledWith(expect.any(Function))
    expect(state.setPartySize).toHaveBeenCalledWith(5)

    const updater = state.setForm.mock.calls[0][0]
    expect(updater({ level: 1, name: '艾拉' })).toEqual({ level: 3, name: '艾拉' })
  })

  it('creates and claims a multiplayer character before navigating back to room', async () => {
    const { result, state, apis, navigate } = renderFlow({
      draft: {
        isMultiplayerCreate: true,
        roomSessionId: 'room-1',
      },
    })

    await act(async () => {
      await result.current.handleSaveAndContinue()
    })

    expect(apis.charactersApi.create).toHaveBeenCalledWith(expect.objectContaining({
      module_id: 'module-1',
      name: '艾拉',
      known_spells: ['魔法飞弹'],
      cantrips: ['光亮术'],
      personality: '谨慎',
    }))
    expect(apis.roomsApi.claimChar).toHaveBeenCalledWith('room-1', 'char-1')
    expect(navigate).toHaveBeenCalledWith('/room/room-1')
    expect(state.setStep).not.toHaveBeenCalledWith(5)
    expect(state.setSaving).toHaveBeenLastCalledWith(false)
  })

  it('keeps the player on create page when multiplayer room claim fails', async () => {
    const claimError = new Error('房间已经关闭')
    const { result, state, apis, navigate } = renderFlow({
      draft: {
        isMultiplayerCreate: true,
        roomSessionId: 'room-1',
      },
      apis: {
        roomsApi: { claimChar: vi.fn().mockRejectedValue(claimError) },
      },
    })

    await act(async () => {
      await result.current.handleSaveAndContinue()
    })

    expect(apis.charactersApi.create).toHaveBeenCalled()
    expect(apis.roomsApi.claimChar).toHaveBeenCalledWith('room-1', 'char-1')
    expect(navigate).not.toHaveBeenCalled()
    expect(state.setError).toHaveBeenCalledWith('角色认领失败：房间已经关闭。角色已保存，请重试或联系管理员。')
    expect(state.setSaving).toHaveBeenLastCalledWith(false)
  })
})
