import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { charactersApi, gameApi } from '../api/client'
import {
  BackIcon, ShieldIcon, HeartIcon, DiceD20Icon,
  BookIcon, ClassIcon, MagicIcon,
} from '../components/Icons'
import Portrait from '../components/Portrait'
import { classKey } from '../components/Crests'
import { Divider } from '../components/Ornaments'
import InventoryPanel from '../components/inventory/InventoryPanel'
import {
  buildLevelUpAbilityChoicePlan,
  buildLevelUpFeatChoicePlan,
  buildLevelUpFightingStyleChoicePlan,
  buildLevelUpManeuverChoicePlan,
  buildLevelUpSpellChoicePlan,
  buildLevelUpSubclassChoicePlan,
} from '../utils/levelUpSpellChoices'

// ── 常量 ──────────────────────────────────────────────────
const ABILITY_LABELS = {
  str: { en: 'STR', zh: '力量' },
  dex: { en: 'DEX', zh: '敏捷' },
  con: { en: 'CON', zh: '体质' },
  int: { en: 'INT', zh: '智力' },
  wis: { en: 'WIS', zh: '感知' },
  cha: { en: 'CHA', zh: '魅力' },
}

const SKILL_ABILITY_MAP = {
  '运动': 'str',
  '体操': 'dex', '巧手': 'dex', '隐匿': 'dex',
  '奥秘': 'int', '历史': 'int', '调查': 'int', '自然': 'int', '宗教': 'int',
  '驯兽': 'wis', '洞悉': 'wis', '医药': 'wis', '感知': 'wis', '求生': 'wis',
  '欺瞒': 'cha', '恐吓': 'cha', '表演': 'cha', '游说': 'cha',
  // English fallbacks
  'Athletics': 'str',
  'Acrobatics': 'dex', 'Sleight of Hand': 'dex', 'Stealth': 'dex',
  'Arcana': 'int', 'History': 'int', 'Investigation': 'int', 'Nature': 'int', 'Religion': 'int',
  'Animal Handling': 'wis', 'Insight': 'wis', 'Medicine': 'wis', 'Perception': 'wis', 'Survival': 'wis',
  'Deception': 'cha', 'Intimidation': 'cha', 'Performance': 'cha', 'Persuasion': 'cha',
}

const ALL_SKILLS = [
  '运动',
  '体操', '巧手', '隐匿',
  '奥秘', '历史', '调查', '自然', '���教',
  '驯兽', '洞悉', '医药', '感知', '求生',
  '欺瞒', '恐吓', '表演', '游说',
]

export default function CharacterSheet() {
  const { characterId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const [char, setChar] = useState(null)
  const [partyMembers, setPartyMembers] = useState([])
  const [characterOptions, setCharacterOptions] = useState(null)
  const [levelUpSelections, setLevelUpSelections] = useState({
    spells: [],
    cantrips: [],
    replacementOld: '',
    replacementNew: '',
    abilityIncreases: {},
    featName: '',
    subclassName: '',
    fightingStyleName: '',
    maneuvers: [],
  })
  const [levelUpBusy, setLevelUpBusy] = useState(false)
  const [levelUpNotice, setLevelUpNotice] = useState('')
  const [error, setError] = useState('')

  const loadCharacter = useCallback(async () => {
    try {
      const [data, optionsData] = await Promise.all([
        charactersApi.get(characterId),
        charactersApi.options ? charactersApi.options().catch(() => null) : Promise.resolve(null),
      ])
      setChar(data)
      if (optionsData) setCharacterOptions(optionsData)
      const sessionId = searchParams.get('sessionId')
      if (sessionId) {
        const session = await gameApi.getSession(sessionId)
        const party = [session.player, ...(session.companions || [])]
          .filter(member => member?.id && member.id !== characterId)
          .map(member => ({ id: member.id, name: member.name }))
        setPartyMembers(party)
      } else {
        setPartyMembers([])
      }
    } catch (e) {
      setError(e.message)
    }
  }, [characterId, searchParams])

  useEffect(() => { loadCharacter() }, [loadCharacter])

  const levelUpSpellPlan = useMemo(
    () => (char ? buildLevelUpSpellChoicePlan(char, characterOptions || {}) : null),
    [char, characterOptions],
  )
  const levelUpAbilityPlan = useMemo(
    () => (char ? buildLevelUpAbilityChoicePlan(char, characterOptions || {}) : null),
    [char, characterOptions],
  )
  const levelUpFeatPlan = useMemo(
    () => (char ? buildLevelUpFeatChoicePlan(char, characterOptions || {}) : null),
    [char, characterOptions],
  )
  const levelUpSubclassPlan = useMemo(
    () => (char ? buildLevelUpSubclassChoicePlan(char, characterOptions || {}) : null),
    [char, characterOptions],
  )
  const levelUpFightingStylePlan = useMemo(
    () => (char ? buildLevelUpFightingStyleChoicePlan(char, characterOptions || {}) : null),
    [char, characterOptions],
  )
  const levelUpManeuverPlan = useMemo(
    () => (char ? buildLevelUpManeuverChoicePlan(char, characterOptions || {}, levelUpSelections.subclassName) : null),
    [char, characterOptions, levelUpSelections.subclassName],
  )

  const resetLevelUpSelections = useCallback(() => {
    setLevelUpSelections({
      spells: [],
      cantrips: [],
      replacementOld: '',
      replacementNew: '',
      abilityIncreases: {},
      featName: '',
      subclassName: '',
      fightingStyleName: '',
      maneuvers: [],
    })
  }, [])

  const toggleLevelUpChoice = useCallback((kind, value, capacity) => {
    const key = kind === 'cantrip' ? 'cantrips' : 'spells'
    setLevelUpSelections(prev => {
      const current = prev[key] || []
      if (current.includes(value)) {
        return { ...prev, [key]: current.filter(item => item !== value) }
      }
      if (current.length >= capacity) return prev
      return { ...prev, [key]: [...current, value] }
    })
  }, [])

  const toggleLevelUpManeuver = useCallback((value, capacity) => {
    setLevelUpSelections(prev => {
      const current = prev.maneuvers || []
      if (current.includes(value)) {
        return { ...prev, maneuvers: current.filter(item => item !== value) }
      }
      if (current.length >= capacity) return prev
      return { ...prev, maneuvers: [...current, value] }
    })
  }, [])

  const adjustLevelUpAbility = useCallback((ability, change) => {
    setLevelUpSelections(prev => {
      const current = prev.abilityIncreases || {}
      const currentValue = Number(current[ability] || 0)
      const maxIncrease = levelUpAbilityPlan?.abilityOptions?.[ability]?.maxIncrease || 0
      const total = Object.values(current).reduce((sum, value) => sum + (Number(value) || 0), 0)
      const nextValue = Math.max(0, Math.min(maxIncrease, currentValue + change))
      const nextTotal = total - currentValue + nextValue

      if (nextTotal > (levelUpAbilityPlan?.abilityCapacity || 0)) return prev

      const nextIncreases = { ...current }
      if (nextValue > 0) nextIncreases[ability] = nextValue
      else delete nextIncreases[ability]
      return { ...prev, abilityIncreases: nextIncreases, featName: '' }
    })
  }, [levelUpAbilityPlan])

  const handleLevelUp = useCallback(async () => {
    if (!char || levelUpBusy) return
    setLevelUpBusy(true)
    setError('')
    setLevelUpNotice('')

    const payload = { use_average_hp: true }
    const abilityIncreases = Object.fromEntries(
      Object.entries(levelUpSelections.abilityIncreases || {})
        .filter(([, value]) => Number(value) > 0),
    )
    if (levelUpSelections.featName) payload.feat_choice = { name: levelUpSelections.featName }
    else if (Object.keys(abilityIncreases).length) payload.ability_score_increases = abilityIncreases
    if (levelUpSelections.subclassName) payload.subclass_choice = levelUpSelections.subclassName
    if (levelUpSelections.fightingStyleName) payload.fighting_style_choice = levelUpSelections.fightingStyleName
    if (levelUpSelections.maneuvers.length) payload.maneuver_choices = levelUpSelections.maneuvers
    if (levelUpSelections.spells.length) payload.learned_spells = levelUpSelections.spells
    if (levelUpSelections.cantrips.length) payload.learned_cantrips = levelUpSelections.cantrips
    if (levelUpSelections.replacementOld && levelUpSelections.replacementNew) {
      payload.spell_replacements = [{
        old_spell: levelUpSelections.replacementOld,
        new_spell: levelUpSelections.replacementNew,
      }]
    }

    try {
      const result = await charactersApi.levelUp(char.id, payload)
      if (result?.character) setChar(result.character)
      resetLevelUpSelections()
      setLevelUpNotice('Level up complete')
    } catch (e) {
      setError(e.message)
    } finally {
      setLevelUpBusy(false)
    }
  }, [char, levelUpBusy, levelUpSelections, resetLevelUpSelections])

  if (error && !char) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ color: 'var(--red-light)', marginBottom: 16 }}>{error}</p>
          <button className="btn-fantasy" onClick={() => navigate(-1)}>
            <BackIcon size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} /> 返回
          </button>
        </div>
      </div>
    )
  }

  if (!char) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}>
        <p style={{ color: 'var(--gold)', animation: 'pulse 1.5s infinite' }}>加载角色数据...</p>
      </div>
    )
  }

  const derived = char.derived || {}
  const mods = derived.ability_modifiers || {}
  const saves = derived.saving_throws || {}
  const scores = char.ability_scores || {}
  const hpMax = char.hp_max || derived.hp_max || char.hp_current || 1
  const hpCur = char.hp_current || 0
  const hpPct = Math.max(0, Math.min(100, Math.round((hpCur / hpMax) * 100)))
  const hpColor = hpPct > 60 ? 'var(--green-light)' : hpPct > 30 ? '#f59e0b' : 'var(--red-light)'
  const profBonus = derived.proficiency_bonus || 2
  const passivePerception = 10 + (mods.wis || 0) + ((char.proficient_skills || []).includes('感知') || (char.proficient_skills || []).includes('Perception') ? profBonus : 0)
  const slotsMax = derived.spell_slots_max || {}
  const slotsCur = char.spell_slots || {}

  const fmtMod = (v) => v >= 0 ? `+${v}` : `${v}`

  return (
    <div className="character-sheet-page">
      {/* Header */}
      <header className="character-sheet-header">
        <button className="btn-ghost character-sheet-back" style={{ fontSize: 12 }} onClick={() => navigate(-1)}>
          ⬅ 返回
        </button>
        <div className="display-title character-sheet-header-title">☙ 角色卡 ❧</div>
        <div className="character-sheet-header-spacer" />
      </header>

      {/* Main content */}
      <div className="character-sheet-content">
        {error && (
          <p style={{ color: '#ffaaaa', fontSize: 12, marginBottom: 12, padding: 8, background: 'rgba(139,32,32,.2)', border: '1px solid var(--blood)', borderRadius: 4 }}>{error}</p>
        )}

        {/* ── Identity Section ── */}
        <div className="panel-ornate" style={{ padding: 20, marginBottom: 16 }}>
          <div className="character-sheet-identity-row">
            <Portrait cls={classKey(char.char_class)} size="lg" />
            <div className="character-sheet-identity-body">
              <div className="display-title character-sheet-name" style={{ fontSize: 24, marginBottom: 4 }}>{char.name}</div>
              <div className="eyebrow" style={{ marginBottom: 4 }}>
                {char.race} · {char.char_class} · Lv{char.level}
                {char.subclass && ` · ${char.subclass}`}
              </div>
              {char.background && (
                <p style={{ color: 'var(--parchment-dark)', fontSize: 12, margin: 0, fontFamily: 'var(--font-script)', fontStyle: 'italic' }}>
                  {char.background}
                  {char.alignment && ` · ${char.alignment}`}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* ── Core Stats Row ── */}
        <div className="character-sheet-core-grid">
          {/* HP */}
          <div className="panel" style={{ padding: 12, textAlign: 'center' }}>
            <p style={{ color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 6px' }}>
              <HeartIcon size={12} color={hpColor} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 3 }} /> 生命值
            </p>
            <div style={{ height: 6, background: 'var(--wood)', borderRadius: 3, overflow: 'hidden', marginBottom: 6 }}>
              <div style={{ height: '100%', borderRadius: 3, background: hpColor, width: `${hpPct}%`, transition: 'width 0.4s' }} />
            </div>
            <p style={{ color: hpColor, fontSize: 18, fontWeight: 700, margin: 0 }}>{hpCur} / {hpMax}</p>
          </div>
          {/* AC */}
          <div className="panel" style={{ padding: 12, textAlign: 'center' }}>
            <p style={{ color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 6px' }}>
              <ShieldIcon size={12} color="var(--blue-light)" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 3 }} /> 护甲等级
            </p>
            <p style={{ color: 'var(--blue-light)', fontSize: 26, fontWeight: 700, margin: 0 }}>{derived.ac || 10}</p>
          </div>
          {/* Initiative */}
          <div className="panel" style={{ padding: 12, textAlign: 'center' }}>
            <p style={{ color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 6px' }}>
              <DiceD20Icon size={12} color="var(--gold)" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 3 }} /> 先攻
            </p>
            <p style={{ color: 'var(--gold)', fontSize: 26, fontWeight: 700, margin: 0 }}>{fmtMod(derived.initiative || 0)}</p>
          </div>
          {/* Proficiency & Passive Perception */}
          <div className="panel" style={{ padding: 12, textAlign: 'center' }}>
            <p style={{ color: 'var(--text-dim)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 6px' }}>
              熟练 / 被动感知
            </p>
            <p style={{ color: 'var(--parchment)', fontSize: 18, fontWeight: 700, margin: 0 }}>
              +{profBonus} <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>/</span> {passivePerception}
            </p>
          </div>
        </div>

        {/* ── Ability Scores ── */}
        <div className="panel" style={{ padding: 16, marginBottom: 16 }}>
          <SectionTitle>能力值</SectionTitle>
          <div className="character-sheet-ability-grid">
            {Object.entries(ABILITY_LABELS).map(([key, label]) => {
              const score = scores[key] || 10
              const mod = mods[key] || 0
              return (
                <div key={key} className="ability-card">
                  <p style={{ color: 'var(--gold-dim)', fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 4px' }}>
                    {label.zh}
                  </p>
                  <p style={{ color: 'var(--parchment)', fontSize: 22, fontWeight: 700, margin: '0 0 2px' }}>{score}</p>
                  <p style={{ color: mod >= 0 ? 'var(--green-light)' : 'var(--red-light)', fontSize: 13, fontWeight: 600, margin: 0 }}>
                    {fmtMod(mod)}
                  </p>
                </div>
              )
            })}
          </div>
        </div>

        <div className="character-sheet-two-column-grid">
          {/* ── Saving Throws ── */}
          <div className="panel" style={{ padding: 16 }}>
            <SectionTitle>豁免检定</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(ABILITY_LABELS).map(([key, label]) => {
                const prof = (char.proficient_saves || []).includes(key)
                const val = saves[key] || (mods[key] || 0)
                return (
                  <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0' }}>
                    <div style={{
                      width: 10, height: 10, borderRadius: '50%',
                      background: prof ? 'var(--gold)' : 'transparent',
                      border: `2px solid ${prof ? 'var(--gold)' : 'var(--wood-light)'}`,
                      flexShrink: 0,
                    }} />
                    <span style={{ color: 'var(--text-dim)', fontSize: 11, width: 32 }}>{label.zh}</span>
                    <span style={{ color: prof ? 'var(--gold)' : 'var(--parchment)', fontSize: 13, fontWeight: prof ? 700 : 400 }}>
                      {fmtMod(val)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* ── Skills ── */}
          <div className="panel" style={{ padding: 16 }}>
            <SectionTitle>技能</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 240, overflowY: 'auto' }}>
              {ALL_SKILLS.map(skill => {
                const prof = (char.proficient_skills || []).includes(skill)
                const abilKey = SKILL_ABILITY_MAP[skill] || 'str'
                const mod = mods[abilKey] || 0
                const val = prof ? mod + profBonus : mod
                return (
                  <div key={skill} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 0' }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: prof ? 'var(--gold)' : 'transparent',
                      border: `1.5px solid ${prof ? 'var(--gold)' : 'var(--wood-light)'}`,
                      flexShrink: 0,
                    }} />
                    <span style={{ color: 'var(--text-dim)', fontSize: 10, flex: 1 }}>
                      {skill}
                      <span style={{ color: 'var(--wood-light)', marginLeft: 4 }}>({ABILITY_LABELS[abilKey]?.en})</span>
                    </span>
                    <span style={{ color: prof ? 'var(--gold)' : 'var(--parchment)', fontSize: 12, fontWeight: prof ? 700 : 400 }}>
                      {fmtMod(val)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        <InventoryPanel
          character={char}
          partyMembers={partyMembers}
          onCharacterChange={setChar}
          onError={setError}
        />

        <LevelUpPanel
          spellPlan={levelUpSpellPlan}
          abilityPlan={levelUpAbilityPlan}
          featPlan={levelUpFeatPlan}
          subclassPlan={levelUpSubclassPlan}
          fightingStylePlan={levelUpFightingStylePlan}
          maneuverPlan={levelUpManeuverPlan}
          selections={levelUpSelections}
          onToggleChoice={toggleLevelUpChoice}
          onToggleManeuver={toggleLevelUpManeuver}
          onAdjustAbility={adjustLevelUpAbility}
          onSelectionChange={setLevelUpSelections}
          onLevelUp={handleLevelUp}
          busy={levelUpBusy}
          notice={levelUpNotice}
        />

        {/* ── Spell Slots ── */}
        {Object.keys(slotsMax).length > 0 && (
          <div className="panel" style={{ padding: 16, marginBottom: 16 }}>
            <SectionTitle>
              <MagicIcon size={14} color="#8a5af6" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />
              法术位
            </SectionTitle>
            <div className="character-sheet-spell-slot-grid">
              {Object.entries(slotsMax).map(([lvl, max]) => {
                const cur = slotsCur[lvl] ?? max
                return (
                  <div key={lvl} style={{
                    padding: '8px 10px', borderRadius: 6,
                    background: 'rgba(138,90,246,0.08)',
                    border: '1px solid rgba(138,90,246,0.2)',
                    textAlign: 'center',
                  }}>
                    <p style={{ color: '#8a5af6', fontSize: 10, fontWeight: 700, margin: '0 0 4px', textTransform: 'uppercase' }}>
                      {lvl[0]}环
                    </p>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 3, marginBottom: 4 }}>
                      {Array.from({ length: max }).map((_, i) => (
                        <div key={i} style={{
                          width: 10, height: 10, borderRadius: '50%',
                          background: i < cur ? '#8a5af6' : 'var(--wood)',
                          border: '1.5px solid rgba(138,90,246,0.5)',
                        }} />
                      ))}
                    </div>
                    <p style={{ color: 'var(--parchment)', fontSize: 12, margin: 0 }}>{cur}/{max}</p>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* ── Known / Prepared Spells ── */}
        {((char.cantrips || []).length > 0 || (char.known_spells || []).length > 0) && (
          <div className="panel" style={{ padding: 16, marginBottom: 16 }}>
            <SectionTitle>
              <BookIcon size={14} color="#8a5af6" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />
              法术列表
            </SectionTitle>

            {(char.cantrips || []).length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <p style={{ color: 'var(--blue-light)', fontSize: 10, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase' }}>
                  戏法 (无限使用)
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {char.cantrips.map(s => (
                    <span key={s} style={{
                      fontSize: 11, padding: '3px 10px', borderRadius: 12,
                      background: 'rgba(58,122,170,0.12)', border: '1px solid rgba(58,122,170,0.3)',
                      color: 'var(--blue-light)',
                    }}>{s}</span>
                  ))}
                </div>
              </div>
            )}

            {(char.prepared_spells || []).length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <p style={{ color: '#c084fc', fontSize: 10, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase' }}>
                  已准备法术
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {char.prepared_spells.map(s => (
                    <span key={s} style={{
                      fontSize: 11, padding: '3px 10px', borderRadius: 12,
                      background: 'rgba(138,90,246,0.12)', border: '1px solid rgba(138,90,246,0.3)',
                      color: '#c084fc',
                    }}>{s}</span>
                  ))}
                </div>
              </div>
            )}

            {(char.known_spells || []).length > 0 && (
              <div>
                <p style={{ color: 'var(--parchment-dark)', fontSize: 10, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase' }}>
                  已知法术
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {char.known_spells.map(s => (
                    <span key={s} style={{
                      fontSize: 11, padding: '3px 10px', borderRadius: 12,
                      background: 'rgba(138,90,246,0.06)', border: '1px solid var(--wood-light)',
                      color: 'var(--parchment-dark)',
                    }}>{s}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Class Features ── */}
        <div className="panel" style={{ padding: 16, marginBottom: 16 }}>
          <SectionTitle>职业特性</SectionTitle>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {char.fighting_style && (
              <FeatureTag label="战斗风格" value={char.fighting_style} color="var(--red-light)" />
            )}
            {(char.feats || []).map((f, i) => (
              <FeatureTag key={i} label="专长" value={typeof f === 'string' ? f : f.name} color="var(--gold)" />
            ))}
            {char.subclass && (
              <FeatureTag label="子职业" value={char.subclass} color="#8a5af6" />
            )}
            {derived.caster_type && (
              <FeatureTag label="施法类型" value={derived.caster_type} color="var(--blue-light)" />
            )}
            {!char.fighting_style && !(char.feats || []).length && !char.subclass && !derived.caster_type && (
              <p style={{ color: 'var(--text-dim)', fontSize: 12 }}>暂无特殊职业特性</p>
            )}
          </div>
        </div>

        {/* ── Languages & Tools ── */}
        <div className="character-sheet-two-column-grid">
          <div className="panel" style={{ padding: 16 }}>
            <SectionTitle>语言</SectionTitle>
            {(char.languages || []).length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {char.languages.map(l => <span key={l} className="tag tag-info">{l}</span>)}
              </div>
            ) : (
              <p style={{ color: 'var(--text-dim)', fontSize: 12 }}>Common</p>
            )}
          </div>
          <div className="panel" style={{ padding: 16 }}>
            <SectionTitle>工具熟练</SectionTitle>
            {(char.tool_proficiencies || []).length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {char.tool_proficiencies.map(t => <span key={t} className="tag tag-info">{t}</span>)}
              </div>
            ) : (
              <p style={{ color: 'var(--text-dim)', fontSize: 12 }}>无</p>
            )}
          </div>
        </div>

        {/* ── Conditions ── */}
        {(char.conditions || []).length > 0 && (
          <div className="panel" style={{ padding: 16, marginBottom: 16, borderColor: 'var(--red)' }}>
            <SectionTitle>
              <span style={{ color: 'var(--red-light)' }}>状态条件</span>
            </SectionTitle>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {char.conditions.map(c => {
                const dur = (char.condition_durations || {})[c]
                return (
                  <span key={c} style={{
                    fontSize: 12, padding: '4px 12px', borderRadius: 6,
                    background: 'rgba(139,32,32,0.2)', border: '1px solid var(--red)',
                    color: 'var(--red-light)', fontWeight: 600,
                  }}>
                    {c}{dur != null ? ` (${dur} 回合)` : ''}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* Bottom spacer */}
        <div style={{ height: 32 }} />
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────

function LevelUpPanel({
  spellPlan,
  abilityPlan,
  featPlan,
  subclassPlan,
  fightingStylePlan,
  maneuverPlan,
  selections,
  onToggleChoice,
  onToggleManeuver,
  onAdjustAbility,
  onSelectionChange,
  onLevelUp,
  busy,
  notice,
}) {
  const plan = spellPlan || abilityPlan || featPlan || subclassPlan || fightingStylePlan || maneuverPlan
  if (!plan) return null

  const hasSpellChoices = (spellPlan?.spellOptions || []).length > 0 && spellPlan.spellCapacity > 0
  const hasCantripChoices = (spellPlan?.cantripOptions || []).length > 0 && spellPlan.cantripCapacity > 0
  const hasReplacementChoices = spellPlan?.canReplaceSpell && (spellPlan?.replacementNewOptions || []).length > 0
  const hasAbilityChoices = abilityPlan?.isAsiLevel && abilityPlan.abilityCapacity > 0
  const hasFeatChoices = featPlan?.isFeatChoiceLevel && (featPlan?.featOptions || []).length > 0
  const hasSubclassChoices = subclassPlan?.isSubclassChoiceLevel && (subclassPlan?.subclassOptions || []).length > 0
  const hasFightingStyleChoices = fightingStylePlan?.isFightingStyleChoiceLevel && (fightingStylePlan?.styleOptions || []).length > 0
  const hasManeuverChoices = maneuverPlan?.isBattleMaster && maneuverPlan.requiredChoices > 0 && (maneuverPlan?.maneuverOptions || []).length > 0
  const selectedSpellCount = selections.spells.length
  const selectedCantripCount = selections.cantrips.length
  const selectedManeuverCount = selections.maneuvers.length
  const selectedAbilityTotal = Object.values(selections.abilityIncreases || {})
    .reduce((sum, value) => sum + (Number(value) || 0), 0)
  const hasProgressionChoices = hasSpellChoices || hasCantripChoices || hasReplacementChoices
    || hasAbilityChoices || hasFeatChoices || hasSubclassChoices || hasFightingStyleChoices || hasManeuverChoices
  const hasCompletedAsiChoice = !hasAbilityChoices
    || Boolean(selections.featName)
    || selectedAbilityTotal === abilityPlan.abilityCapacity
  const hasCompletedSubclassChoice = !hasSubclassChoices || Boolean(selections.subclassName)
  const hasCompletedFightingStyleChoice = !hasFightingStyleChoices || Boolean(selections.fightingStyleName)
  const hasCompletedManeuverChoice = !hasManeuverChoices || selectedManeuverCount === maneuverPlan.requiredChoices
  const canSubmitLevelUp = hasCompletedAsiChoice
    && hasCompletedSubclassChoice
    && hasCompletedFightingStyleChoice
    && hasCompletedManeuverChoice
  const selectedFeat = (featPlan?.featOptions || []).find(feat => feat.name === selections.featName)

  return (
    <div className="panel" style={{ padding: 16, marginBottom: 16 }}>
      <SectionTitle>Level Up</SectionTitle>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: hasProgressionChoices ? 12 : 0 }}>
        <div>
          <p style={{ color: 'var(--parchment)', fontSize: 14, fontWeight: 700, margin: 0 }}>
            Lv{plan.currentLevel} -&gt; Lv{plan.nextLevel}
          </p>
          <p style={{ color: 'var(--text-dim)', fontSize: 11, margin: '3px 0 0' }}>
            {plan.classKey || 'Class'}{spellPlan?.preparationType ? ` / ${spellPlan.preparationType}` : ''}
          </p>
        </div>
        <button
          type="button"
          className="btn-fantasy"
          onClick={onLevelUp}
          disabled={busy || !canSubmitLevelUp}
          style={{ minWidth: 112 }}
        >
          {busy ? 'Leveling...' : 'Level Up'}
        </button>
      </div>

      {hasSubclassChoices && (
        <div style={{ marginTop: 10 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--text-dim)', fontSize: 11 }}>
            Subclass
            <select
              aria-label="Subclass choice"
              value={selections.subclassName}
              onChange={(event) => onSelectionChange(prev => ({
                ...prev,
                subclassName: event.target.value,
                maneuvers: event.target.value === 'Battle Master' ? prev.maneuvers : [],
              }))}
              style={levelUpSelectStyle}
            >
              <option value="">Choose subclass</option>
              {subclassPlan.subclassOptions.map(option => (
                <option key={option.name} value={option.name}>{option.name}</option>
              ))}
            </select>
          </label>
        </div>
      )}

      {hasFightingStyleChoices && (
        <div style={{ marginTop: 10 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--text-dim)', fontSize: 11 }}>
            Fighting Style
            <select
              aria-label="Fighting style choice"
              value={selections.fightingStyleName}
              onChange={(event) => onSelectionChange(prev => ({
                ...prev,
                fightingStyleName: event.target.value,
              }))}
              style={levelUpSelectStyle}
            >
              <option value="">Choose style</option>
              {fightingStylePlan.styleOptions.map(style => (
                <option key={style.name} value={style.name}>
                  {style.zh ? `${style.name} - ${style.zh}` : style.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {hasManeuverChoices && (
        <LevelUpChoiceGroup
          title={`Maneuvers ${selectedManeuverCount}/${maneuverPlan.requiredChoices}`}
          values={maneuverPlan.maneuverOptions.map(option => option.id)}
          selected={selections.maneuvers}
          onToggle={(value) => onToggleManeuver(value, maneuverPlan.requiredChoices)}
          labelPrefix="Learn maneuver"
        />
      )}

      {hasAbilityChoices && (
        <div style={{ marginTop: 10 }}>
          <p style={{ color: 'var(--gold-dim)', fontSize: 10, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase' }}>
            ASI {selectedAbilityTotal}/{abilityPlan.abilityCapacity}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(142px, 1fr))', gap: 8 }}>
            {Object.entries(ABILITY_LABELS).map(([ability, label]) => {
              const option = abilityPlan.abilityOptions?.[ability] || { score: 10, maxIncrease: 0 }
              const selected = Number(selections.abilityIncreases?.[ability] || 0)
              const canIncrease = selected < option.maxIncrease && selectedAbilityTotal < abilityPlan.abilityCapacity
              return (
                <div
                  key={ability}
                  style={{
                    minHeight: 42,
                    borderRadius: 6,
                    border: '1px solid var(--wood-light)',
                    background: 'rgba(201,162,76,0.06)',
                    padding: '6px 8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                  }}
                >
                  <div>
                    <p style={{ color: 'var(--parchment)', fontSize: 12, fontWeight: 700, margin: 0 }}>
                      {label.en}
                    </p>
                    <p style={{ color: 'var(--text-dim)', fontSize: 10, margin: '2px 0 0' }}>
                      {option.score} -&gt; {option.score + selected}
                    </p>
                  </div>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <button
                      type="button"
                      aria-label={`Decrease ${label.en}`}
                      className="btn-ghost"
                      onClick={() => onAdjustAbility(ability, -1)}
                      disabled={selected <= 0}
                      style={{ minWidth: 28, minHeight: 28, padding: 0 }}
                    >
                      -
                    </button>
                    <span style={{ color: 'var(--gold)', fontSize: 12, fontWeight: 700, minWidth: 10, textAlign: 'center' }}>
                      {selected}
                    </span>
                    <button
                      type="button"
                      aria-label={`Increase ${label.en}`}
                      className="btn-ghost"
                      onClick={() => onAdjustAbility(ability, 1)}
                      disabled={!canIncrease}
                      style={{ minWidth: 28, minHeight: 28, padding: 0 }}
                    >
                      +
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {hasFeatChoices && (
        <div style={{ marginTop: 10 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--text-dim)', fontSize: 11 }}>
            Feat
            <select
              aria-label="Feat choice"
              value={selections.featName}
              onChange={(event) => onSelectionChange(prev => ({
                ...prev,
                featName: event.target.value,
                abilityIncreases: {},
              }))}
              style={levelUpSelectStyle}
            >
              <option value="">No feat</option>
              {featPlan.featOptions.map(feat => (
                <option key={feat.name} value={feat.name}>
                  {feat.zh ? `${feat.name} - ${feat.zh}` : feat.name}
                </option>
              ))}
            </select>
          </label>
          {selectedFeat?.desc && (
            <p style={{ color: 'var(--text-dim)', fontSize: 11, margin: '6px 0 0' }}>
              {selectedFeat.desc}
            </p>
          )}
        </div>
      )}

      {hasSpellChoices && (
        <LevelUpChoiceGroup
          title={`Spells ${selectedSpellCount}/${spellPlan.spellCapacity}`}
          values={spellPlan.spellOptions}
          selected={selections.spells}
          onToggle={(value) => onToggleChoice('spell', value, spellPlan.spellCapacity)}
          labelPrefix="Learn"
        />
      )}

      {hasCantripChoices && (
        <LevelUpChoiceGroup
          title={`Cantrips ${selectedCantripCount}/${spellPlan.cantripCapacity}`}
          values={spellPlan.cantripOptions}
          selected={selections.cantrips}
          onToggle={(value) => onToggleChoice('cantrip', value, spellPlan.cantripCapacity)}
          labelPrefix="Learn cantrip"
        />
      )}

      {hasReplacementChoices && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginTop: 10 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--text-dim)', fontSize: 11 }}>
            Replace known spell
            <select
              aria-label="Replace known spell"
              value={selections.replacementOld}
              onChange={(event) => onSelectionChange(prev => ({
                ...prev,
                replacementOld: event.target.value,
              }))}
              style={levelUpSelectStyle}
            >
              <option value="">None</option>
              {spellPlan.replacementKnownOptions.map(spell => (
                <option key={spell} value={spell}>{spell}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--text-dim)', fontSize: 11 }}>
            Replacement spell
            <select
              aria-label="Replacement spell"
              value={selections.replacementNew}
              onChange={(event) => onSelectionChange(prev => ({
                ...prev,
                replacementNew: event.target.value,
              }))}
              disabled={!selections.replacementOld}
              style={levelUpSelectStyle}
            >
              <option value="">None</option>
              {spellPlan.replacementNewOptions.map(spell => (
                <option key={spell} value={spell}>{spell}</option>
              ))}
            </select>
          </label>
        </div>
      )}

      {notice && (
        <p role="status" style={{ color: 'var(--green-light)', fontSize: 12, margin: '10px 0 0' }}>
          {notice}
        </p>
      )}
    </div>
  )
}

function LevelUpChoiceGroup({ title, values, selected, onToggle, labelPrefix }) {
  return (
    <div style={{ marginTop: 10 }}>
      <p style={{ color: 'var(--gold-dim)', fontSize: 10, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase' }}>
        {title}
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {values.map(value => (
          <label
            key={value}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              minHeight: 28,
              padding: '4px 9px',
              borderRadius: 6,
              border: '1px solid var(--wood-light)',
              color: selected.includes(value) ? 'var(--gold)' : 'var(--parchment-dark)',
              background: selected.includes(value) ? 'rgba(201,162,76,0.12)' : 'rgba(138,90,246,0.06)',
              fontSize: 11,
            }}
          >
            <input
              aria-label={`${labelPrefix} ${value}`}
              type="checkbox"
              checked={selected.includes(value)}
              onChange={() => onToggle(value)}
            />
            {value}
          </label>
        ))}
      </div>
    </div>
  )
}

const levelUpSelectStyle = {
  minHeight: 34,
  borderRadius: 6,
  border: '1px solid var(--wood-light)',
  background: 'var(--bg)',
  color: 'var(--parchment)',
  padding: '4px 8px',
}

function SectionTitle({ children }) {
  return (
    <p style={{
      color: 'var(--gold)', fontSize: 12, fontWeight: 700,
      textTransform: 'uppercase', letterSpacing: '0.1em',
      margin: '0 0 10px', paddingBottom: 6,
      borderBottom: '1px solid var(--wood)',
    }}>
      {children}
    </p>
  )
}

function FeatureTag({ label, value, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>{label}:</span>
      <span style={{
        fontSize: 12, padding: '2px 10px', borderRadius: 10,
        background: `${color}18`, border: `1px solid ${color}40`,
        color: color, fontWeight: 600,
      }}>{value}</span>
    </div>
  )
}
