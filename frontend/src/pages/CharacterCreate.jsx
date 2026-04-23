import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { modulesApi, charactersApi, gameApi, roomsApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import {
  RACE_INFO, CLASS_INFO, SKILL_INFO, BACKGROUND_INFO,
  MULTICLASS_REQUIREMENTS, CLASS_ZH_TO_EN, ABILITY_ZH,
} from '../data/dnd5e.js'
import {
  BackIcon, ClassIcon, SwordIcon, ShieldIcon, WandIcon,
  BookIcon, ScrollIcon,
} from '../components/Icons'
import Portrait from '../components/Portrait'
import { classKey } from '../components/Crests'

// ── 常量 ──────────────────────────────────────────────────
const POINT_BUY_TOTAL = 27
const SCORE_COSTS    = { 8:0, 9:1, 10:2, 11:3, 12:4, 13:5, 14:7, 15:9 }
const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
const ABILITY_KEYS   = ['str','dex','con','int','wis','cha']

function modifier(score) { return Math.floor((score - 10) / 2) }
function modStr(n)        { return n >= 0 ? `+${n}` : `${n}` }

// ── 信息弹窗 ──────────────────────────────────────────────
function InfoModal({ type, itemKey, onClose }) {
  if (!itemKey || !type) return null
  let title = '', body = null

  if (type === 'race') {
    const info = RACE_INFO[itemKey]
    if (!info) return null
    title = `${info.zh}`
    body = (
      <>
        <p style={{ color: 'var(--text)', opacity: 0.75, fontSize: '0.875rem', lineHeight: 1.7, marginBottom: '0.75rem' }}>{info.description}</p>
        <div style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
          <span className="tag tag-info">速度 {info.speed}尺</span>
          <span className="tag tag-info">体型 {info.size}</span>
        </div>
        <p style={{ color: 'var(--gold)', fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '0.4rem' }}>种族特性</p>
        {info.traits.map((t, i) => (
          <div key={i} style={{ marginBottom: '0.4rem', paddingLeft: '0.6rem', borderLeft: '2px solid var(--wood-light)' }}>
            <span style={{ color: 'var(--text-bright)', fontSize: '0.85rem', fontWeight: 600 }}>{t.name}：</span>
            <span style={{ color: 'var(--text)', opacity: 0.65, fontSize: '0.8rem' }}>{t.desc}</span>
          </div>
        ))}
        <div style={{ marginTop: '0.75rem', padding: '0.6rem', borderRadius: '0.4rem',
          background: 'rgba(42,90,42,0.12)', border: '1px solid var(--green)' }}>
          <p style={{ color: 'var(--green-light)', fontSize: '0.8rem' }}>提示：{info.playstyle}</p>
        </div>
      </>
    )
  } else if (type === 'class') {
    const info = CLASS_INFO[itemKey]
    if (!info) return null
    title = `${info.zh}`
    body = (
      <>
        <div style={{ marginBottom: '0.6rem', display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
          <span className="tag tag-level">生命骰 {info.hit_die}</span>
          <span className="tag tag-ok">{info.primary_ability}</span>
        </div>
        <p style={{ color: 'var(--text)', opacity: 0.75, fontSize: '0.875rem', lineHeight: 1.7, marginBottom: '0.6rem' }}>{info.description}</p>
        <p style={{ color: 'var(--text-dim)', fontSize: '0.75rem', marginBottom: '0.75rem' }}>
          护甲: {info.armor} | 武器: {info.weapons}
        </p>
        <p style={{ color: 'var(--gold)', fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '0.4rem' }}>职业特性</p>
        {info.features.map((f, i) => (
          <div key={i} style={{ marginBottom: '0.35rem', paddingLeft: '0.6rem', borderLeft: '2px solid var(--wood-light)' }}>
            <span style={{ color: 'var(--gold)', fontSize: '0.72rem', opacity: 0.8 }}>Lv{f.level} </span>
            <span style={{ color: 'var(--text-bright)', fontSize: '0.82rem', fontWeight: 600 }}>{f.name}：</span>
            <span style={{ color: 'var(--text)', opacity: 0.65, fontSize: '0.78rem' }}>{f.desc}</span>
          </div>
        ))}
        {info.subclasses?.length > 0 && (
          <>
            <p style={{ color: 'var(--gold)', fontSize: '0.8rem', fontWeight: 'bold', margin: '0.75rem 0 0.4rem' }}>
              {info.subclass_label}（{info.subclass_unlock}级解锁）
            </p>
            {info.subclasses.map((s, i) => (
              <div key={i} style={{ marginBottom: '0.35rem', paddingLeft: '0.6rem', borderLeft: '2px solid var(--wood-light)' }}>
                <span style={{ color: 'var(--text-bright)', fontSize: '0.82rem', fontWeight: 600 }}>{s.zh}：</span>
                <span style={{ color: 'var(--text)', opacity: 0.65, fontSize: '0.78rem' }}>{s.description}</span>
              </div>
            ))}
          </>
        )}
      </>
    )
  } else if (type === 'skill') {
    const info = SKILL_INFO[itemKey]
    if (!info) return null
    title = `${itemKey}（${info.en}）`
    body = (
      <>
        <span className="tag tag-level" style={{ marginBottom: '0.75rem', display: 'inline-flex' }}>
          关联属性：{ABILITY_ZH[info.ability] || info.ability}
        </span>
        <p style={{ color: 'var(--text)', opacity: 0.75, fontSize: '0.875rem', lineHeight: 1.7 }}>{info.desc}</p>
      </>
    )
  } else if (type === 'background') {
    const info = BACKGROUND_INFO[itemKey]
    if (!info) return null
    title = `${info.zh}`
    body = <p style={{ color: 'var(--text)', opacity: 0.75, fontSize: '0.875rem', lineHeight: 1.7 }}>{info.desc}</p>
  }

  if (!body) return null
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 999,
      background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(2px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem',
    }} onClick={onClose}>
      <div className="panel" style={{
        padding: '1.5rem', maxWidth: '480px', width: '100%', maxHeight: '80vh',
        overflowY: 'auto', position: 'relative',
      }} onClick={e => e.stopPropagation()}>
        <h3 style={{ color: 'var(--gold)', fontSize: '1.1rem', fontWeight: 'bold',
          marginBottom: '1rem', paddingRight: '2rem' }}>{title}</h3>
        {body}
        <button onClick={onClose} style={{
          position: 'absolute', top: '0.75rem', right: '0.75rem',
          background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: '1.1rem',
        }}>&#x2715;</button>
      </div>
    </div>
  )
}

function InfoBtn({ onClick }) {
  return (
    <button onClick={onClick} title="查看详情" style={{
      background: 'rgba(201,168,76,0.1)', border: '1px solid rgba(201,168,76,0.3)',
      borderRadius: '50%', width: '20px', height: '20px', color: 'var(--gold)',
      fontSize: '0.7rem', cursor: 'pointer', flexShrink: 0,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    }}>&#x2139;</button>
  )
}

// ── 主组件 ────────────────────────────────────────────────
export default function CharacterCreate() {
  const { moduleId } = useParams()
  const navigate     = useNavigate()
  const [searchParams] = useSearchParams()
  // 多人模式：URL 含 ?roomSession=xxx 表示是从 Room 页进来的
  const roomSessionId = searchParams.get('roomSession') || null
  const isMultiplayerCreate = !!roomSessionId
  const { setPlayerCharacter, setCompanions, setSelectedModule } = useGameStore()

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

  const [partySize,       setPartySize]       = useState(4)
  const [companions,      setLocalCompanions] = useState([])
  const [generatingParty, setGeneratingParty] = useState(false)
  const [savedCharId,     setSavedCharId]     = useState(null)
  const [saving,          setSaving]          = useState(false)
  const [error,           setError]           = useState('')

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
      setOptions(opts)
      setForm(f => ({ ...f, level: mod.level_min || 1 }))
      setPartySize(mod.recommended_party_size || 4)
    } catch (e) { setError(e.message) }
  }

  // ── 职业/种族 键值 ─────────────────────────────────────
  const classEnKey = CLASS_ZH_TO_EN[form.char_class] || form.char_class
  const classInfo  = CLASS_INFO[classEnKey] || null
  // 种族键可能是英文或中文，在 RACE_INFO 中查找
  const raceEnKey  = Object.keys(RACE_INFO).find(k =>
    k === form.race || RACE_INFO[k]?.zh === form.race
  ) || ''

  // ── 种族加值 ───────────────────────────────────────────
  const racialBonuses = useMemo(() => (
    options.racial_bonuses[form.race] || {}
  ), [form.race, options.racial_bonuses])

  function standardScores() {
    const r = {}
    for (const k of ABILITY_KEYS) {
      const idx = standardAssigned[k]
      r[k] = idx !== undefined ? STANDARD_ARRAY[idx] : 8
    }
    return r
  }

  const baseScores  = scoreMethod === 'pointbuy' ? scores : standardScores()
  const finalScores = useMemo(() => {
    const r = { ...baseScores }
    for (const [k,v] of Object.entries(racialBonuses)) r[k] = (r[k] || 8) + v
    return r
  }, [baseScores, racialBonuses])

  // ── 点数购买 ───────────────────────────────────────────
  const pointsSpent = Object.values(scores).reduce((s,v) => s + (SCORE_COSTS[v]||0), 0)
  const pointsLeft  = POINT_BUY_TOTAL - pointsSpent

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

  // ── 技能 / 施法 ────────────────────────────────────────
  const skillConfig = useMemo(() => (
    options.class_skill_choices[form.char_class] ||
    options.class_skill_choices[classEnKey] ||
    { count:2, options: options.all_skills || [] }
  ), [form.char_class, classEnKey, options.class_skill_choices, options.all_skills])

  const saveProfs = useMemo(() => (
    options.class_save_proficiencies[form.char_class] ||
    options.class_save_proficiencies[classEnKey] || []
  ), [form.char_class, classEnKey, options.class_save_proficiencies])

  const isSpellcaster     = !!(options.spellcaster_classes?.includes(classEnKey))
  const cantripCount      = options.starting_cantrips_count?.[classEnKey] || 0
  const spellCount        = options.starting_spells_count?.[classEnKey]  || 0
  const availableCantrips = options.class_cantrips?.[classEnKey] || []
  const availableSpells   = options.class_spells?.[classEnKey]   || []

  // Phase 12: 动态步骤计算
  const hasFightingStyle  = !!(options.fighting_style_classes?.[classEnKey] && form.level >= (options.fighting_style_classes[classEnKey]?.level || 99))
  const needsASI          = form.level >= 4
  const asiLevels         = classEnKey === 'Fighter' ? (options.asi_levels_fighter || [4,6,8,12,14,16,19]) :
                            classEnKey === 'Rogue' ? (options.asi_levels_rogue || [4,8,10,12,16,19]) :
                            (options.asi_levels || [4,8,12,16,19])
  const asiCount          = asiLevels.filter(l => form.level >= l).length

  // 装备步骤始终存在 (step 4)
  // 法术步骤仅施法职业 (step 5 if caster)
  // 专长步骤仅 lv4+ (step 5/6)
  const spellStep         = isSpellcaster ? 5 : -1
  const featStep          = needsASI ? (isSpellcaster ? 6 : 5) : -1
  const partyStep         = (featStep > 0 ? featStep : (spellStep > 0 ? spellStep : 4)) + 1

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

  // ── 子职业 ─────────────────────────────────────────────
  const showSubclass    = !!(classInfo && form.level >= classInfo.subclass_unlock)
  const subclassOptions = classInfo?.subclasses || []

  // ── 双职业 ─────────────────────────────────────────────
  const multiclassEnKey = CLASS_ZH_TO_EN[form.multiclass_class] || form.multiclass_class
  const multiReqs       = MULTICLASS_REQUIREMENTS[multiclassEnKey] || {}
  const multiReqMet     = Object.entries(multiReqs).every(([ab,min]) => (finalScores[ab]||0) >= min)

  // ── 步骤验证 ───────────────────────────────────────────
  const step1Valid = !!(form.name.trim() && form.race && form.char_class &&
    (!form.multiclassEnabled || (form.multiclass_class && multiReqMet)))
  const step2Valid = scoreMethod === 'pointbuy' ? true : Object.keys(standardAssigned).length === 6
  const step3Valid = chosenSkills.length === skillConfig.count
  const step4Valid = chosenCantrips.length === cantripCount && chosenSpells.length === spellCount

  // ── 保存角色 ───────────────────────────────────────────
  const handleSaveAndContinue = async () => {
    setSaving(true); setError('')
    try {
      const multiclassInfo = form.multiclassEnabled && form.multiclass_class
        ? { char_class: form.multiclass_class, level: form.multiclass_level } : null
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
      navigate(`/adventure/${result.session_id}`)
    } catch (e) { setError(e.message) }
    finally { setSaving(false) }
  }

  if (!module) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <p style={{ color: 'var(--gold)', animation: 'pulse 2s infinite' }}>加载模组信息...</p>
    </div>
  )

  const STEPS = (() => {
    const s = ['基础信息', '能力值', '技能熟练', '装备选择']
    if (isSpellcaster) s.push('法术选择')
    if (needsASI) s.push('专长/属性提升')
    // 多人模式：不需要 AI 生成队伍，最后一步是"回到房间"
    s.push(isMultiplayerCreate ? '加入房间' : '确认队伍')
    return s
  })()

  return (
    <div className="create-scene" style={{ maxWidth: 980, margin: '0 auto', position: 'relative', zIndex: 1 }}>
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

      {/* ══ Step 1: 基础信息 ══ */}
      {step === 1 && (
        <div className="step-pane">
          <div className="step-title">✧ 第一章 · 身世与血脉 ✧</div>
          <div className="step-sub">姓名决定传说，血脉决定起点，职业决定道路。</div>

          <div className="create-field">
            <label className="lbl">英雄之名</label>
            <input className="input-fantasy"
              placeholder="输入你的名字…" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          </div>

          {/* 种族 · 卡片网格 */}
          <div className="create-field">
            <label className="lbl">血脉 · 种族</label>
            <div className="race-grid">
              {options.races.map(r => {
                const sel = form.race === r
                const enKey = Object.keys(RACE_INFO).find(k => RACE_INFO[k].zh === r) || r
                const info = RACE_INFO[enKey]
                const bonus = options.racial_ability_bonuses?.[r] || options.racial_ability_bonuses?.[enKey] || {}
                return (
                  <div key={r}
                    className={`race-card ${sel ? 'sel' : ''}`}
                    onClick={() => setForm(f => ({ ...f, race: r }))}>
                    <div className="race-name">{r}</div>
                    <div className="race-meta">{info?.size || '—'} · 速度 {info?.speed || 30}</div>
                    {Object.keys(bonus).length > 0 && (
                      <div className="race-bonus">
                        {Object.entries(bonus).map(([k, v]) => (
                          <span key={k}>{ABILITY_ZH[k] || k} +{v}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
            {form.race && RACE_INFO[raceEnKey]?.description && (
              <div className="hint"><em>"{RACE_INFO[raceEnKey].description.slice(0, 80)}…"</em>
                {raceEnKey && (
                  <button
                    onClick={() => openModal('race', raceEnKey)}
                    style={{ marginLeft: 6, background: 'none', border: 'none',
                      color: 'var(--amber)', cursor: 'pointer', fontSize: 11 }}
                  >【详情】</button>
                )}
              </div>
            )}
          </div>

          {/* 职业 · 纹章卡片网格 */}
          <div className="create-field">
            <label className="lbl">使命 · 职业</label>
            <div className="class-grid">
              {options.classes.map(c => {
                const sel = form.char_class === c
                const enKey = CLASS_ZH_TO_EN[c] || c
                const info = CLASS_INFO[enKey]
                return (
                  <div key={c}
                    className={`class-card ${sel ? 'sel' : ''}`}
                    onClick={() => setForm(f => ({ ...f, char_class: c, subclass: '' }))}>
                    <Portrait cls={classKey(c)} size="sm" style={{ margin: '0 auto 6px' }} />
                    <div className="class-name">{c}</div>
                    <div className="class-prim">{info?.primary_ability || info?.hit_die ? `d${info.hit_die}` : ''}</div>
                  </div>
                )
              })}
            </div>
            {classInfo && (
              <div className="class-details">
                <div className="row">
                  <span className="tag tag-gold">生命骰 d{classInfo.hit_die}</span>
                  <span className="tag">主属性 {classInfo.primary_ability}</span>
                  {saveProfs.length > 0 && (
                    <span className="tag">豁免 {saveProfs.map(k => ABILITY_ZH[k] || k).join('/')}</span>
                  )}
                </div>
                {classInfo.description && (
                  <p className="desc"><em>"{classInfo.description.slice(0, 120)}"</em></p>
                )}
                <div className="row-muted">
                  {classInfo.armor_proficiency && `护甲：${classInfo.armor_proficiency}`}
                  {classEnKey && (
                    <button
                      onClick={() => openModal('class', classEnKey)}
                      style={{ marginLeft: 10, background: 'none', border: 'none',
                        color: 'var(--amber)', cursor: 'pointer', fontSize: 11 }}
                    >【完整特性】</button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 子职业 · 胶囊 */}
          {showSubclass && subclassOptions.length > 0 && (
            <div className="create-field">
              <label className="lbl">
                {classInfo.subclass_label}（Lv{classInfo.subclass_unlock} 解锁）
              </label>
              <div className="sub-grid">
                {subclassOptions.map(sc => {
                  const sel = form.subclass === sc.name
                  return (
                    <div key={sc.name}
                      className={`sub-chip ${sel ? 'sel' : ''}`}
                      onClick={() => setForm(f => ({ ...f, subclass: sel ? '' : sc.name }))}>
                      {sc.zh}
                    </div>
                  )
                })}
              </div>
              {!form.subclass && (
                <div className="hint">可跳过，稍后决定</div>
              )}
            </div>
          )}

          {/* 战斗风格 */}
          {hasFightingStyle && (
            <div className="create-field">
              <label className="lbl">战斗风格</label>
              <div className="fstyle-grid">
                {(options.fighting_style_classes?.[classEnKey]?.styles || []).map(style => {
                  const sel = fightingStyle === style
                  const info = options.fighting_styles?.[style] || {}
                  return (
                    <div key={style}
                      className={`fstyle-card ${sel ? 'sel' : ''}`}
                      onClick={() => setFightingStyle(sel ? '' : style)}>
                      <div className="n">{info.zh || style}</div>
                      <div className="d">{info.desc}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

            {/* 等级 + 阵营 */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Field label="等级（1--20）">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <input type="range" min={1} max={20} value={form.level}
                      onChange={e => setForm(f => ({ ...f, level: +e.target.value }))}
                      style={{ flex: 1, accentColor: 'var(--gold)' }} />
                    <span style={{ fontSize: '1.25rem', fontWeight: 'bold', width: '32px', textAlign: 'center', color: 'var(--gold)' }}>
                      {form.level}
                    </span>
                  </div>
                  <p style={{
                    fontSize: '0.75rem', marginTop: '4px',
                    color: form.level>=module.level_min && form.level<=module.level_max ? 'var(--green-light)' : 'var(--text-dim)',
                  }}>
                    {form.level>=module.level_min && form.level<=module.level_max
                      ? `\u2713 推荐范围 ${module.level_min}--${module.level_max}`
                      : `推荐 Lv${module.level_min}--${module.level_max}`}
                  </p>
                </div>
              </Field>
              <Field label="阵营">
                <Select value={form.alignment} options={options.alignments} placeholder="选择阵营"
                  onChange={v => setForm(f => ({ ...f, alignment: v }))} />
              </Field>
            </div>

            <Field label="背景（可选）">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Select value={form.background} options={options.backgrounds} placeholder="选择背景"
                  onChange={v => setForm(f => ({ ...f, background: v }))} />
                {form.background && BACKGROUND_INFO[form.background] && (
                  <InfoBtn onClick={() => openModal('background', form.background)} />
                )}
              </div>
            </Field>

            {/* 双职业 */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', userSelect: 'none' }}
                onClick={() => setForm(f => ({ ...f, multiclassEnabled: !f.multiclassEnabled }))}>
                <div style={{
                  width: '16px', height: '16px', borderRadius: '3px',
                  border: `1px solid ${form.multiclassEnabled ? 'var(--gold)' : 'var(--wood-light)'}`,
                  background: form.multiclassEnabled ? 'rgba(201,168,76,0.2)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.75rem', color: 'var(--gold)',
                }}>
                  {form.multiclassEnabled && '\u2713'}
                </div>
                <span style={{ fontSize: '0.875rem', color: form.multiclassEnabled ? 'var(--gold)' : 'var(--text-dim)' }}>
                  启用双职业
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', opacity: 0.5 }}>（可选）</span>
              </div>

              {form.multiclassEnabled && (
                <div style={{
                  marginTop: '12px', padding: '12px', borderRadius: '6px',
                  border: '1px solid var(--wood-light)', background: 'rgba(201,168,76,0.04)',
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                    <Field label="第二职业">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Select value={form.multiclass_class}
                          options={options.classes.filter(c => c !== form.char_class)}
                          placeholder="选择职业"
                          onChange={v => setForm(f => ({ ...f, multiclass_class: v }))} />
                        {multiclassEnKey && CLASS_INFO[multiclassEnKey] && (
                          <InfoBtn onClick={() => openModal('class', multiclassEnKey)} />
                        )}
                      </div>
                    </Field>
                    <Field label="副职等级">
                      <input type="number" min={1} max={Math.max(1, 20 - form.level)}
                        value={form.multiclass_level}
                        onChange={e => setForm(f => ({ ...f, multiclass_level: +e.target.value || 1 }))}
                        className="input-fantasy"
                        style={{ textAlign: 'center' }} />
                    </Field>
                  </div>
                  {form.multiclass_class && Object.keys(multiReqs).length > 0 && (
                    <div style={{
                      fontSize: '0.75rem', padding: '8px', borderRadius: '6px',
                      background: multiReqMet ? 'rgba(42,90,42,0.12)' : 'rgba(139,32,32,0.12)',
                      border: `1px solid ${multiReqMet ? 'var(--green)' : 'var(--red)'}`,
                    }}>
                      <span style={{ color: multiReqMet ? 'var(--green-light)' : 'var(--red-light)' }}>
                        {multiReqMet ? '\u2713 已满足' : '\u2717 未满足'} 入门要求：
                      </span>
                      {Object.entries(multiReqs).map(([ab,min]) => {
                        const met = (finalScores[ab]||0) >= min
                        return (
                          <span key={ab} style={{ marginLeft: '8px', color: met ? 'var(--green-light)' : 'var(--red-light)' }}>
                            {ABILITY_ZH[ab]||ab}&gt;={min}（当前{finalScores[ab]||8}）
                          </span>
                        )
                      })}
                    </div>
                  )}
                  {!form.multiclass_class && (
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', opacity: 0.5 }}>选择第二职业后将显示入门属性要求</p>
                  )}
                </div>
              )}
            </div>

        </div>
      )}

      {/* ══ Step 2: 能力值 ══ */}
      {step === 2 && (
        <div className="step-pane">
          <div className="step-title">✧ 第二章 · 天赋与禀性 ✧</div>
          <div className="step-sub">六项能力决定你能做什么、擅长什么。</div>

          {/* 方法切换 · 大按钮 */}
          <div className="method-tabs">
            {[
              ['pointbuy', '点数购买', `更自由 · ${POINT_BUY_TOTAL} 点`],
              ['standard', '标准数组', `经典 · ${STANDARD_ARRAY.join('/')}`],
            ].map(([k, n, d]) => (
              <div key={k}
                className={`method-tab ${scoreMethod === k ? 'sel' : ''}`}
                onClick={() => { setScoreMethod(k); setStandardAssigned({}) }}>
                <div className="n">{n}</div>
                <div className="d">{d}</div>
              </div>
            ))}
          </div>

          {/* 点数进度条 */}
          {scoreMethod === 'pointbuy' && (
            <div className="points-bar">
              <div className="label">剩余点数</div>
              <div className="points-big" style={{ color: pointsLeft === 0 ? 'var(--emerald-light)' : 'var(--amber)' }}>
                {pointsLeft}
              </div>
              <div className="track">
                <div className="fill" style={{
                  width: `${((POINT_BUY_TOTAL - pointsLeft) / POINT_BUY_TOTAL) * 100}%`,
                  background: pointsLeft === 0 ? 'var(--emerald-light)' : 'var(--gold-gradient)',
                }} />
              </div>
              <div className="label">
                {pointsLeft === 0 ? '✓ 已分配完毕' : `${POINT_BUY_TOTAL - pointsLeft} / ${POINT_BUY_TOTAL}`}
              </div>
            </div>
          )}

          {/* 六项能力 · 牌匾 */}
          <div className="ability-grid">
            {ABILITY_KEYS.map(key => {
              const base  = baseScores[key]
              const bonus = racialBonuses[key] || 0
              const final = finalScores[key]
              const mod   = modifier(final)
              return (
                <div key={key} className="ability-plaque">
                  <div className="plaque-top">
                    <div className="ab-name">{ABILITY_ZH[key] || key}</div>
                    <div className="ab-key">{key.toUpperCase()}</div>
                  </div>
                  <div className="plaque-main">
                    <div className="score">{final}</div>
                    <div className="mod">{modStr(mod)}</div>
                  </div>
                  {bonus > 0 && (
                    <div className="bonus-badge">基础 {base} · 种族 +{bonus}</div>
                  )}
                  {scoreMethod === 'pointbuy' && (
                    <div className="adj">
                      <button onClick={() => adjustScore(key, -1)} disabled={base <= 8}>−</button>
                      <div className="val">{base}</div>
                      <button onClick={() => adjustScore(key, 1)}
                        disabled={base >= 15 || pointsLeft < (SCORE_COSTS[base + 1] - SCORE_COSTS[base])}>+</button>
                    </div>
                  )}
                  {scoreMethod === 'standard' && (
                    <div className="array-row">
                      {STANDARD_ARRAY.map((v, idx) => {
                        const used = Object.entries(standardAssigned).some(([a, i]) => a !== key && i === idx)
                        const sel = standardAssigned[key] === idx
                        return (
                          <button key={idx}
                            disabled={used}
                            className={`arr ${sel ? 'sel' : ''}`}
                            onClick={() => assignStandard(key, idx)}>
                            {v}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* 派生属性预览 · 条带 */}
          {form.char_class && (() => {
            const prof = 2 + Math.floor((form.level - 1) / 4)
            const conMod = modifier(finalScores.con || 10)
            const dexMod = modifier(finalScores.dex || 10)
            const strMod = modifier(finalScores.str || 10)
            const hitDie = CLASS_INFO[classEnKey]?.hit_die || 8
            const hp = hitDie + conMod + Math.max(0, form.level - 1) * (Math.floor(hitDie / 2) + 1 + conMod)
            return (
              <div className="derived-row">
                <div className="der"><div className="t">最大生命</div><div className="v">{Math.max(1, hp)}</div></div>
                <div className="der"><div className="t">先攻</div><div className="v">{modStr(dexMod)}</div></div>
                <div className="der"><div className="t">熟练</div><div className="v">+{prof}</div></div>
                <div className="der"><div className="t">攻击</div><div className="v">{modStr(prof + Math.max(strMod, dexMod))}</div></div>
                <div className="der"><div className="t">AC</div><div className="v">{10 + dexMod}</div></div>
              </div>
            )
          })()}

            {/* 双职业要求提示（在能力值页也显示） */}
            {form.multiclassEnabled && form.multiclass_class && Object.keys(multiReqs).length > 0 && (
              <div style={{
                fontSize: '0.75rem', padding: '8px', borderRadius: '6px',
                background: multiReqMet ? 'rgba(42,90,42,0.12)' : 'rgba(139,32,32,0.12)',
                border: `1px solid ${multiReqMet ? 'var(--green)' : 'var(--red)'}`,
              }}>
                <span style={{ color: multiReqMet ? 'var(--green-light)' : 'var(--red-light)' }}>
                  双职业（{CLASS_INFO[multiclassEnKey]?.zh || form.multiclass_class}）要求：
                </span>
                {Object.entries(multiReqs).map(([ab,min]) => {
                  const met = (finalScores[ab]||0) >= min
                  return (
                    <span key={ab} style={{ marginLeft: '8px', color: met ? 'var(--green-light)' : 'var(--red-light)' }}>
                      {ABILITY_ZH[ab]||ab}&gt;={min}（{finalScores[ab]||8}）
                    </span>
                  )
                })}
              </div>
            )}

        </div>
      )}

      {/* ══ Step 3: 技能熟练 ══ */}
      {step === 3 && (
        <div className="step-pane">
          <div className="step-title">✧ 第三章 · 所学所长 ✧</div>
          <div className="step-sub">
            {form.char_class} 可选择 <b style={{ color: 'var(--amber)' }}>{skillConfig.count}</b> 项技能熟练 · 已选{' '}
            <b style={{ color: chosenSkills.length === skillConfig.count ? 'var(--emerald-light)' : 'var(--amber)' }}>
              {chosenSkills.length}
            </b>
          </div>

          {/* 豁免熟练提示 */}
          {saveProfs.length > 0 && (
            <div className="create-note">
              <span className="lead">职业豁免熟练</span>
              （由 {form.char_class} 自动获得）：
              {saveProfs.map(k => ABILITY_ZH[k] || k).join(' · ')}
            </div>
          )}

          {/* 技能 · 4 列网格 */}
          <div className="skill-grid">
            {skillConfig.options.map(skill => {
              const sel = chosenSkills.includes(skill)
              const dis = !sel && chosenSkills.length >= skillConfig.count
              const skillData = SKILL_INFO[skill]
              return (
                <div key={skill}
                  className={`skill-card ${sel ? 'sel' : ''} ${dis ? 'dis' : ''}`}
                  onClick={() => !dis && toggleSkill(skill)}>
                  <div className="s-check">{sel ? '✓' : '○'}</div>
                  <div className="s-name">
                    {skill}
                    {skillData && (
                      <button
                        type="button"
                        onClick={e => { e.stopPropagation(); openModal('skill', skill) }}
                        style={{
                          marginLeft: 6, background: 'none', border: 'none',
                          color: 'var(--amber)', cursor: 'pointer', fontSize: 10,
                          padding: 0,
                        }}
                      >ⓘ</button>
                    )}
                  </div>
                  <div className="s-ab">{ABILITY_ZH[skillData?.ability] || skillData?.ability || ''}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ══ Step 4: 装备选择 ══ */}
      {step === 4 && (
        <div className="step-pane">
          <div className="step-title">✧ 第四章 · 起始装备 ✧</div>
          <div className="step-sub">这是你踏上旅程时所携之物。</div>

          {/* 装备方案 · 大卡片 */}
          <div className="equip-list">
            {(options.starting_equipment?.[classEnKey] || []).map((opt, idx) => {
              const sel = equipChoice === idx
              return (
                <div key={idx}
                  className={`equip-card ${sel ? 'sel' : ''}`}
                  onClick={() => setEquipChoice(idx)}>
                  <div className="equip-head">
                    <div className={`radio ${sel ? 'on' : ''}`}>{sel && <div className="dot" />}</div>
                    <div className="equip-name">{opt.label}</div>
                  </div>
                  <div className="equip-items">
                    {opt.items.map((item, j) => {
                      const glyph = item.slot === 'weapon' ? '⚔' :
                                    item.slot === 'armor' ? '🛡' :
                                    item.slot === 'offhand' ? '◈' : '◇'
                      return (
                        <span key={j} className="item-chip">
                          {glyph} {getItemZh(item.name)}
                        </span>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>

          {/* 背景特性 · 金边卡 */}
          {form.background && options.background_features?.[form.background] && (
            <div className="bg-feat">
              <div className="bf-title">◈ 背景特性 · {options.background_features[form.background].feature} ◈</div>
              <div className="bf-desc">
                {options.background_features[form.background].feature_desc}
              </div>
              <div className="bf-tags">
                {(options.background_features[form.background].skills || []).map(s => (
                  <span key={s} className="tag tag-gold">⚔ {s}</span>
                ))}
                {(options.background_features[form.background].tools || []).map(t => (
                  <span key={t} className="tag">◈ {t}</span>
                ))}
                {options.background_features[form.background].languages > 0 && (
                  <span className="tag">◈ 额外语言 × {options.background_features[form.background].languages}</span>
                )}
              </div>
            </div>
          )}

            {/* 语言选择（如有额外名额） */}
            {(() => {
              const raceLang = options.racial_languages?.[form.race] || { fixed: ['Common'], bonus: 0 }
              const bgLangBonus = options.background_features?.[form.background]?.languages || 0
              const totalBonus = raceLang.bonus + bgLangBonus
              if (totalBonus <= 0) return null
              const fixed = raceLang.fixed || []
              const available = (options.all_languages || []).filter(l => !fixed.includes(l) && !bonusLanguages.includes(l))
              return (
                <div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-bright)', marginBottom: '6px' }}>
                    额外语言选择（{bonusLanguages.length}/{totalBonus}）
                  </p>
                  <p style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginBottom: '8px' }}>
                    种族固定语言：{fixed.join('、')}
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {available.map(lang => {
                      const sel = bonusLanguages.includes(lang)
                      return (
                        <button key={lang} className="skill-btn"
                          style={{
                            borderColor: sel ? 'var(--gold)' : 'var(--wood-light)',
                            background: sel ? 'rgba(201,168,76,0.2)' : undefined,
                            color: sel ? 'var(--gold)' : 'var(--text-dim)',
                          }}
                          onClick={() => setBonusLanguages(prev =>
                            prev.includes(lang) ? prev.filter(l => l !== lang) :
                            prev.length >= totalBonus ? prev : [...prev, lang]
                          )}>
                          {sel && '\u2713 '}{lang}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )
            })()}

        </div>
      )}

      {/* ══ Step 5: 法术选择（施法职业）══ */}
      {step === 5 && isSpellcaster && (
        <div className="step-pane">
          <div className="step-title">✧ 第五章 · 秘术与祷言 ✧</div>
          <div className="step-sub">
            {options.spell_preparation_type?.[classEnKey] === 'spellbook'
              ? `${classInfo?.zh || classEnKey} — 选择法术录入法术书（每日可准备一部分）`
              : options.spell_preparation_type?.[classEnKey] === 'prepared'
              ? `${classInfo?.zh || classEnKey} — 从职业法术表中选择准备法术（长休后可更换）`
              : `${classInfo?.zh || classEnKey} — 选择永久掌握的法术`}
          </div>
            {cantripCount > 0 && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--blue-light)' }}>戏法（0环，无限使用）</span>
                  <span style={{ fontSize: '0.75rem', color: chosenCantrips.length===cantripCount ? 'var(--green-light)' : 'var(--gold)' }}>
                    {chosenCantrips.length}/{cantripCount}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  {availableCantrips.map(name => {
                    const sel = chosenCantrips.includes(name)
                    const dis = !sel && chosenCantrips.length >= cantripCount
                    return (
                      <button key={name} disabled={dis} onClick={() => toggleCantrip(name)}
                        className="skill-btn"
                        style={{
                          textAlign: 'left', padding: '8px 12px',
                          borderColor: sel ? 'var(--blue-light)' : 'var(--wood-light)',
                          background: sel ? 'rgba(58,122,170,0.12)' : undefined,
                          color: dis ? 'var(--wood-light)' : sel ? 'var(--blue-light)' : 'var(--parchment)',
                          cursor: dis ? 'not-allowed' : 'pointer',
                          opacity: dis ? 0.4 : 1,
                        }}>{sel && '\u2713 '}{name}</button>
                    )
                  })}
                </div>
              </div>
            )}

            {spellCount > 0 && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.875rem', color: '#c084fc' }}>已知法术</span>
                  <span style={{ fontSize: '0.75rem', color: chosenSpells.length===spellCount ? 'var(--green-light)' : 'var(--gold)' }}>
                    {chosenSpells.length}/{spellCount}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  {availableSpells.map(name => {
                    const sel = chosenSpells.includes(name)
                    const dis = !sel && chosenSpells.length >= spellCount
                    return (
                      <button key={name} disabled={dis} onClick={() => toggleSpell(name)}
                        className="skill-btn"
                        style={{
                          textAlign: 'left', padding: '8px 12px',
                          borderColor: sel ? '#c084fc' : 'var(--wood-light)',
                          background: sel ? 'rgba(192,132,252,0.12)' : undefined,
                          color: dis ? 'var(--wood-light)' : sel ? '#c084fc' : 'var(--parchment)',
                          cursor: dis ? 'not-allowed' : 'pointer',
                          opacity: dis ? 0.4 : 1,
                        }}>{sel && '\u2713 '}{name}</button>
                    )
                  })}
                </div>
              </div>
            )}

        </div>
      )}

      {/* ══ Feat/ASI Step ══ */}
      {step === featStep && needsASI && (
        <div className="step-pane">
          <div className="step-title">✧ 第六章 · 淬炼与专长 ✧</div>
          <div className="step-sub">
            Lv{form.level} — {asiCount} 次属性提升 (ASI) 或专长选择
          </div>
            {Array.from({ length: asiCount }, (_, i) => {
              const feat = chosenFeats[i]
              const isASI = feat?.name === '__ASI__'
              return (
                <div key={i} style={{
                  padding: '12px 16px', borderRadius: '8px',
                  border: '1px solid var(--wood-light)', background: 'rgba(10,8,6,0.3)',
                }}>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-bright)', marginBottom: '8px', fontWeight: 600 }}>
                    第 {i + 1} 次选择（Lv {asiLevels[i]}）
                  </p>
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                    <button className={isASI ? 'btn-gold' : 'btn-fantasy'}
                      style={{ flex: 1, padding: '6px 12px', fontSize: '0.75rem' }}
                      onClick={() => {
                        const next = [...chosenFeats]
                        next[i] = { name: '__ASI__', desc: '两项属性各+1' }
                        setChosenFeats(next)
                      }}>+2 属性提升</button>
                    <button className={(feat && !isASI) ? 'btn-gold' : 'btn-fantasy'}
                      style={{ flex: 1, padding: '6px 12px', fontSize: '0.75rem' }}
                      onClick={() => {
                        const usedNames = chosenFeats.filter(f => f && f.name !== '__ASI__').map(f => f.name)
                        const available = Object.keys(options.feats || {}).filter(n => !usedNames.includes(n))
                        if (available.length > 0) {
                          const next = [...chosenFeats]
                          next[i] = { name: available[0] }
                          setChosenFeats(next)
                        }
                      }}>选择专长</button>
                  </div>
                  {feat && !isASI && (
                    <div>
                      <select value={feat.name} className="input-fantasy" style={{ marginBottom: '4px' }}
                        onChange={e => {
                          const next = [...chosenFeats]
                          next[i] = { name: e.target.value }
                          setChosenFeats(next)
                        }}>
                        {Object.entries(options.feats || {}).map(([name, info]) => (
                          <option key={name} value={name}>{info.zh || name} -- {info.desc?.slice(0, 30)}</option>
                        ))}
                      </select>
                      <p style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                        {(options.feats || {})[feat.name]?.desc}
                      </p>
                    </div>
                  )}
                </div>
              )
            })}

        </div>
      )}

      {/* ══ Party Step: 确认队伍 ══ */}
      {step === partyStep && (
        <div className="step-pane">
          <div className="step-title">✧ 终章 · 同伴相逢 ✧</div>
          <div className="step-sub">你的冒险不会独自前行。AI 已为你组建了最合拍的队伍。</div>

          {/* 玩家英雄大卡 */}
          {(() => {
            const hero = useGameStore.getState().playerCharacter
            const derived = hero?.derived || {}
            const mods = derived.ability_modifiers || {}
            const scores = hero?.ability_scores || finalScores
            const prof = derived.proficiency_bonus || (2 + Math.floor((form.level - 1) / 4))
            const hpMax = derived.hp_max || 1
            const ac = derived.ac || 10
            const dexMod = mods.dex != null ? mods.dex : modifier(scores.dex || 10)
            return (
              <div className="final-hero-card">
                <div className="fh-left">
                  <Portrait cls={classKey(form.char_class)} size="xl" />
                </div>
                <div className="fh-right">
                  <div className="fh-name">{form.name || '未命名英雄'}</div>
                  <div className="fh-sub">
                    {form.race || '—'} · {form.char_class || '—'}
                    {form.subclass ? ` · ${form.subclass}` : ''} · Lv {form.level}
                  </div>
                  <div className="fh-align">
                    {form.alignment || ''}
                    {form.background ? ` · 背景：${form.background}` : ''}
                  </div>

                  <div className="fh-stats">
                    {ABILITY_KEYS.map(k => {
                      const score = scores[k] || finalScores[k] || 10
                      const m = mods[k] != null ? mods[k] : modifier(score)
                      return (
                        <div key={k} className="fh-stat">
                          <div className="n">{ABILITY_ZH[k]}</div>
                          <div className="v">{score}</div>
                          <div className="m">{modStr(m)}</div>
                        </div>
                      )
                    })}
                  </div>

                  <div className="fh-derived">
                    <span>HP {hpMax}</span>
                    <span>AC {ac}</span>
                    <span>熟练 +{prof}</span>
                    <span>先攻 {modStr(dexMod)}</span>
                  </div>
                </div>
              </div>
            )
          })()}

          {/* 队伍人数选择 */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
            margin: '18px 0',
            fontFamily: 'var(--font-mono)', fontSize: 11,
            color: 'var(--parchment-dark)', letterSpacing: '.15em',
          }}>
            <span>队伍人数</span>
            {[2, 3, 4].map(n => (
              <button key={n}
                className={partySize === n ? 'btn-gold' : 'btn-ghost'}
                style={{ padding: '4px 12px', fontSize: 11 }}
                onClick={() => setPartySize(n)}>{n} 人</button>
            ))}
          </div>

          {/* 队友 · 金色饰带 */}
          <div className="companions-title">
            <span className="orn">❦</span>
            <span className="t">你的队友</span>
            <span className="orn">❦</span>
          </div>

          {generatingParty ? (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <p style={{
                color: 'var(--amber)', animation: 'pulse 2s infinite',
                fontFamily: 'var(--font-script)', fontStyle: 'italic',
              }}>✦ AI 正在为你召唤伙伴… ✦</p>
              <p style={{ fontSize: 12, color: 'var(--parchment-dark)', marginTop: 8 }}>
                根据你的职业分析队伍需求
              </p>
            </div>
          ) : (
            <div className="companions-grid">
              {companions.map(c => (
                <div key={c.id} className="companion-card">
                  <Portrait cls={classKey(c.char_class)} size="md" />
                  <div className="cc-info">
                    <div className="cc-name">{c.name}</div>
                    <div className="cc-sub">{c.race} · {c.char_class} · Lv {c.level || 1}</div>
                    {c.personality && (
                      <div className="cc-role" style={{
                        overflow: 'hidden', textOverflow: 'ellipsis',
                        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                      }}>{c.personality}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {!generatingParty && companions.length > 0 && (
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <button className="btn-ghost" style={{ fontSize: 11, padding: '6px 16px' }}
                onClick={() => handleGenerateParty()}>
                🔄 重新生成队伍
              </button>
            </div>
          )}

          {error && (
            <p style={{
              color: '#ffaaaa', fontSize: 12, marginTop: 12, padding: 8,
              background: 'rgba(139,32,32,.2)', border: '1px solid var(--blood)', borderRadius: 4,
              textAlign: 'center',
            }}>! {error}</p>
          )}
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

// ── 衍生属性预览 ──────────────────────────────────────────
function DerivedPreview({ scores, charClass, level }) {
  const prof = 2 + Math.floor((level - 1) / 4)
  const mods = {}
  for (const k of ABILITY_KEYS) mods[k] = Math.floor((scores[k] - 10) / 2)
  const HIT_DICE = {
    Fighter:10, Paladin:10, Ranger:10, Barbarian:12,
    Rogue:8, Monk:8, Bard:8, Cleric:8, Druid:8, Warlock:8, Sorcerer:6, Wizard:6,
  }
  const hd = HIT_DICE[charClass] || 8
  const hp = hd + mods.con + Math.max(0, level-1) * (Math.floor(hd/2)+1+mods.con)
  const items = [
    { label:'HP',   value: Math.max(1, hp) },
    { label:'先攻', value: modStr(mods.dex) },
    { label:'熟练', value: `+${prof}` },
    { label:'攻击', value: modStr(prof + Math.max(mods.str, mods.dex)) },
    { label:'AC',   value: 10 + mods.dex },
  ]
  return (
    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
      {items.map(({ label, value }) => (
        <div key={label} className="ability-card" style={{ padding: '8px 12px' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{label}</div>
          <div style={{ fontWeight: 'bold', color: 'var(--gold)' }}>{value}</div>
        </div>
      ))}
    </div>
  )
}

// ── 子组件 ────────────────────────────────────────────────
function Field({ label, children }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: '0.75rem', marginBottom: '6px', color: 'var(--text)', opacity: 0.7 }}>{label}</label>
      {children}
    </div>
  )
}

function Select({ value, options, placeholder, onChange }) {
  return (
    <select className="input-fantasy"
      style={{ color: value ? 'var(--parchment)' : 'var(--text-dim)', background: 'var(--bg2)' }}
      value={value} onChange={e => onChange(e.target.value)}>
      <option value="">{placeholder}</option>
      {options.map(o => <option key={o} value={o} style={{ background: 'var(--bg2)' }}>{o}</option>)}
    </select>
  )
}

function CompanionCard({ char, isPlayer }) {
  if (!char) return null
  const hpMax   = char.derived?.hp_max || char.hp_max || char.hp_current || 1
  const hpCur   = char.hp_current ?? hpMax
  const hpPct   = Math.round((hpCur / hpMax) * 100)
  const hpColor = hpPct > 60 ? 'var(--green-light)' : hpPct > 30 ? 'var(--gold)' : 'var(--red-light)'
  return (
    <div className="panel" style={{ padding: '12px', display: 'flex', gap: '12px' }}>
      <div className={isPlayer ? 'portrait portrait-player' : 'portrait portrait-ally'}>
        <ClassIcon className={char.char_class} size={22} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, color: 'var(--text-bright)' }}>{char.name}</span>
          {isPlayer && <span className="tag tag-ok">你</span>}
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{char.race} {char.char_class} Lv{char.level}</span>
        </div>
        {!isPlayer && (char.personality || char.catchphrase || char.backstory) && (
          <CompanionBio personality={char.personality} catchphrase={char.catchphrase} backstory={char.backstory} speechStyle={char.speech_style} combatPref={char.combat_preference} />
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
          <div style={{ flex: 1, height: '6px', borderRadius: '3px', overflow: 'hidden', background: 'var(--wood)' }}>
            <div style={{ height: '100%', borderRadius: '3px', width: `${hpPct}%`, background: hpColor, transition: 'width 0.3s' }} />
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{hpCur}/{hpMax} HP</span>
        </div>
      </div>
    </div>
  )
}

function CompanionBio({ personality, catchphrase, backstory, speechStyle, combatPref }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div style={{ marginTop: 4 }}>
      {/* 预览行：个性描述截断 + 口头禅 */}
      {!expanded && (
        <>
          {personality && (
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {personality}
            </p>
          )}
          {catchphrase && (
            <p style={{ fontSize: '0.75rem', marginTop: 2, fontStyle: 'italic', color: 'var(--emerald-light)' }}>
              「{catchphrase}」
            </p>
          )}
        </>
      )}

      {/* 展开后：完整信息 */}
      {expanded && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', lineHeight: 1.7, marginTop: 4 }}>
          {personality && <p style={{ marginBottom: 6 }}><span style={{ color: 'var(--amber)', fontWeight: 600 }}>性格：</span>{personality}</p>}
          {backstory && <p style={{ marginBottom: 6 }}><span style={{ color: 'var(--amber)', fontWeight: 600 }}>背景：</span>{backstory}</p>}
          {speechStyle && <p style={{ marginBottom: 6 }}><span style={{ color: 'var(--amber)', fontWeight: 600 }}>说话风格：</span>{speechStyle}</p>}
          {combatPref && <p style={{ marginBottom: 6 }}><span style={{ color: 'var(--amber)', fontWeight: 600 }}>战斗偏好：</span>{combatPref}</p>}
          {catchphrase && <p style={{ fontStyle: 'italic', color: 'var(--emerald-light)' }}>「{catchphrase}」</p>}
        </div>
      )}

      {/* 展开/收起按钮 */}
      <button onClick={() => setExpanded(!expanded)} style={{
        marginTop: 4, padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem',
        background: 'transparent', border: '1px solid var(--bark)',
        color: 'var(--amber)', cursor: 'pointer', fontFamily: 'inherit',
        transition: 'all 0.2s',
      }}>
        {expanded ? '收起 ▲' : '展开介绍 ▼'}
      </button>
    </div>
  )
}
