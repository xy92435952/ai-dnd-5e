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
import MagicInitiateChoiceFields from '../components/feats/MagicInitiateChoiceFields'
import {
  buildLevelUpAbilityChoicePlan,
  buildLevelUpFeatChoicePlan,
  buildLevelUpFightingStyleChoicePlan,
  buildLevelUpManeuverChoicePlan,
  buildLevelUpSpellChoicePlan,
  buildLevelUpSubclassChoicePlan,
} from '../utils/levelUpSpellChoices'
import {
  FEAT_ABILITY_OPTIONS,
  buildDefaultMagicInitiateChoice,
  featRequiresAbilityChoice,
  featRequiresMagicInitiateChoices,
  getMagicInitiateSelectionFailure,
  normalizeFeatAbility,
} from '../utils/characterCreate'

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

const LEVEL_UP_DESCRIPTION_KEYS = ['desc', 'description', 'summary', 'effect', 'details', 'text']

function levelUpOptionLabel(option, fallback = '') {
  if (typeof option === 'string') return option
  const primary = option?.label || option?.name || option?.id || fallback
  const secondary = option?.zh && option.zh !== primary ? option.zh : ''
  return secondary ? `${primary} - ${secondary}` : primary
}

function levelUpOptionDescription(option) {
  if (!option || typeof option === 'string') return ''
  const detail = LEVEL_UP_DESCRIPTION_KEYS.map(key => option[key]).find(Boolean)
  if (Array.isArray(detail)) return detail.filter(Boolean).join(' ')
  return typeof detail === 'string' ? detail : ''
}

function levelUpChoiceValue(option) {
  if (typeof option === 'string') return option
  return option?.value || option?.id || option?.name || ''
}

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
    featAbility: '',
    magicInitiateClass: '',
    magicInitiateCantrips: [],
    magicInitiateSpell: '',
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
      featAbility: '',
      magicInitiateClass: '',
      magicInitiateCantrips: [],
      magicInitiateSpell: '',
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
      const next = { ...prev, [key]: [...current, value] }
      if (kind === 'spell' && next.replacementNew === value) next.replacementNew = ''
      return next
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
      return {
        ...prev,
        abilityIncreases: nextIncreases,
        featName: '',
        featAbility: '',
        magicInitiateClass: '',
        magicInitiateCantrips: [],
        magicInitiateSpell: '',
      }
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
    if (levelUpSelections.featName) {
      payload.feat_choice = { name: levelUpSelections.featName }
      if (featRequiresAbilityChoice(payload.feat_choice)) {
        payload.feat_choice.ability = normalizeFeatAbility(levelUpSelections.featAbility)
      }
      if (featRequiresMagicInitiateChoices(payload.feat_choice)) {
        payload.feat_choice.spellcasting_class = levelUpSelections.magicInitiateClass
        payload.feat_choice.cantrips = levelUpSelections.magicInitiateCantrips
        payload.feat_choice.spell = levelUpSelections.magicInitiateSpell
      }
    }
    else if (Object.keys(abilityIncreases).length) payload.ability_score_increases = abilityIncreases
    if (levelUpSelections.subclassName) payload.subclass_choice = levelUpSelections.subclassName
    if (levelUpSelections.fightingStyleName) payload.fighting_style_choice = levelUpSelections.fightingStyleName
    if (levelUpSelections.maneuvers.length) payload.maneuver_choices = levelUpSelections.maneuvers
    if (levelUpSelections.spells.length) payload.learned_spells = levelUpSelections.spells
    if (levelUpSelections.cantrips.length) payload.learned_cantrips = levelUpSelections.cantrips
    const selectedLearnedSpells = new Set(levelUpSelections.spells || [])
    const hasReplacementOverlap = selectedLearnedSpells.has(levelUpSelections.replacementOld)
      || selectedLearnedSpells.has(levelUpSelections.replacementNew)
    if (levelUpSelections.replacementOld && levelUpSelections.replacementNew && !hasReplacementOverlap) {
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
      <main className="character-sheet-state-shell" aria-label="角色卡加载失败">
        <div className="character-sheet-state-panel">
          <p className="character-sheet-state-error" role="alert">{error}</p>
          <button type="button" className="btn-fantasy character-sheet-state-back" onClick={() => navigate(-1)}>
            <BackIcon size={14} className="character-sheet-inline-icon" /> 返回
          </button>
        </div>
      </main>
    )
  }

  if (!char) {
    return (
      <main className="character-sheet-state-shell" aria-label="角色卡加载中">
        <p className="character-sheet-loading-text" role="status">加载角色数据...</p>
      </main>
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
  const coreStats = [
    {
      key: 'hp',
      label: '生命值',
      value: `${hpCur} / ${hpMax}`,
      tone: 'hp',
      valueStyle: { '--character-sheet-stat-color': hpColor },
      icon: <HeartIcon size={12} color={hpColor} className="character-sheet-stat-icon" />,
      meter: {
        value: hpCur,
        max: hpMax,
        percent: hpPct,
        color: hpColor,
      },
    },
    {
      key: 'ac',
      label: '护甲等级',
      value: derived.ac || 10,
      tone: 'ac',
      icon: <ShieldIcon size={12} color="var(--blue-light)" className="character-sheet-stat-icon" />,
    },
    {
      key: 'initiative',
      label: '先攻',
      value: fmtMod(derived.initiative || 0),
      tone: 'initiative',
      icon: <DiceD20Icon size={12} color="var(--gold)" className="character-sheet-stat-icon" />,
    },
    {
      key: 'prof-passive',
      label: '熟练 / 被动感知',
      value: (
        <>
          +{profBonus} <span className="character-sheet-stat-separator">/</span> {passivePerception}
        </>
      ),
      tone: 'passive',
      compact: true,
    },
  ]

  return (
    <main className="character-sheet-page" aria-label={`角色卡：${char.name}`}>
      {/* Header */}
      <header className="character-sheet-header" aria-label="角色卡顶部栏">
        <button type="button" className="btn-ghost character-sheet-back" onClick={() => navigate(-1)}>
          ⬅ 返回
        </button>
        <div className="display-title character-sheet-header-title">☙ 角色卡 ❧</div>
        <div className="character-sheet-header-spacer" />
      </header>

      {/* Main content */}
      <div className="character-sheet-content">
        {error && (
          <p className="character-sheet-inline-error" role="alert">{error}</p>
        )}

        {/* ── Identity Section ── */}
        <section className="panel-ornate character-sheet-identity-card" aria-label="角色身份">
          <div className="character-sheet-identity-row">
            <Portrait cls={classKey(char.char_class)} size="lg" />
            <div className="character-sheet-identity-body">
              <div className="display-title character-sheet-name">{char.name}</div>
              <div className="eyebrow character-sheet-identity-meta">
                {char.race} · {char.char_class} · Lv{char.level}
                {char.subclass && ` · ${char.subclass}`}
              </div>
              {char.background && (
                <p className="character-sheet-background">
                  {char.background}
                  {char.alignment && ` · ${char.alignment}`}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ── Core Stats Row ── */}
        <section className="character-sheet-core-grid" aria-label="核心数值" role="list">
          {coreStats.map(stat => (
            <article
              key={stat.key}
              className={`panel character-sheet-stat-card character-sheet-stat-card-${stat.tone}`}
              role="listitem"
              aria-label={`${stat.label} ${typeof stat.value === 'string' || typeof stat.value === 'number' ? stat.value : ''}`.trim()}
            >
              <p className="character-sheet-stat-label">
                {stat.icon}
                {stat.label}
              </p>
              {stat.meter && (
                <div
                  className="character-sheet-hp-meter"
                  role="meter"
                  aria-label="生命值比例"
                  aria-valuemin="0"
                  aria-valuemax={stat.meter.max}
                  aria-valuenow={stat.meter.value}
                >
                  <div
                    className="character-sheet-hp-meter-fill"
                    style={{
                      '--character-sheet-hp-width': `${stat.meter.percent}%`,
                      '--character-sheet-hp-color': stat.meter.color,
                    }}
                  />
                </div>
              )}
              <p
                className={`character-sheet-stat-value${stat.compact ? ' character-sheet-stat-value-compact' : ''}`}
                style={stat.valueStyle}
              >
                {stat.value}
              </p>
            </article>
          ))}
        </section>

        {/* ── Ability Scores ── */}
        <section className="panel character-sheet-ability-panel" aria-label="能力值">
          <SectionTitle>能力值</SectionTitle>
          <div className="character-sheet-ability-grid" role="list" aria-label="能力值列表">
            {Object.entries(ABILITY_LABELS).map(([key, label]) => {
              const score = scores[key] || 10
              const mod = mods[key] || 0
              return (
                <article
                  key={key}
                  className="ability-card character-sheet-ability-card"
                  role="listitem"
                  aria-label={`${label.zh} ${score} ${fmtMod(mod)}`}
                >
                  <p className="label character-sheet-ability-label">
                    {label.zh}
                  </p>
                  <p className="score character-sheet-ability-score">{score}</p>
                  <p className={`mod character-sheet-ability-mod${mod < 0 ? ' neg' : ''}`}>
                    {fmtMod(mod)}
                  </p>
                </article>
              )
            })}
          </div>
        </section>

        <div className="character-sheet-two-column-grid">
          {/* ── Saving Throws ── */}
          <section className="panel character-sheet-check-panel" aria-label="豁免检定">
            <SectionTitle>豁免检定</SectionTitle>
            <div className="character-sheet-check-list" role="list" aria-label="豁免检定列表">
              {Object.entries(ABILITY_LABELS).map(([key, label]) => {
                const prof = (char.proficient_saves || []).includes(key)
                const val = saves[key] || (mods[key] || 0)
                return (
                  <div
                    key={key}
                    className="character-sheet-check-row"
                    data-proficient={prof ? 'true' : 'false'}
                    role="listitem"
                    aria-label={`${label.zh} ${fmtMod(val)}${prof ? ' 熟练' : ''}`}
                  >
                    <span className="character-sheet-proficiency-dot" aria-hidden="true" />
                    <span className="character-sheet-check-label">{label.zh}</span>
                    <span className="character-sheet-check-value">
                      {fmtMod(val)}
                    </span>
                  </div>
                )
              })}
            </div>
          </section>

          {/* ── Skills ── */}
          <section className="panel character-sheet-check-panel" aria-label="技能">
            <SectionTitle>技能</SectionTitle>
            <div className="character-sheet-skill-list" role="list" aria-label="技能列表">
              {ALL_SKILLS.map(skill => {
                const prof = (char.proficient_skills || []).includes(skill)
                const abilKey = SKILL_ABILITY_MAP[skill] || 'str'
                const mod = mods[abilKey] || 0
                const val = prof ? mod + profBonus : mod
                return (
                  <div
                    key={skill}
                    className="character-sheet-skill-row"
                    data-proficient={prof ? 'true' : 'false'}
                    role="listitem"
                    aria-label={`${skill} ${ABILITY_LABELS[abilKey]?.en || abilKey} ${fmtMod(val)}${prof ? ' 熟练' : ''}`}
                  >
                    <span className="character-sheet-proficiency-dot character-sheet-proficiency-dot-sm" aria-hidden="true" />
                    <span className="character-sheet-skill-label">
                      {skill}
                      <span className="character-sheet-skill-ability">({ABILITY_LABELS[abilKey]?.en})</span>
                    </span>
                    <span className="character-sheet-check-value">
                      {fmtMod(val)}
                    </span>
                  </div>
                )
              })}
            </div>
          </section>
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
          <section className="panel character-sheet-spell-slot-panel" aria-label="法术位">
            <SectionTitle>
              <MagicIcon size={14} className="character-sheet-section-icon" />
              法术位
            </SectionTitle>
            <div className="character-sheet-spell-slot-grid" role="list" aria-label="法术位列表">
              {Object.entries(slotsMax).map(([lvl, max]) => {
                const cur = slotsCur[lvl] ?? max
                return (
                  <article
                    key={lvl}
                    className="character-sheet-spell-slot-card"
                    role="listitem"
                    aria-label={`${lvl[0]}环法术位 ${cur}/${max}`}
                  >
                    <p className="character-sheet-spell-slot-level">
                      {lvl[0]}环
                    </p>
                    <div className="character-sheet-spell-slot-pips" aria-hidden="true">
                      {Array.from({ length: max }).map((_, i) => (
                        <span
                          key={i}
                          className={`character-sheet-spell-slot-pip${i < cur ? ' filled' : ''}`}
                        />
                      ))}
                    </div>
                    <p className="character-sheet-spell-slot-count">{cur}/{max}</p>
                  </article>
                )
              })}
            </div>
          </section>
        )}

        {/* ── Known / Prepared Spells ── */}
        {((char.cantrips || []).length > 0 || (char.known_spells || []).length > 0) && (
          <section className="panel character-sheet-spell-list-panel" aria-label="法术列表">
            <SectionTitle>
              <BookIcon size={14} className="character-sheet-section-icon" />
              法术列表
            </SectionTitle>

            {(char.cantrips || []).length > 0 && (
              <div className="character-sheet-spell-group">
                <p className="character-sheet-spell-group-title character-sheet-spell-group-title-cantrip">
                  戏法 (无限使用)
                </p>
                <div className="character-sheet-spell-tag-list" role="list" aria-label="戏法列表">
                  {char.cantrips.map(s => (
                    <span
                      key={s}
                      className="character-sheet-spell-tag character-sheet-spell-tag-cantrip"
                      role="listitem"
                      aria-label={s}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {(char.prepared_spells || []).length > 0 && (
              <div className="character-sheet-spell-group">
                <p className="character-sheet-spell-group-title character-sheet-spell-group-title-prepared">
                  已准备法术
                </p>
                <div className="character-sheet-spell-tag-list" role="list" aria-label="已准备法术列表">
                  {char.prepared_spells.map(s => (
                    <span
                      key={s}
                      className="character-sheet-spell-tag character-sheet-spell-tag-prepared"
                      role="listitem"
                      aria-label={s}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {(char.known_spells || []).length > 0 && (
              <div className="character-sheet-spell-group">
                <p className="character-sheet-spell-group-title character-sheet-spell-group-title-known">
                  已知法术
                </p>
                <div className="character-sheet-spell-tag-list" role="list" aria-label="已知法术列表">
                  {char.known_spells.map(s => (
                    <span
                      key={s}
                      className="character-sheet-spell-tag character-sheet-spell-tag-known"
                      role="listitem"
                      aria-label={s}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>
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
    </main>
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
  const selectedLearnedSpells = new Set(selections.spells || [])
  const replacementNewOptions = (spellPlan?.replacementNewOptions || [])
    .filter(spell => !selectedLearnedSpells.has(spell))
  const hasReplacementChoices = spellPlan?.canReplaceSpell && replacementNewOptions.length > 0
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
  const selectedFeat = (featPlan?.featOptions || []).find(feat => feat.name === selections.featName)
  const selectedFeatRequiresAbility = featRequiresAbilityChoice(selectedFeat || { name: selections.featName })
  const selectedFeatRequiresMagicInitiate = featRequiresMagicInitiateChoices(selectedFeat || { name: selections.featName })
  const selectedFeatMagicInitiateFailure = selectedFeatRequiresMagicInitiate
    ? getMagicInitiateSelectionFailure({
      name: selections.featName,
      spellcasting_class: selections.magicInitiateClass,
      cantrips: selections.magicInitiateCantrips,
      spell: selections.magicInitiateSpell,
    }, featPlan?.magicInitiateSpellOptions || {})
    : ''
  const hasProgressionChoices = hasSpellChoices || hasCantripChoices || hasReplacementChoices
    || hasAbilityChoices || hasFeatChoices || hasSubclassChoices || hasFightingStyleChoices || hasManeuverChoices
  const hasCompletedAsiChoice = !hasAbilityChoices
    || Boolean(
      selections.featName
      && selectedFeat
      && !selectedFeat.unavailableReason
      && (!selectedFeatRequiresAbility || normalizeFeatAbility(selections.featAbility))
      && !selectedFeatMagicInitiateFailure
    )
    || selectedAbilityTotal === abilityPlan.abilityCapacity
  const hasCompletedSubclassChoice = !hasSubclassChoices || Boolean(selections.subclassName)
  const hasCompletedFightingStyleChoice = !hasFightingStyleChoices || Boolean(selections.fightingStyleName)
  const hasCompletedManeuverChoice = !hasManeuverChoices || selectedManeuverCount === maneuverPlan.requiredChoices
  const canSubmitLevelUp = hasCompletedAsiChoice
    && hasCompletedSubclassChoice
    && hasCompletedFightingStyleChoice
    && hasCompletedManeuverChoice
  const selectedSubclass = (subclassPlan?.subclassOptions || [])
    .find(option => levelUpChoiceValue(option) === selections.subclassName)
  const selectedFightingStyle = (fightingStylePlan?.styleOptions || [])
    .find(option => levelUpChoiceValue(option) === selections.fightingStyleName)

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
                <option key={option.name} value={option.name}>{levelUpOptionLabel(option, option.name)}</option>
              ))}
            </select>
          </label>
          <LevelUpOptionDetail option={selectedSubclass} />
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
          <LevelUpOptionDetail option={selectedFightingStyle} />
        </div>
      )}

      {hasManeuverChoices && (
        <LevelUpChoiceGroup
          title={`Maneuvers ${selectedManeuverCount}/${maneuverPlan.requiredChoices}`}
          values={maneuverPlan.maneuverOptions}
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
              onChange={(event) => {
                const magicInitiateChoice = featRequiresMagicInitiateChoices({ name: event.target.value })
                  ? buildDefaultMagicInitiateChoice(featPlan?.magicInitiateSpellOptions || {})
                  : { spellcasting_class: '', cantrips: [], spell: '' }
                onSelectionChange(prev => ({
                  ...prev,
                  featName: event.target.value,
                  featAbility: featRequiresAbilityChoice({ name: event.target.value })
                    ? FEAT_ABILITY_OPTIONS[0].value
                    : '',
                  magicInitiateClass: magicInitiateChoice.spellcasting_class,
                  magicInitiateCantrips: magicInitiateChoice.cantrips,
                  magicInitiateSpell: magicInitiateChoice.spell,
                  abilityIncreases: {},
                }))
              }}
              style={levelUpSelectStyle}
            >
              <option value="">No feat</option>
              {featPlan.featOptions.map(feat => (
                <option key={feat.name} value={feat.name} disabled={Boolean(feat.unavailableReason)}>
                  {feat.zh ? `${feat.name} - ${feat.zh}` : feat.name}
                  {feat.unavailableReason ? ` (${feat.unavailableReason})` : ''}
                </option>
              ))}
            </select>
          </label>
          {selectedFeat?.prereq && (
            <p style={{ color: 'var(--gold-dim)', fontSize: 10, margin: '6px 0 0' }}>
              Prerequisite: {selectedFeat.prereq}
            </p>
          )}
          {selectedFeat?.unavailableReason && (
            <p style={{ color: 'var(--red-light)', fontSize: 10, margin: '6px 0 0' }}>
              {selectedFeat.unavailableReason}
            </p>
          )}
          {selectedFeatRequiresAbility && (
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--text-dim)', fontSize: 11, marginTop: 8 }}>
              Ability
              <select
                aria-label="Feat ability choice"
                value={normalizeFeatAbility(selections.featAbility)}
                onChange={(event) => onSelectionChange(prev => ({
                  ...prev,
                  featAbility: event.target.value,
                }))}
                style={levelUpSelectStyle}
              >
                {FEAT_ABILITY_OPTIONS.map(option => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
          )}
          {selectedFeatRequiresMagicInitiate && (
            <>
              <MagicInitiateChoiceFields
                value={{
                  spellcasting_class: selections.magicInitiateClass,
                  cantrips: selections.magicInitiateCantrips,
                  spell: selections.magicInitiateSpell,
                }}
                options={featPlan?.magicInitiateSpellOptions || {}}
                onChange={(choice) => onSelectionChange(prev => ({
                  ...prev,
                  magicInitiateClass: choice.spellcasting_class,
                  magicInitiateCantrips: choice.cantrips,
                  magicInitiateSpell: choice.spell,
                }))}
                selectStyle={levelUpSelectStyle}
              />
              {selectedFeatMagicInitiateFailure && (
                <p style={{ color: 'var(--red-light)', fontSize: 10, margin: '6px 0 0' }}>
                  {selectedFeatMagicInitiateFailure}
                </p>
              )}
            </>
          )}
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
              {replacementNewOptions.map(spell => (
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

function LevelUpOptionDetail({ option }) {
  const description = levelUpOptionDescription(option)
  if (!description) return null
  return (
    <p style={{ color: 'var(--text-dim)', fontSize: 11, lineHeight: 1.4, margin: '6px 0 0' }}>
      {description}
    </p>
  )
}

function LevelUpChoiceGroup({ title, values, selected, onToggle, labelPrefix }) {
  const items = (values || [])
    .map(option => {
      const value = levelUpChoiceValue(option)
      return {
        value,
        label: levelUpOptionLabel(option, value),
        description: levelUpOptionDescription(option),
      }
    })
    .filter(item => item.value)

  return (
    <div style={{ marginTop: 10 }}>
      <p style={{ color: 'var(--gold-dim)', fontSize: 10, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase' }}>
        {title}
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {items.map(item => (
          <label
            key={item.value}
            style={{
              display: 'inline-flex',
              alignItems: 'flex-start',
              flexDirection: 'column',
              gap: 5,
              minHeight: 28,
              maxWidth: item.description ? 260 : '100%',
              padding: '4px 9px',
              borderRadius: 6,
              border: '1px solid var(--wood-light)',
              color: selected.includes(item.value) ? 'var(--gold)' : 'var(--parchment-dark)',
              background: selected.includes(item.value) ? 'rgba(201,162,76,0.12)' : 'rgba(138,90,246,0.06)',
              fontSize: 11,
            }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <input
                aria-label={`${labelPrefix} ${item.label}`}
                type="checkbox"
                checked={selected.includes(item.value)}
                onChange={() => onToggle(item.value)}
              />
              <span>{item.label}</span>
            </span>
            {item.description && (
              <span style={{ color: 'var(--text-dim)', fontSize: 10, lineHeight: 1.35, marginLeft: 20, wordBreak: 'break-word' }}>
                {item.description}
              </span>
            )}
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
    <p className="character-sheet-section-title">
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
