import React from 'react'
import Portrait from '../Portrait'
import { classKey } from '../Crests'

const ABILITY_KEYS = [
  ['str', '力量'],
  ['dex', '敏捷'],
  ['con', '体质'],
  ['int', '智力'],
  ['wis', '感知'],
  ['cha', '魅力'],
]

function compactText(value) {
  if (Array.isArray(value)) return value.filter(Boolean).join('、')
  if (typeof value === 'string') return value.trim()
  if (value == null) return ''
  return String(value)
}

function formatEquipment(equipment = {}) {
  if (!equipment || typeof equipment !== 'object') return ''

  return Object.entries(equipment)
    .flatMap(([slot, value]) => {
      const label = slot === 'weapons' || slot === 'weapon'
        ? '武器'
        : slot === 'armor'
          ? '护甲'
          : slot === 'gear'
            ? '物品'
            : slot

      const items = Array.isArray(value) ? value : [value]
      return items
        .map(item => {
          if (!item) return ''
          if (typeof item === 'string') return `${label}: ${item}`
          return `${label}: ${item.zh || item.name || item.item_name || item.label || ''}`.trim()
        })
        .filter(text => text && text !== `${label}:`)
    })
    .join('、')
}

function formatAbilityScores(scores = {}) {
  return ABILITY_KEYS
    .map(([key, label]) => {
      const score = scores?.[key]
      return score == null ? null : `${label} ${score}`
    })
    .filter(Boolean)
    .join('、')
}

function DetailBlock({ label, children, wide = false }) {
  const text = compactText(children)
  if (!text) return null

  return (
    <div className={`companion-detail-block${wide ? ' wide' : ''}`}>
      <span>{label}</span>
      <p>{text}</p>
    </div>
  )
}

export default function CharacterCreateStepPartyCompanions({ companions, generatingParty, handleGenerateParty, error }) {
  return (
    <>
      {generatingParty ? (
        <div className="companions-generating" role="status">
          <p className="companions-generating-title">
            ✦ AI 正在为你召唤伙伴… ✦
          </p>
          <p className="companions-generating-copy">
            根据你的职业分析队伍需求
          </p>
        </div>
      ) : (
        <div className="companions-grid">
          {companions.map(c => (
            <div key={c.id} className="companion-card">
              <div className="companion-card-main">
                <Portrait cls={classKey(c.char_class)} size="md" />
                <div className="cc-info">
                  <div className="cc-name">{c.name}</div>
                  <div className="cc-sub">{c.race} · {c.char_class} · Lv {c.level || 1}</div>
                  {c.personality && (
                    <div className="cc-role cc-role-clamp">
                      {c.personality}
                    </div>
                  )}
                </div>
              </div>
              <details className="companion-details" aria-label={`${c.name || '队友'} 明细`}>
                <summary>展开明细</summary>
                <div className="companion-detail-grid">
                  <DetailBlock label="战斗数据">
                    {[
                      c.hp_max || c.derived?.hp_max ? `HP ${c.hp_current ?? c.hp_max ?? c.derived?.hp_max}/${c.hp_max ?? c.derived?.hp_max}` : '',
                      c.ac || c.derived?.ac ? `AC ${c.ac ?? c.derived?.ac}` : '',
                      c.derived?.speed ? `速度 ${c.derived.speed}` : '',
                      c.derived?.proficiency_bonus ? `熟练 +${c.derived.proficiency_bonus}` : '',
                    ].filter(Boolean).join('、')}
                  </DetailBlock>
                  <DetailBlock label="属性" wide>{formatAbilityScores(c.ability_scores)}</DetailBlock>
                  <DetailBlock label="技能" wide>{c.proficient_skills}</DetailBlock>
                  <DetailBlock label="法术" wide>{[...(c.cantrips || []), ...(c.prepared_spells || []), ...(c.known_spells || [])]}</DetailBlock>
                  <DetailBlock label="装备" wide>{formatEquipment(c.equipment)}</DetailBlock>
                  <DetailBlock label="性格" wide>{c.personality || c.personality_traits}</DetailBlock>
                  <DetailBlock label="说话风格" wide>{c.speech_style}</DetailBlock>
                  <DetailBlock label="战斗偏好" wide>{c.combat_preference}</DetailBlock>
                  <DetailBlock label="口头禅" wide>{c.catchphrase}</DetailBlock>
                  <DetailBlock label="背景" wide>{c.backstory}</DetailBlock>
                </div>
              </details>
            </div>
          ))}
        </div>
      )}

      {!generatingParty && companions.length > 0 && (
        <div className="companions-regenerate-row">
          <button
            className="btn-ghost companions-regenerate-button"
            type="button"
            onClick={() => handleGenerateParty()}
          >
            🔄 重新生成队伍
          </button>
        </div>
      )}

      {error && (
        <p className="companions-error" role="alert">
          ! {error}
        </p>
      )}
    </>
  )
}
