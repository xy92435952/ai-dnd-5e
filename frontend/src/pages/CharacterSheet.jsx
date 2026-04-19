import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { charactersApi } from '../api/client'
import {
  BackIcon, ShieldIcon, HeartIcon, SwordIcon, DiceD20Icon,
  BookIcon, ClassIcon, MagicIcon, DefendIcon,
} from '../components/Icons'
import Portrait from '../components/Portrait'
import { classKey } from '../components/Crests'
import { Divider } from '../components/Ornaments'

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
  const navigate = useNavigate()

  const [char, setChar] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { loadCharacter() }, [characterId])

  const loadCharacter = async () => {
    try {
      const data = await charactersApi.get(characterId)
      setChar(data)
    } catch (e) {
      setError(e.message)
    }
  }

  const handleEquipToggle = async (category, index) => {
    if (!char || saving) return
    const eq = { ...char.equipment }
    if (category === 'shield') {
      if (eq.shield) {
        eq.shield = { ...eq.shield, equipped: !eq.shield.equipped }
      }
    } else {
      const list = [...(eq[category] || [])]
      list[index] = { ...list[index], equipped: !list[index].equipped }
      eq[category] = list
    }
    setSaving(true)
    try {
      const result = await charactersApi.updateEquipment(char.id, eq)
      setChar(prev => ({ ...prev, equipment: result.equipment, derived: result.derived }))
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

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
  const hpMax = derived.hp_max || char.hp_current || 1
  const hpCur = char.hp_current || 0
  const hpPct = Math.max(0, Math.min(100, Math.round((hpCur / hpMax) * 100)))
  const hpColor = hpPct > 60 ? 'var(--green-light)' : hpPct > 30 ? '#f59e0b' : 'var(--red-light)'
  const profBonus = derived.proficiency_bonus || 2
  const passivePerception = 10 + (mods.wis || 0) + ((char.proficient_skills || []).includes('感知') || (char.proficient_skills || []).includes('Perception') ? profBonus : 0)
  const eq = char.equipment || {}
  const slotsMax = derived.spell_slots_max || {}
  const slotsCur = char.spell_slots || {}

  const fmtMod = (v) => v >= 0 ? `+${v}` : `${v}`

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1 }}>
      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 20px',
        borderBottom: '1px solid var(--bark-light)',
        background: 'rgba(10,6,2,.55)',
        backdropFilter: 'blur(6px)',
        flexShrink: 0,
      }}>
        <button className="btn-ghost" style={{ fontSize: 12 }} onClick={() => navigate(-1)}>
          ⬅ 返回
        </button>
        <div className="display-title" style={{ fontSize: 16 }}>☙ 角色卡 ❧</div>
        <div style={{ width: 80 }} />
      </header>

      {/* Main content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px', maxWidth: 1000, margin: '0 auto', width: '100%' }}>
        {error && (
          <p style={{ color: '#ffaaaa', fontSize: 12, marginBottom: 12, padding: 8, background: 'rgba(139,32,32,.2)', border: '1px solid var(--blood)', borderRadius: 4 }}>{error}</p>
        )}

        {/* ── Identity Section ── */}
        <div className="panel-ornate" style={{ padding: 20, marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
            <Portrait cls={classKey(char.char_class)} size="lg" />
            <div style={{ flex: 1 }}>
              <div className="display-title" style={{ fontSize: 24, marginBottom: 4 }}>{char.name}</div>
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
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
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
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
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

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
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

        {/* ── Equipment ── */}
        <div className="panel" style={{ padding: 16, marginBottom: 16 }}>
          <SectionTitle>装备</SectionTitle>

          {/* Gold */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, padding: '8px 12px', background: 'rgba(201,168,76,0.08)', borderRadius: 6, border: '1px solid var(--gold-dim)' }}>
            <span style={{ fontSize: 16 }}>&#x1F4B0;</span>
            <span style={{ color: 'var(--gold)', fontSize: 16, fontWeight: 700 }}>{eq.gold ?? 0}</span>
            <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>gp</span>
          </div>

          {/* Weapons */}
          {(eq.weapons || []).length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <p style={{ color: 'var(--red-light)', fontSize: 11, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <SwordIcon size={11} color="var(--red-light)" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                武器
              </p>
              {eq.weapons.map((w, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                  background: w.equipped ? 'rgba(139,32,32,0.1)' : 'transparent',
                  border: `1px solid ${w.equipped ? 'var(--red)' : 'var(--wood)'}`,
                  borderRadius: 6, marginBottom: 4, cursor: 'pointer',
                }} onClick={() => handleEquipToggle('weapons', i)}>
                  <div style={{
                    width: 14, height: 14, borderRadius: 3,
                    background: w.equipped ? 'var(--red-light)' : 'transparent',
                    border: `2px solid ${w.equipped ? 'var(--red-light)' : 'var(--wood-light)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--bg)', fontSize: 10, fontWeight: 700, flexShrink: 0,
                  }}>
                    {w.equipped && '\u2713'}
                  </div>
                  <span style={{ color: 'var(--parchment)', fontSize: 12, fontWeight: 600, flex: 1 }}>{w.zh || w.name}</span>
                  {w.damage && <span style={{ color: 'var(--red-light)', fontSize: 11 }}>{w.damage}</span>}
                  {w.type && <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>{w.type}</span>}
                  {w.properties && <span style={{ color: 'var(--wood-light)', fontSize: 9 }}>{Array.isArray(w.properties) ? w.properties.join(', ') : w.properties}</span>}
                </div>
              ))}
            </div>
          )}

          {/* Armor */}
          {(eq.armor || []).length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <p style={{ color: 'var(--blue-light)', fontSize: 11, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <ShieldIcon size={11} color="var(--blue-light)" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                护甲
              </p>
              {eq.armor.map((a, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                  background: a.equipped ? 'rgba(26,58,90,0.15)' : 'transparent',
                  border: `1px solid ${a.equipped ? 'var(--blue)' : 'var(--wood)'}`,
                  borderRadius: 6, marginBottom: 4, cursor: 'pointer',
                }} onClick={() => handleEquipToggle('armor', i)}>
                  <div style={{
                    width: 14, height: 14, borderRadius: 3,
                    background: a.equipped ? 'var(--blue-light)' : 'transparent',
                    border: `2px solid ${a.equipped ? 'var(--blue-light)' : 'var(--wood-light)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--bg)', fontSize: 10, fontWeight: 700, flexShrink: 0,
                  }}>
                    {a.equipped && '\u2713'}
                  </div>
                  <span style={{ color: 'var(--parchment)', fontSize: 12, fontWeight: 600, flex: 1 }}>{a.zh || a.name}</span>
                  {a.ac != null && <span style={{ color: 'var(--blue-light)', fontSize: 11 }}>AC {a.ac}</span>}
                  {a.type && <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>{a.type}</span>}
                </div>
              ))}
            </div>
          )}

          {/* Shield */}
          {eq.shield && (
            <div style={{ marginBottom: 12 }}>
              <p style={{ color: 'var(--blue-light)', fontSize: 11, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <DefendIcon size={11} color="var(--blue-light)" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                盾牌
              </p>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                background: eq.shield.equipped ? 'rgba(26,58,90,0.15)' : 'transparent',
                border: `1px solid ${eq.shield.equipped ? 'var(--blue)' : 'var(--wood)'}`,
                borderRadius: 6, cursor: 'pointer',
              }} onClick={() => handleEquipToggle('shield', 0)}>
                <div style={{
                  width: 14, height: 14, borderRadius: 3,
                  background: eq.shield.equipped ? 'var(--blue-light)' : 'transparent',
                  border: `2px solid ${eq.shield.equipped ? 'var(--blue-light)' : 'var(--wood-light)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'var(--bg)', fontSize: 10, fontWeight: 700, flexShrink: 0,
                }}>
                  {eq.shield.equipped && '\u2713'}
                </div>
                <span style={{ color: 'var(--parchment)', fontSize: 12, fontWeight: 600, flex: 1 }}>{eq.shield.zh || eq.shield.name}</span>
                <span style={{ color: 'var(--blue-light)', fontSize: 11 }}>+{eq.shield.ac} AC</span>
              </div>
            </div>
          )}

          {/* Gear */}
          {(eq.gear || []).length > 0 && (
            <div>
              <p style={{ color: 'var(--text-dim)', fontSize: 11, fontWeight: 700, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                杂物
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {eq.gear.map((g, i) => (
                  <span key={i} className="tag tag-info">{typeof g === 'string' ? g : (g.zh || g.name || g)}</span>
                ))}
              </div>
            </div>
          )}

          {/* No equipment */}
          {!(eq.weapons?.length || eq.armor?.length || eq.shield || eq.gear?.length) && (
            <p style={{ color: 'var(--text-dim)', fontSize: 12, textAlign: 'center', padding: 16 }}>
              暂无装备数据
            </p>
          )}
        </div>

        {/* ── Spell Slots ── */}
        {Object.keys(slotsMax).length > 0 && (
          <div className="panel" style={{ padding: 16, marginBottom: 16 }}>
            <SectionTitle>
              <MagicIcon size={14} color="#8a5af6" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />
              法术位
            </SectionTitle>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 8 }}>
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
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
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
