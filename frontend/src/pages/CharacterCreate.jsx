import { useState, useEffect, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { modulesApi, charactersApi, gameApi } from '../api/client'
import { useGameStore } from '../store/gameStore'
import {
  RACE_INFO, CLASS_INFO, SKILL_INFO, BACKGROUND_INFO,
  MULTICLASS_REQUIREMENTS, CLASS_ZH_TO_EN, ABILITY_ZH,
} from '../data/dnd5e.js'
import {
  BackIcon, ClassIcon, SwordIcon, ShieldIcon, WandIcon,
  BookIcon, ScrollIcon,
} from '../components/Icons'

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
        // Phase 12 新增
        fighting_style:    fightingStyle || null,
        equipment_choice:  equipChoice,
        bonus_languages:   bonusLanguages,
        feats:             chosenFeats,
      })
      setSavedCharId(char.id)
      setPlayerCharacter(char)
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
    s.push('确认队伍')
    return s
  })()

  return (
    <div style={{ minHeight: '100vh', padding: '16px', maxWidth: '768px', margin: '0 auto' }}>
      <InfoModal type={modal.type} itemKey={modal.itemKey} onClose={closeModal} />

      {/* 顶部 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <button className="btn-fantasy" style={{ fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '6px' }}
          onClick={() => navigate('/')}>
          <BackIcon size={16} /> 返回
        </button>
        <div>
          <h2 style={{ color: 'var(--gold)', fontWeight: 600, fontSize: '1.1rem', margin: 0 }}>{module.name}</h2>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', margin: 0 }}>推荐等级 Lv {module.level_min}--{module.level_max}</p>
        </div>
      </div>

      {/* 步骤指示器 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '32px', overflowX: 'auto' }}>
        {STEPS.map((label, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
            <div style={{
              width: '28px', height: '28px', borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.75rem', fontWeight: 'bold',
              ...(step > i+1
                ? { background: 'var(--green)', color: 'var(--green-light)' }
                : step === i+1
                ? { background: 'var(--gold)', color: 'var(--bg)' }
                : { background: 'var(--wood)', border: '1px solid var(--wood-light)', color: 'var(--text-dim)' }),
            }}>
              {step > i+1 ? '\u2713' : i+1}
            </div>
            <span style={{ fontSize: '0.75rem', color: step === i+1 ? 'var(--gold)' : 'var(--text-dim)' }}>{label}</span>
            {i < STEPS.length-1 && <span style={{ opacity: 0.2, margin: '0 2px', color: 'var(--text-dim)' }}>--</span>}
          </div>
        ))}
      </div>

      {error && (
        <div className="panel" style={{ padding: '12px', marginBottom: '16px', borderColor: 'var(--red)' }}>
          <p style={{ color: 'var(--red-light)', fontSize: '0.875rem', margin: 0 }}>! {error}</p>
        </div>
      )}

      {/* ══ Step 1: 基础信息 ══ */}
      {step === 1 && (
        <div className="panel" style={{ padding: '24px' }}>
          <h3 style={{ color: 'var(--gold)', fontSize: '1.125rem', fontWeight: 600, margin: '0 0 20px' }}>创建你的角色</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <Field label="角色名">
              <input className="input-fantasy"
                placeholder="输入角色名..." value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </Field>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Field label="种族">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Select value={form.race} options={options.races} placeholder="选择种族"
                    onChange={v => setForm(f => ({ ...f, race: v }))} />
                  {raceEnKey && <InfoBtn onClick={() => openModal('race', raceEnKey)} />}
                </div>
                {form.race && Object.keys(racialBonuses).length > 0 && (
                  <p style={{ fontSize: '0.75rem', marginTop: '4px', color: 'var(--green-light)' }}>
                    种族加值：{Object.entries(racialBonuses).map(([k,v]) =>
                      `${ABILITY_ZH[k]||k} +${v}`).join('、')}
                  </p>
                )}
              </Field>

              <Field label="职业">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Select value={form.char_class} options={options.classes} placeholder="选择职业"
                    onChange={v => setForm(f => ({ ...f, char_class: v }))} />
                  {classInfo && <InfoBtn onClick={() => openModal('class', classEnKey)} />}
                </div>
                {saveProfs.length > 0 && (
                  <p style={{ fontSize: '0.75rem', marginTop: '4px', color: 'var(--text-dim)' }}>
                    豁免熟练：{saveProfs.map(k => ABILITY_ZH[k]||k).join('、')}
                  </p>
                )}
              </Field>
            </div>

            {/* 子职业 */}
            {showSubclass && subclassOptions.length > 0 && (
              <Field label={`${classInfo.subclass_label}（${classInfo.subclass_unlock}级解锁）`}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
                  {subclassOptions.map(sc => {
                    const sel = form.subclass === sc.name
                    return (
                      <div key={sc.name}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          gap: '8px', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer',
                          transition: 'all 0.2s',
                          border: `1px solid ${sel ? 'var(--gold)' : 'var(--wood-light)'}`,
                          background: sel ? 'rgba(201,168,76,0.12)' : 'transparent',
                        }}
                        onClick={() => setForm(f => ({ ...f, subclass: sel ? '' : sc.name }))}>
                        <div style={{ minWidth: 0 }}>
                          <div style={{
                            fontSize: '0.875rem', fontWeight: 600, overflow: 'hidden',
                            textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            color: sel ? 'var(--gold)' : 'var(--text-bright)',
                          }}>{sc.zh}</div>
                        </div>
                        <InfoBtn onClick={e => { e.stopPropagation(); openModal('class', classEnKey) }} />
                      </div>
                    )
                  })}
                </div>
                {!form.subclass && <p style={{ fontSize: '0.75rem', marginTop: '4px', color: 'var(--text-dim)', opacity: 0.5 }}>可跳过，稍后决定</p>}
              </Field>
            )}

            {/* 战斗风格（Fighter/Paladin/Ranger） */}
            {hasFightingStyle && (
              <Field label="战斗风格">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
                  {(options.fighting_style_classes?.[classEnKey]?.styles || []).map(style => {
                    const sel = fightingStyle === style
                    const info = options.fighting_styles?.[style] || {}
                    return (
                      <div key={style}
                        style={{
                          padding: '8px 12px', borderRadius: '6px', cursor: 'pointer',
                          transition: 'all 0.2s',
                          border: `1px solid ${sel ? 'var(--gold)' : 'var(--wood-light)'}`,
                          background: sel ? 'rgba(201,168,76,0.12)' : 'transparent',
                        }}
                        onClick={() => setFightingStyle(sel ? '' : style)}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          {style.toLowerCase().includes('defense') || style.toLowerCase().includes('protection')
                            ? <ShieldIcon size={14} color={sel ? 'var(--gold)' : 'var(--text-dim)'} />
                            : style.toLowerCase().includes('dueling') || style.toLowerCase().includes('great')
                            ? <SwordIcon size={14} color={sel ? 'var(--gold)' : 'var(--text-dim)'} />
                            : <WandIcon size={14} color={sel ? 'var(--gold)' : 'var(--text-dim)'} />}
                          <span style={{ fontSize: '0.875rem', fontWeight: 600,
                            color: sel ? 'var(--gold)' : 'var(--text-bright)' }}>
                            {sel && '\u2713 '}{info.zh || style}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>{info.desc}</div>
                      </div>
                    )
                  })}
                </div>
              </Field>
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

            <button className="btn-gold" disabled={!step1Valid}
              style={{ width: '100%', padding: '12px', marginTop: '8px', fontSize: '0.95rem' }}
              onClick={() => setStep(2)}>
              下一步：分配能力值 &rarr;
            </button>
          </div>
        </div>
      )}

      {/* ══ Step 2: 能力值 ══ */}
      {step === 2 && (
        <div className="panel" style={{ padding: '24px' }}>
          <h3 style={{ color: 'var(--gold)', fontSize: '1.125rem', fontWeight: 600, margin: '0 0 20px' }}>分配能力值</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ display: 'flex', gap: '12px' }}>
              {['pointbuy','standard'].map(m => (
                <button key={m}
                  className={scoreMethod === m ? 'btn-gold' : 'btn-fantasy'}
                  style={{ flex: 1, padding: '8px', fontSize: '0.875rem' }}
                  onClick={() => { setScoreMethod(m); setStandardAssigned({}) }}>
                  {m==='pointbuy' ? '点数购买' : '标准数组'}
                </button>
              ))}
            </div>

            {scoreMethod === 'pointbuy' && (
              <div style={{ textAlign: 'center' }}>
                <p style={{ fontSize: '0.875rem', color: pointsLeft === 0 ? 'var(--green-light)' : 'var(--gold)' }}>
                  剩余点数：<strong style={{
                    fontSize: 18,
                    color: pointsLeft === 0 ? 'var(--green-light)' : pointsLeft <= 3 ? 'var(--gold)' : 'var(--gold)',
                  }}>{pointsLeft}</strong> / {POINT_BUY_TOTAL}
                  {pointsLeft === 0 && <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--green-light)' }}>{'\u2713'} 已分配完毕</span>}
                </p>
                <div style={{ height: 4, background: 'var(--wood)', borderRadius: 2, margin: '6px auto', maxWidth: 200 }}>
                  <div style={{
                    height: '100%', borderRadius: 2,
                    width: `${((POINT_BUY_TOTAL - pointsLeft) / POINT_BUY_TOTAL) * 100}%`,
                    background: pointsLeft === 0 ? 'var(--green-light)' : 'var(--gold)',
                    transition: 'width 0.2s ease',
                  }} />
                </div>
              </div>
            )}
            {scoreMethod === 'standard' && (
              <p style={{ fontSize: '0.75rem', textAlign: 'center', color: 'var(--text-dim)' }}>
                数组：{STANDARD_ARRAY.join(' / ')} -- 点击分配给对应能力
              </p>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {ABILITY_KEYS.map(key => {
                const base  = baseScores[key]
                const bonus = racialBonuses[key] || 0
                const final = finalScores[key]
                const mod   = modifier(final)
                return (
                  <div key={key} className="ability-card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ textAlign: 'center', width: '48px', flexShrink: 0 }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{ABILITY_ZH[key]||key}</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--text-bright)' }}>{final}</div>
                        <div style={{ fontSize: '0.75rem', color: mod>=0 ? 'var(--green-light)' : 'var(--red-light)' }}>
                          {modStr(mod)}
                        </div>
                      </div>
                      {bonus > 0 && (
                        <span className="tag tag-ok" style={{ flexShrink: 0 }}>
                          基础{base} +{bonus}
                        </span>
                      )}
                      {scoreMethod === 'pointbuy' && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                          <button className="btn-fantasy" style={{ padding: '2px', fontSize: '0.75rem' }}
                            onClick={() => adjustScore(key,1)}
                            disabled={base>=15 || pointsLeft<(SCORE_COSTS[base+1]-SCORE_COSTS[base])}>{'\u25B2'}</button>
                          <button className="btn-fantasy" style={{ padding: '2px', fontSize: '0.75rem' }}
                            onClick={() => adjustScore(key,-1)} disabled={base<=8}>{'\u25BC'}</button>
                        </div>
                      )}
                      {scoreMethod === 'standard' && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', flex: 1 }}>
                          {STANDARD_ARRAY.map((val,idx) => {
                            const usedByOther = Object.entries(standardAssigned).some(([a,i]) => a!==key && i===idx)
                            const selected    = standardAssigned[key] === idx
                            return (
                              <button key={idx} disabled={usedByOther}
                                className="skill-btn"
                                style={{
                                  padding: '2px 8px',
                                  borderColor: selected ? 'var(--gold)' : 'var(--wood-light)',
                                  color: selected ? 'var(--gold)' : usedByOther ? 'var(--wood-light)' : 'var(--parchment)',
                                  background: selected ? 'rgba(201,168,76,0.15)' : 'transparent',
                                  cursor: usedByOther ? 'not-allowed' : 'pointer',
                                  opacity: usedByOther ? 0.4 : 1,
                                }}
                                onClick={() => assignStandard(key,idx)}>{val}</button>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {form.char_class && (
              <DerivedPreview scores={finalScores} charClass={classEnKey} level={form.level} />
            )}

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

            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn-fantasy" style={{ flex: 1, padding: '8px' }} onClick={() => setStep(1)}>
                <BackIcon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />返回
              </button>
              <button className="btn-gold" style={{ flex: 1, padding: '8px' }} disabled={!step2Valid}
                onClick={() => setStep(3)}>下一步：技能熟练 &rarr;</button>
            </div>
          </div>
        </div>
      )}

      {/* ══ Step 3: 技能熟练 ══ */}
      {step === 3 && (
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ color: 'var(--gold)', fontSize: '1.125rem', fontWeight: 600, margin: '0 0 4px' }}>选择技能熟练</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', margin: 0 }}>
              {form.char_class} 可选 <strong style={{ color: 'var(--text-bright)' }}>{skillConfig.count}</strong> 项 · 已选{' '}
              <strong style={{ color: chosenSkills.length===skillConfig.count ? 'var(--green-light)' : 'var(--gold)' }}>
                {chosenSkills.length}
              </strong>
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {saveProfs.length > 0 && (
              <div style={{
                fontSize: '0.75rem', padding: '8px', borderRadius: '6px',
                background: 'rgba(26,58,90,0.15)', border: '1px solid var(--blue)',
              }}>
                <span style={{ color: 'var(--blue-light)' }}>职业豁免熟练（自动获得）：</span>
                <span style={{ marginLeft: '4px', color: 'var(--text)', opacity: 0.8 }}>{saveProfs.map(k => ABILITY_ZH[k]||k).join('、')}</span>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
              {skillConfig.options.map(skill => {
                const selected  = chosenSkills.includes(skill)
                const disabled  = !selected && chosenSkills.length >= skillConfig.count
                const skillData = SKILL_INFO[skill]
                return (
                  <div key={skill} style={{ position: 'relative' }}>
                    <button disabled={disabled} onClick={() => toggleSkill(skill)}
                      className="skill-btn"
                      style={{
                        width: '100%', textAlign: 'left', padding: '8px',
                        borderColor: selected ? 'var(--gold)' : 'var(--wood-light)',
                        background: selected ? 'rgba(201,168,76,0.12)' : undefined,
                        color: disabled ? 'var(--wood-light)' : selected ? 'var(--gold)' : 'var(--parchment)',
                        cursor: disabled ? 'not-allowed' : 'pointer',
                        paddingRight: skillData ? '1.75rem' : undefined,
                        opacity: disabled ? 0.4 : 1,
                      }}>
                      {selected && '\u2713 '}{skill}
                      {skillData && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginLeft: '4px' }}>
                          {ABILITY_ZH[skillData.ability]?.slice(0,1)}
                        </span>
                      )}
                    </button>
                    {skillData && (
                      <div style={{ position: 'absolute', right: '4px', top: '50%', transform: 'translateY(-50%)' }}>
                        <InfoBtn onClick={e => { e.stopPropagation(); openModal('skill', skill) }} />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn-fantasy" style={{ flex: 1, padding: '8px' }} onClick={() => setStep(2)}>
                <BackIcon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />返回
              </button>
              <button className="btn-gold" style={{ flex: 1, padding: '8px' }} disabled={!step3Valid}
                onClick={() => setStep(4)}>下一步：装备选择 &rarr;</button>
            </div>
          </div>
        </div>
      )}

      {/* ══ Step 4: 装备选择 ══ */}
      {step === 4 && (
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ color: 'var(--gold)', fontSize: '1.125rem', fontWeight: 600, margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ScrollIcon size={20} color="var(--gold)" /> 选择起始装备
            </h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', margin: 0 }}>选择你的出发装备方案</p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {(options.starting_equipment?.[classEnKey] || []).map((opt, idx) => (
              <label key={idx} style={{
                display: 'block', padding: '12px 16px', borderRadius: '8px', cursor: 'pointer',
                border: `1px solid ${equipChoice === idx ? 'var(--gold)' : 'var(--wood-light)'}`,
                background: equipChoice === idx ? 'rgba(201,168,76,0.1)' : 'rgba(10,8,6,0.3)',
                transition: 'all 0.2s',
              }} onClick={() => setEquipChoice(idx)}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="radio" checked={equipChoice === idx} readOnly style={{ accentColor: 'var(--gold)' }} />
                  <span style={{ color: 'var(--text-bright)', fontWeight: 600 }}>{opt.label}</span>
                </div>
                <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {opt.items.map((item, j) => (
                    <span key={j} className="tag" style={{
                      borderColor: item.slot === 'weapon' ? 'var(--red)' :
                                    item.slot === 'armor' ? 'var(--blue)' :
                                    item.slot === 'offhand' ? '#5b21b6' : 'var(--wood-light)',
                      color: item.slot === 'weapon' ? 'var(--red-light)' :
                             item.slot === 'armor' ? 'var(--blue-light)' :
                             item.slot === 'offhand' ? '#c4b5fd' : 'var(--text-dim)',
                      background: item.slot === 'weapon' ? 'rgba(139,32,32,0.15)' :
                                  item.slot === 'armor' ? 'rgba(26,58,90,0.15)' :
                                  item.slot === 'offhand' ? 'rgba(91,33,182,0.15)' : 'rgba(74,53,32,0.15)',
                    }}>
                      {getItemZh(item.name)}
                    </span>
                  ))}
                </div>
              </label>
            ))}

            {/* 背景特性预览 */}
            {form.background && options.background_features?.[form.background] && (
              <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(42,90,42,0.12)', border: '1px solid var(--green)' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--green-light)', marginBottom: '4px', margin: '0 0 4px' }}>
                  背景特性：{options.background_features[form.background].feature}
                </p>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-dim)', margin: 0 }}>
                  {options.background_features[form.background].feature_desc}
                </p>
                <div style={{ display: 'flex', gap: '8px', marginTop: '6px', fontSize: '0.7rem' }}>
                  {options.background_features[form.background].skills?.length > 0 && (
                    <span style={{ color: 'var(--green-light)' }}>技能：{options.background_features[form.background].skills.join('、')}</span>
                  )}
                  {options.background_features[form.background].tools?.length > 0 && (
                    <span style={{ color: 'var(--blue-light)' }}>工具：{options.background_features[form.background].tools.join('、')}</span>
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

            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn-fantasy" style={{ flex: 1, padding: '8px' }} onClick={() => setStep(3)}>
                <BackIcon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />返回
              </button>
              {isSpellcaster ? (
                <button className="btn-gold" style={{ flex: 1, padding: '8px' }}
                  onClick={() => setStep(5)}>下一步：法术选择 &rarr;</button>
              ) : needsASI ? (
                <button className="btn-gold" style={{ flex: 1, padding: '8px' }}
                  onClick={() => setStep(5)}>下一步：专长/属性提升 &rarr;</button>
              ) : (
                <button className="btn-gold" style={{ flex: 1, padding: '8px' }} disabled={saving}
                  onClick={handleSaveAndContinue}>
                  {saving ? '生成队伍中...' : '确认并生成队伍 \u2192'}</button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ══ Step 5: 法术选择（施法职业）══ */}
      {step === 5 && isSpellcaster && (
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ color: 'var(--gold)', fontSize: '1.125rem', fontWeight: 600, margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BookIcon size={20} color="var(--gold)" />
              {options.spell_preparation_type?.[classEnKey] === 'spellbook' ? '法术书' :
               options.spell_preparation_type?.[classEnKey] === 'prepared' ? '准备法术' : '已知法术'}
            </h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', margin: 0 }}>
              {options.spell_preparation_type?.[classEnKey] === 'spellbook'
                ? `${classInfo?.zh || classEnKey} -- 选择法术录入法术书（每日可准备一部分）`
                : options.spell_preparation_type?.[classEnKey] === 'prepared'
                ? `${classInfo?.zh || classEnKey} -- 从职业法术表中选择准备法术（长休后可更换）`
                : `${classInfo?.zh || classEnKey} -- 选择永久掌握的法术`}
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
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

            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn-fantasy" style={{ flex: 1, padding: '8px' }} onClick={() => setStep(4)}>
                <BackIcon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />返回
              </button>
              {needsASI ? (
                <button className="btn-gold" style={{ flex: 1, padding: '8px' }} disabled={!step4Valid}
                  onClick={() => setStep(featStep)}>下一步：专长/属性提升 &rarr;</button>
              ) : (
                <button className="btn-gold" style={{ flex: 1, padding: '8px' }} disabled={!step4Valid || saving}
                  onClick={handleSaveAndContinue}>
                  {saving ? '生成队伍中...' : '确认并生成队伍 \u2192'}</button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ══ Feat/ASI Step ══ */}
      {step === featStep && needsASI && (
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ color: 'var(--gold)', fontSize: '1.125rem', fontWeight: 600, margin: '0 0 4px' }}>专长 / 属性提升</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', margin: 0 }}>
              Lv{form.level} 可选择 {asiCount} 次属性提升(ASI)或专长
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
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

            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn-fantasy" style={{ flex: 1, padding: '8px' }}
                onClick={() => setStep(isSpellcaster ? spellStep : 4)}>
                <BackIcon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />返回
              </button>
              <button className="btn-gold" style={{ flex: 1, padding: '8px' }} disabled={saving}
                onClick={handleSaveAndContinue}>
                {saving ? '生成队伍中...' : '确认并生成队伍 \u2192'}</button>
            </div>
          </div>
        </div>
      )}

      {/* ══ Party Step: 确认队伍 ══ */}
      {step === partyStep && (
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
            <h3 style={{ color: 'var(--gold)', fontSize: '1.125rem', fontWeight: 600, margin: 0 }}>你的冒险队伍</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>队伍人数</span>
              {[2,3,4].map(n => (
                <button key={n}
                  className={partySize === n ? 'btn-gold' : 'btn-fantasy'}
                  style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                  onClick={() => setPartySize(n)}>{n}人</button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <CompanionCard char={useGameStore.getState().playerCharacter} isPlayer />

            {generatingParty ? (
              <div style={{ textAlign: 'center', padding: '32px 0' }}>
                <p style={{ color: 'var(--gold)', animation: 'pulse 2s infinite' }}>AI正在生成你的队友...</p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '8px' }}>根据你的职业分析队伍需求</p>
              </div>
            ) : (
              companions.map(c => <CompanionCard key={c.id} char={c} />)
            )}

            {!generatingParty && companions.length > 0 && (
              <button className="btn-fantasy" style={{ width: '100%', fontSize: '0.875rem', padding: '8px', opacity: 0.7 }}
                onClick={() => handleGenerateParty()}>重新生成队伍</button>
            )}

            {error && (
              <p style={{ color: 'var(--red-light)', fontSize: '0.875rem' }}>! {error}</p>
            )}

            <button className="btn-gold"
              disabled={companions.length===0 || generatingParty || saving}
              onClick={handleStartAdventure}
              style={{ width: '100%', padding: '12px', fontSize: '1.1rem' }}>
              {saving ? '准备中...' : '开始冒险!'}
            </button>
          </div>
        </div>
      )}
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
        {!isPlayer && char.personality && (
          <p style={{ fontSize: '0.75rem', marginTop: '4px', color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{char.personality}</p>
        )}
        {!isPlayer && char.catchphrase && (
          <p style={{ fontSize: '0.75rem', marginTop: '2px', fontStyle: 'italic', color: 'var(--green-light)' }}>"{char.catchphrase}"</p>
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
