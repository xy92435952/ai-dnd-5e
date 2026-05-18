import React, { useEffect, useMemo } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { charactersApi } from '../api/characters'
import { gameApi } from '../api/game'
import { modulesApi } from '../api/modules'
import { roomsApi } from '../api/rooms'
import { useGameStore } from '../store/gameStore'
import Portrait from '../components/Portrait'
import { classKey } from '../components/Crests'
import LegendForge from '../components/LegendForge'
import {
  CharacterCreateInfoModal as InfoModal,
} from '../components/character-create/CharacterCreateShared'
import CharacterCreateStepBasics from '../components/character-create/CharacterCreateStepBasics'
import CharacterCreateStepAbilities from '../components/character-create/CharacterCreateStepAbilities'
import CharacterCreateStepSkills from '../components/character-create/CharacterCreateStepSkills'
import CharacterCreateStepEquipment from '../components/character-create/CharacterCreateStepEquipment'
import CharacterCreateStepSpells from '../components/character-create/CharacterCreateStepSpells'
import CharacterCreateStepFeats from '../components/character-create/CharacterCreateStepFeats'
import CharacterCreateStepParty from '../components/character-create/CharacterCreateStepParty'
import { useCharacterCreateState } from '../hooks/useCharacterCreateState'
import {
  buildCharacterCreateModel,
  normalizeCharacterOptions,
} from '../utils/characterCreate'
import { ErrorState, LoadingState } from '../components/feedback/AsyncState'

// ── 主组件 ────────────────────────────────────────────────
export default function CharacterCreate() {
  const { moduleId } = useParams()
  const navigate     = useNavigate()
  const [searchParams] = useSearchParams()
  // 多人模式：URL 含 ?roomSession=xxx 表示是从 Room 页进来的
  const roomSessionId = searchParams.get('roomSession') || null
  const isMultiplayerCreate = !!roomSessionId
  const { playerCharacter, setPlayerCharacter, setCompanions, setSelectedModule } = useGameStore()

  const state = useCharacterCreateState()

  const {
    module,
    setModule,
    options,
    setOptions,
    step,
    setStep,
    form,
    setForm,
    scoreMethod,
    setScoreMethod,
    scores,
    setScores,
    standardAssigned,
    setStandardAssigned,
    chosenSkills,
    setChosenSkills,
    chosenCantrips,
    setChosenCantrips,
    chosenSpells,
    setChosenSpells,
    fightingStyle,
    setFightingStyle,
    equipChoice,
    setEquipChoice,
    bonusLanguages,
    setBonusLanguages,
    chosenFeats,
    setChosenFeats,
    narrative,
    setNarrative,
    partySize,
    setPartySize,
    companions,
    setLocalCompanions,
    generatingParty,
    setGeneratingParty,
    savedCharId,
    setSavedCharId,
    saving,
    setSaving,
    error,
    setError,
    forgeOpen,
    setForgeOpen,
    forgeTargetPath,
    setForgeTargetPath,
    modal,
    openModal,
    closeModal,
    adjustScore,
    assignStandard,
    toggleSkill: toggleSkillState,
    toggleCantrip: toggleCantripState,
    toggleSpell: toggleSpellState,
  } = state

  useEffect(() => {
    let cancelled = false

    const loadData = async () => {
      try {
        const [mod, opts] = await Promise.all([modulesApi.get(moduleId), charactersApi.options()])
        if (cancelled) return
        setModule(mod)
        setSelectedModule(mod)
        setOptions(normalizeCharacterOptions(opts))
        setForm(f => ({ ...f, level: mod.level_min || 1 }))
        setPartySize(mod.recommended_party_size || 4)
      } catch (e) {
        if (!cancelled) setError(e.message)
      }
    }

    loadData()
    return () => { cancelled = true }
  }, [moduleId, setModule, setSelectedModule, setOptions, setForm, setPartySize, setError])

  const model = useMemo(() => buildCharacterCreateModel({
    form,
    options,
    scoreMethod,
    scores,
    standardAssigned,
    chosenSkills,
    chosenCantrips,
    chosenSpells,
    isMultiplayerCreate,
  }), [
    form,
    options,
    scoreMethod,
    scores,
    standardAssigned,
    chosenSkills,
    chosenCantrips,
    chosenSpells,
    isMultiplayerCreate,
  ])

  const {
    classEnKey, classInfo, raceEnKey, racialBonuses,
    baseScores, finalScores, pointsLeft,
    skillConfig, saveProfs, isSpellcaster, cantripCount, spellCount,
    availableCantrips, availableSpells, hasFightingStyle, needsASI,
    asiLevels, asiCount, featStep, partyStep,
    multiclassEnKey,
    multiReqs, multiReqMet, step1Valid, step2Valid, step3Valid, step4Valid,
    showSubclass, subclassOptions, steps: STEPS,
  } = model

  const toggleSkill = sk => toggleSkillState(sk, skillConfig.count)
  const toggleCantrip = nm => toggleCantripState(nm, cantripCount)
  const toggleSpell = nm => toggleSpellState(nm, spellCount)

  // ── 物品中文名查找 ─────────────────────────────────────
  const getItemZh = (name) => {
    const w = options.weapons?.[name]
    if (w?.zh) return w.zh
    const a = options.armor?.[name]
    if (a?.zh) return a.zh
    return name
  }

  // ── 保存角色 ───────────────────────────────────────────
  const handleSaveAndContinue = async () => {
    setSaving(true); setError('')
    try {
      const multiclassInfo = form.multiclassEnabled && form.multiclass_class
        ? { char_class: form.multiclass_class, level: form.multiclass_level } : null
      // 叙事字段：空串发 null 让后端识别"未填"
      const narrativePayload = {
        personality:       narrative.personality.trim()       || null,
        backstory:         narrative.backstory.trim()         || null,
        speech_style:      narrative.speech_style.trim()      || null,
        combat_preference: narrative.combat_preference.trim() || null,
        catchphrase:       narrative.catchphrase.trim()       || null,
      }
      const char = await charactersApi.create({
        module_id:         moduleId,
        name:              form.name,
        race:              form.race,
        char_class:        form.char_class,
        subclass:          form.subclass || null,
        level:             form.level,
        background:        form.background || null,
        alignment:         form.alignment,
        ability_scores:    baseScores,
        proficient_skills: chosenSkills,
        known_spells:      chosenSpells,
        cantrips:          chosenCantrips,
        multiclass_info:   multiclassInfo,
        fighting_style:    fightingStyle || null,
        equipment_choice:  equipChoice,
        bonus_languages:   bonusLanguages,
        feats:             chosenFeats,
        ...narrativePayload,
      })
      setSavedCharId(char.id)
      setPlayerCharacter(char)

      if (isMultiplayerCreate) {
        // 多人模式：角色创建完 → 认领到房间 → 返回房间页
        try {
          await roomsApi.claimChar(roomSessionId, char.id)
        } catch (e) {
          // 认领失败：保持在创角页并报错，避免用户回到房间看到"还需创建角色"
          setError(`角色认领失败：${e?.message || '未知错误'}。角色已保存，请重试或联系管理员。`)
          return
        }
        navigate(`/room/${roomSessionId}`)
        return
      }

      // 单人模式：继续生成队伍流程
      setStep(partyStep)
      await handleGenerateParty(char.id)
    } catch (e) { setError(e.message) }
    finally { setSaving(false) }
  }

  const handleGenerateParty = async (charId) => {
    setGeneratingParty(true)
    try {
      const result = await charactersApi.generateParty({
        module_id: moduleId, player_character_id: charId || savedCharId, party_size: partySize,
      })
      setLocalCompanions(result.companions)
      setCompanions(result.companions)
    } catch (e) { setError(`队伍生成失败: ${e.message}`) }
    finally { setGeneratingParty(false) }
  }

  const handleStartAdventure = async () => {
    setSaving(true)
    try {
      const result = await gameApi.createSession({
        module_id: moduleId, player_character_id: savedCharId,
        companion_ids: companions.map(c => c.id),
        save_name: `${form.name}的冒险`,
      })
      // 先触发"传奇诞生"仪式（4.2s），结束后 navigate
      setForgeTargetPath(`/adventure/${result.session_id}`)
      setForgeOpen(true)
    } catch (e) {
      setError(e.message)
      setSaving(false)
    }
  }

  if (!module) {
    return error
      ? <ErrorState error={error} fullScreen />
      : <LoadingState text="加载模组信息中…" />
  }

  const ctx = {
    module,
    step,
    STEPS,
    form,
    setForm,
    options,
    classEnKey,
    classInfo,
    raceEnKey,
    racialBonuses,
    baseScores,
    finalScores,
    pointsLeft,
    scoreMethod,
    setScoreMethod,
    scores,
    setScores,
    standardAssigned,
    setStandardAssigned,
    adjustScore,
    assignStandard,
    skillConfig,
    saveProfs,
    isSpellcaster,
    cantripCount,
    spellCount,
    availableCantrips,
    availableSpells,
    hasFightingStyle,
    needsASI,
    asiLevels,
    asiCount,
    featStep,
    partyStep,
    multiclassEnKey,
    multiReqs,
    multiReqMet,
    step1Valid,
    step2Valid,
    step3Valid,
    step4Valid,
    showSubclass,
    subclassOptions,
    openModal,
    closeModal,
    narrative,
    setNarrative,
    fightingStyle,
    setFightingStyle,
    equipChoice,
    setEquipChoice,
    bonusLanguages,
    setBonusLanguages,
    chosenFeats,
    setChosenFeats,
    chosenSkills,
    setChosenSkills,
    chosenCantrips,
    setChosenCantrips,
    chosenSpells,
    setChosenSpells,
    partySize,
    setPartySize,
    companions,
    generatingParty,
    error,
    setStep,
    savedCharId,
    saving,
    isMultiplayerCreate,
    getItemZh,
    toggleSkill,
    toggleCantrip,
    toggleSpell,
    handleGenerateParty,
    handleStartAdventure,
    handleSaveAndContinue,
    playerCharacter,
    setLocalCompanions,
    setSavedCharId,
  }

  return (
    <div className="create-scene" style={{ maxWidth: 980, margin: '0 auto', position: 'relative', zIndex: 1 }}>
      <LegendForge
        open={forgeOpen}
        name={form.name}
        cls={(classEnKey || 'paladin').toLowerCase()}
        classZh={form.char_class}
        raceZh={form.race}
        onDone={() => {
          setForgeOpen(false)
          if (forgeTargetPath) navigate(forgeTargetPath)
        }}
      />
      <InfoModal type={modal.type} itemKey={modal.itemKey} onClose={closeModal} />

      {/* 顶部 · 标题 + 英雄预览卡 */}
      <div className="create-header">
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <button
            className="btn-ghost"
            style={{ fontSize: 12, padding: '6px 12px', alignSelf: 'flex-start', marginTop: 4 }}
            onClick={() => navigate('/')}
          >⬅ 返回</button>
          <div>
            <div className="eyebrow">◈ 英雄铸造 · Character Forge ◈</div>
            <div
              className="display-title"
              style={{ fontSize: 22, letterSpacing: '.08em', marginTop: 2,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 420 }}
              title={module.name}
            >{module.name}</div>
            <p style={{ fontSize: 11, color: 'var(--parchment-dark)', margin: '2px 0 0', fontFamily: 'var(--font-mono)' }}>
              推荐等级 Lv {module.level_min}-{module.level_max}
            </p>
          </div>
        </div>

        {/* 右侧实时英雄预览 */}
        {form.char_class && (
          <div className="hero-preview">
            <Portrait cls={classKey(form.char_class)} size="md" />
            <div>
              <div className="name">{form.name || '未命名英雄'}</div>
              <div className="sub">{form.race || '—'} · {form.char_class || '—'} · Lv {form.level}</div>
              <div className="align">{form.alignment || ''}{form.background ? ` · ${form.background}` : ''}</div>
            </div>
          </div>
        )}
      </div>

      {/* 步骤指示器 · 新版 */}
      <div className="create-steps">
        {STEPS.map((label, i) => {
          const n = i + 1
          const done = step > n
          const cur = step === n
          return (
            <React.Fragment key={i}>
              <div className={`step-dot ${done ? 'done' : cur ? 'cur' : ''}`}>
                <div className="dot">{done ? '✓' : n}</div>
                <div className="lbl">{label}</div>
              </div>
              {i < STEPS.length - 1 && <div className={`step-line ${done ? 'done' : ''}`} />}
            </React.Fragment>
          )
        })}
      </div>

      {/* 主内容 · 羊皮纸卷轴 */}
      <div className="create-scroll">
        <div className="scroll-ornament top">✦ ❧ ✦</div>

      {error && (
        <div className="panel" style={{ padding: '12px', marginBottom: '16px', borderColor: 'var(--red)' }}>
          <p style={{ color: 'var(--red-light)', fontSize: '0.875rem', margin: 0 }}>! {error}</p>
        </div>
      )}

      {step === 1 && <CharacterCreateStepBasics ctx={ctx} />}
      {step === 2 && <CharacterCreateStepAbilities ctx={ctx} />}
      {step === 3 && <CharacterCreateStepSkills ctx={ctx} />}
      {step === 4 && <CharacterCreateStepEquipment ctx={ctx} />}
      {step === 5 && <CharacterCreateStepSpells ctx={ctx} />}
      {step === featStep && needsASI && <CharacterCreateStepFeats ctx={ctx} />}
      {step === partyStep && <CharacterCreateStepParty ctx={ctx} />}

        <div className="scroll-ornament bottom">✦ ❧ ✦</div>
      </div>{/* end create-scroll */}

      {/* 底部全局导航条 */}
      <div className="create-nav">
        <button
          className="btn-ghost"
          disabled={step === 1}
          onClick={() => setStep(s => Math.max(1, s - 1))}
        >◀ 上一步</button>
        <div className="step-counter">
          {step} / {STEPS.length}
          <span style={{
            marginLeft: 8, fontSize: 10,
            color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)',
          }}>
            {STEPS[step - 1] || ''}
          </span>
        </div>
        {step === partyStep && !isMultiplayerCreate ? (
          // 单人：最后一步是确认队伍 → 开始冒险
          <button
            className="btn-gold"
            disabled={companions.length === 0 || generatingParty || saving}
            onClick={handleStartAdventure}
            style={{ padding: '10px 28px', fontSize: 13, letterSpacing: '.18em' }}
          >{saving ? '✦ 准备中… ✦' : '✦ 开始冒险 ✦'}</button>
        ) : step === partyStep - 1 ? (
          // 倒数第二步 = "装备选择"（或施法的"法术选择"等）
          // 单人：触发创建 + 生成队伍
          // 多人：触发创建 + 认领到房间 + 返回房间页
          <button
            className="btn-gold"
            disabled={saving || !step1Valid || !step2Valid || !step3Valid || !step4Valid}
            onClick={handleSaveAndContinue}
            style={{ padding: '10px 20px', fontSize: 12, letterSpacing: '.12em' }}
          >{saving
            ? (isMultiplayerCreate ? '✦ 加入房间中… ✦' : '✦ 生成队伍中… ✦')
            : (isMultiplayerCreate ? '✦ 确认并返回房间 ✦' : '✦ 确认并生成队伍 ▶ ✦')
          }</button>
        ) : (
          <button
            className="btn-gold"
            onClick={() => setStep(s => Math.min(STEPS.length, s + 1))}
          >{STEPS[step] || '下一步'} ▶</button>
        )}
      </div>
    </div>
  )
}
