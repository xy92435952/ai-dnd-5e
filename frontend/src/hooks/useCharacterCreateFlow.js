import { useCallback, useEffect } from 'react'
import { charactersApi as defaultCharactersApi } from '../api/characters'
import { gameApi as defaultGameApi } from '../api/game'
import { modulesApi as defaultModulesApi } from '../api/modules'
import { roomsApi as defaultRoomsApi } from '../api/rooms'
import { normalizeCharacterOptions } from '../utils/characterCreate'

function buildNarrativePayload(narrative = {}) {
  return {
    personality: narrative.personality?.trim() || null,
    backstory: narrative.backstory?.trim() || null,
    speech_style: narrative.speech_style?.trim() || null,
    combat_preference: narrative.combat_preference?.trim() || null,
    catchphrase: narrative.catchphrase?.trim() || null,
  }
}

function buildMulticlassInfo(form) {
  return form.multiclassEnabled && form.multiclass_class
    ? { char_class: form.multiclass_class, level: form.multiclass_level }
    : null
}

export function useCharacterCreateFlow({
  moduleId,
  roomSessionId = null,
  isMultiplayerCreate = false,
  form,
  baseScores,
  chosenSkills,
  chosenSpells,
  chosenCantrips,
  fightingStyle,
  equipChoice,
  bonusLanguages,
  chosenFeats,
  narrative,
  partySize,
  partyStep,
  savedCharId,
  companions,
  setModule,
  setSelectedModule,
  setOptions,
  setForm,
  setPartySize,
  setError,
  setSaving,
  setSavedCharId,
  setPlayerCharacter,
  setStep,
  setGeneratingParty,
  setLocalCompanions,
  setCompanions,
  setForgeTargetPath,
  setForgeOpen,
  navigate,
  modulesApi = defaultModulesApi,
  charactersApi = defaultCharactersApi,
  roomsApi = defaultRoomsApi,
  gameApi = defaultGameApi,
}) {
  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      try {
        const [mod, opts] = await Promise.all([
          modulesApi.get(moduleId),
          charactersApi.options(),
        ])
        if (cancelled) return
        setModule(mod)
        setSelectedModule(mod)
        setOptions(normalizeCharacterOptions(opts))
        setForm((current) => ({ ...current, level: mod.level_min || 1 }))
        setPartySize(mod.recommended_party_size || 4)
        setError('')
      } catch (e) {
        if (!cancelled) setError(e.message)
      }
    }

    loadData()
    return () => { cancelled = true }
  }, [
    charactersApi,
    moduleId,
    modulesApi,
    setError,
    setForm,
    setModule,
    setOptions,
    setPartySize,
    setSelectedModule,
  ])

  const handleGenerateParty = useCallback(async (charId) => {
    setGeneratingParty(true)
    try {
      const result = await charactersApi.generateParty({
        module_id: moduleId,
        player_character_id: charId || savedCharId,
        party_size: partySize,
      })
      setLocalCompanions(result.companions)
      setCompanions(result.companions)
      setError('')
    } catch (e) {
      setError(`队伍生成失败: ${e.message}`)
    } finally {
      setGeneratingParty(false)
    }
  }, [
    charactersApi,
    moduleId,
    partySize,
    savedCharId,
    setCompanions,
    setError,
    setGeneratingParty,
    setLocalCompanions,
  ])

  const handleSaveAndContinue = useCallback(async () => {
    setSaving(true)
    setError('')
    try {
      const char = await charactersApi.create({
        module_id: moduleId,
        name: form.name,
        race: form.race,
        char_class: form.char_class,
        subclass: form.subclass || null,
        level: form.level,
        background: form.background || null,
        alignment: form.alignment,
        ability_scores: baseScores,
        proficient_skills: chosenSkills,
        known_spells: chosenSpells,
        cantrips: chosenCantrips,
        multiclass_info: buildMulticlassInfo(form),
        fighting_style: fightingStyle || null,
        equipment_choice: equipChoice,
        bonus_languages: bonusLanguages,
        feats: chosenFeats,
        ...buildNarrativePayload(narrative),
      })
      setSavedCharId(char.id)
      setPlayerCharacter(char)

      if (isMultiplayerCreate) {
        try {
          await roomsApi.claimChar(roomSessionId, char.id)
        } catch (e) {
          setError(`角色认领失败：${e?.message || '未知错误'}。角色已保存，请重试或联系管理员。`)
          return
        }
        navigate(`/room/${roomSessionId}`)
        return
      }

      setStep(partyStep)
      await handleGenerateParty(char.id)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }, [
    baseScores,
    bonusLanguages,
    charactersApi,
    chosenCantrips,
    chosenFeats,
    chosenSkills,
    chosenSpells,
    equipChoice,
    fightingStyle,
    form,
    handleGenerateParty,
    isMultiplayerCreate,
    moduleId,
    narrative,
    navigate,
    partyStep,
    roomSessionId,
    roomsApi,
    setError,
    setPlayerCharacter,
    setSavedCharId,
    setSaving,
    setStep,
  ])

  const handleStartAdventure = useCallback(async () => {
    setSaving(true)
    try {
      const result = await gameApi.createSession({
        module_id: moduleId,
        player_character_id: savedCharId,
        companion_ids: companions.map((companion) => companion.id),
        save_name: `${form.name}的冒险`,
      })
      setForgeTargetPath(`/adventure/${result.session_id}`)
      setForgeOpen(true)
      setError('')
    } catch (e) {
      setError(e.message)
      setSaving(false)
    }
  }, [
    companions,
    form.name,
    gameApi,
    moduleId,
    savedCharId,
    setError,
    setForgeOpen,
    setForgeTargetPath,
    setSaving,
  ])

  return {
    handleGenerateParty,
    handleSaveAndContinue,
    handleStartAdventure,
  }
}
