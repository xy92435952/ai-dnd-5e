import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { modulesApi, charactersApi, gameApi, roomsApi } from '../api/client'
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
import { DM_STYLES, DEFAULT_DM_STYLE, getDmStyle } from '../data/dmStyles'
import {
  SCORE_COSTS,
  buildCharacterCreateModel,
  normalizeCharacterOptions,
  pruneUnavailableChoices,
} from '../utils/characterCreate'

// ── 主组件 ────────────────────────────────────────────────
export default function CharacterCreate() {
  const { moduleId } = useParams()
  const navigate     = useNavigate()
  const [searchParams] = useSearchParams()
  // 多人模式：URL 含 ?roomSession=xxx 表示是从 Room 页进来的
  const roomSessionId = searchParams.get('roomSession') || null
  const isMultiplayerCreate = !!roomSessionId
  const { playerCharacter, setPlayerCharacter, setCompanions, setSelectedModule } = useGameStore()

  const [module,  setModule]  = useState(null)
  const [options, setOptions] = useState({
    races:[], classes:[], backgrounds:[], alignments:[],
    racial_bonuses:{}, class_skill_choices:{}, class_save_proficiencies:{}, all_skills:[],
    class_cantrips:{}, class_spells:{}, starting_cantrips_count:{}, starting_spells_count:{},
    spellcaster_classes:[],
  })
  const [step, setStep] = useState(1)

  const [form, setForm] = useState({
    name:'', race:'', char_class:'', subclass:'', level:1,
    background:'', alignment:'中立善良',
    multiclassEnabled:false, multiclass_class:'', multiclass_level:1,
  })
  const [scoreMethod,      setScoreMethod]      = useState('pointbuy')
  const [scores,           setScores]           = useState({ str:8,dex:8,con:8,int:8,wis:8,cha:8 })
  const [standardAssigned, setStandardAssigned] = useState({})
  const [chosenSkills,     setChosenSkills]     = useState([])
  const [chosenCantrips,   setChosenCantrips]   = useState([])
  const [chosenSpells,     setChosenSpells]     = useState([])

  // Phase 12 新增
  const [fightingStyle,   setFightingStyle]   = useState('')
  const [equipChoice,     setEquipChoice]     = useState(0)
  const [bonusLanguages,  setBonusLanguages]  = useState([])
  const [chosenFeats,     setChosenFeats]     = useState([])   // [{name:"Alert"}, ...]

  // 角色叙事字段（全部可选）
  // 价值：玩家断线被 AI 托管时，DM 据此代演不出戏；多人聊天时队友也按 personality 反应
  const [narrative, setNarrative] = useState({
    personality:        '',
    backstory:          '',
    speech_style:       '',
    combat_preference:  '',
    catchphrase:        '',
  })

  const [partySize,       setPartySize]       = useState(4)
  const [companions,      setLocalCompanions] = useState([])
  const [dmStyle,         setDmStyle]         = useState(DEFAULT_DM_STYLE)
  const [generatingParty, setGeneratingParty] = useState(false)
  const [savedCharId,     setSavedCharId]     = useState(null)
  const [saving,          setSaving]          = useState(false)
  const [error,           setError]           = useState('')
  // 传奇铸造仪式：创建完成"开始冒险"时弹出 → 4.2s 后 navigate
  const [forgeOpen,       setForgeOpen]       = useState(false)
  const [forgeTargetPath, setForgeTargetPath] = useState(null)

  const [modal, setModal] = useState({ type:'', itemKey:'' })
  const openModal  = (type, itemKey) => setModal({ type, itemKey })
  const closeModal = () => setModal({ type:'', itemKey:'' })

  useEffect(() => { loadData() }, [moduleId])
  useEffect(() => {
    setChosenSkills([]); setChosenCantrips([]); setChosenSpells([])
    setForm(f => ({ ...f, subclass:'' }))
  }, [form.char_class])

  const loadData = async () => {
    try {
      const [mod, opts] = await Promise.all([modulesApi.get(moduleId), charactersApi.options()])
      setModule(mod)
      setSelectedModule(mod)
      setOptions(normalizeCharacterOptions(opts))
      setForm(f => ({ ...f, level: mod.level_min || 1 }))
      setPartySize(mod.recommended_party_size || 4)
    } catch (e) { setError(e.message) }
  }

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
    asiLevels, asiCount, featStep, partyStep, styleStep,
    multiclassEnKey,
    multiReqs, multiReqMet, step1Valid, step2Valid, step3Valid, step4Valid,
    showSubclass, subclassOptions, steps: STEPS,
  } = model
  const availableCantripsKey = availableCantrips.join('\u0000')
  const availableSpellsKey = availableSpells.join('\u0000')

  useEffect(() => {
    setChosenCantrips((prev) => {
      const next = pruneUnavailableChoices(prev, availableCantrips, cantripCount)
      return next.length === prev.length && next.every((item, index) => item === prev[index]) ? prev : next
    })
  }, [availableCantripsKey, cantripCount])

  useEffect(() => {
    setChosenSpells((prev) => {
      const next = pruneUnavailableChoices(prev, availableSpells, spellCount)
      return next.length === prev.length && next.every((item, index) => item === prev[index]) ? prev : next
    })
  }, [availableSpellsKey, spellCount])

  const adjustScore = (ab, delta) => {
    const cur = scores[ab], next = cur + delta
    if (next < 8 || next > 15) return
    if (delta > 0 && (SCORE_COSTS[next]-SCORE_COSTS[cur]) > pointsLeft) return
    setScores(s => ({ ...s, [ab]: next }))
  }
  const assignStandard = (ab, idx) => {
    if (Object.entries(standardAssigned).some(([a,i]) => a!==ab && i===idx)) return
    setStandardAssigned(p => ({ ...p, [ab]: idx }))
  }

  const toggleSkill   = sk => setChosenSkills(p   => p.includes(sk) ? p.filter(x=>x!==sk) : p.length>=skillConfig.count ? p : [...p,sk])
  const toggleCantrip = nm => setChosenCantrips(p  => p.includes(nm) ? p.filter(x=>x!==nm) : p.length>=cantripCount ? p : [...p,nm])
  const toggleSpell   = nm => setChosenSpells(p    => p.includes(nm) ? p.filter(x=>x!==nm) : p.length>=spellCount   ? p : [...p,nm])

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
        dm_style: dmStyle,
      })
      // 先触发"传奇诞生"仪式（4.2s），结束后 navigate
      setForgeTargetPath(`/adventure/${result.session_id}`)
      setForgeOpen(true)
    } catch (e) {
      setError(e.message)
      setSaving(false)
    }
  }

  if (!module) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <p style={{ color: 'var(--gold)', animation: 'pulse 2s infinite' }}>加载模组信息...</p>
    </div>
  )

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
    styleStep,
    dmStyle,
    setDmStyle,
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
        <div className="create-header-main">
          <button
            className="btn-ghost"
            style={{ fontSize: 12, padding: '6px 12px', alignSelf: 'flex-start', marginTop: 4 }}
            onClick={() => navigate('/')}
          >⬅ 返回</button>
          <div className="create-header-copy">
            <div className="eyebrow">◈ 英雄铸造 · Character Forge ◈</div>
            <div
              className="display-title create-module-title"
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

      {step === styleStep && !isMultiplayerCreate && (
        <div className="step-pane">
          <div className="step-title">✦ 选择你的 DM 风格 ✦</div>
          <div className="step-sub">
            这个选择会在冒险创建时锁定，之后不能更改。它会影响叙事语气、节奏、选项设计和队友反应。
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 12,
            marginTop: 20,
          }}>
            {DM_STYLES.map(style => {
              const selected = dmStyle === style.key
              return (
                <button
                  key={style.key}
                  type="button"
                  onClick={() => setDmStyle(style.key)}
                  className="panel"
                  style={{
                    textAlign: 'left',
                    padding: 14,
                    cursor: 'pointer',
                    borderColor: selected ? style.accent : 'var(--bark-light)',
                    boxShadow: selected ? `inset 0 0 0 1px ${style.accent}, 0 0 18px -8px ${style.accent}` : 'none',
                    background: selected
                      ? `linear-gradient(180deg, ${style.accent}22, rgba(10,6,2,.45))`
                      : 'rgba(10,6,2,.35)',
                    minHeight: 118,
                  }}
                >
                  <div style={{
                    fontFamily: 'var(--font-heading)',
                    color: selected ? style.accent : 'var(--parchment)',
                    fontSize: 15,
                    letterSpacing: '.08em',
                    marginBottom: 8,
                  }}>{style.label}</div>
                  <div style={{
                    color: 'var(--parchment-dark)',
                    fontSize: 12,
                    lineHeight: 1.65,
                  }}>{style.summary}</div>
                </button>
              )
            })}
          </div>

          <div style={{
            marginTop: 18,
            padding: 12,
            border: '1px solid rgba(216,180,95,.28)',
            background: 'rgba(216,180,95,.06)',
            color: 'var(--parchment-dark)',
            fontSize: 12,
            lineHeight: 1.7,
          }}>
            当前选择：<b style={{ color: getDmStyle(dmStyle).accent }}>{getDmStyle(dmStyle).label}</b>
            <span style={{ marginLeft: 8 }}>{getDmStyle(dmStyle).summary}</span>
          </div>
        </div>
      )}

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
        {step === styleStep && !isMultiplayerCreate ? (
          // 单人：最后一步是选择 DM 风格 → 开始冒险
          <button
            className="btn-gold"
            disabled={!dmStyle || companions.length === 0 || generatingParty || saving}
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
