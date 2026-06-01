import React from 'react'
import { SpellIcon, HeartIcon } from '../Icons'
import { buildConditionImpactTags } from '../../utils/conditionRules'
import { buildSpellRuleBadges, buildSpellRulePreview } from '../../utils/spellRuleBadges'

export default function SpellModalList({
  level,
  shownSpells,
  cantrips,
  caster = null,
  combat = null,
  playerId = null,
  selectedTarget = null,
  selectedSpell,
  setSelectedSpell,
  onSpellHover,
}) {
  return (
    <div className="space-y-1.5 overflow-y-auto flex-1" style={{ maxHeight:260 }}>
      {shownSpells.length === 0 ? (
        <p className="text-xs text-center py-4" style={{ color: 'var(--text-dim)' }}>
          {level === 0 ? '未习得戏法' : '当前法术位不足或无可用法术'}
        </p>
      ) : shownSpells.map(spell => {
        const isSel = selectedSpell?.name === spell.name
        const isCantrip = spell.level === 0 || cantrips?.includes(spell.name)
        const badges = buildSpellRuleBadges(spell, { isCantrip })
        const previewRows = buildSpellRulePreview(spell, { caster })
        const targetFit = buildSpellTargetFit(spell, { combat, playerId, selectedTarget })
        return (
          <div key={spell.name}
            onClick={() => setSelectedSpell(isSel ? null : spell)}
            onMouseEnter={() => onSpellHover?.(spell)}
            onMouseLeave={() => onSpellHover?.(null)}
            style={{
              padding:'8px 10px', borderRadius:6, cursor:'pointer',
              background: isSel ? (isCantrip ? 'rgba(58,122,170,0.18)' : 'rgba(138,90,246,0.18)') : 'var(--bg)',
              border: `1px solid ${isSel ? (isCantrip ? 'var(--blue-light)' : '#8a5af6') : 'var(--wood)'}`,
              transition:'all 0.1s',
            }}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold" style={{ color:'var(--parchment)' }}>
                {isCantrip
                  ? <SpellIcon size={12} color="var(--blue-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
                  : spell.type==='heal'
                    ? <HeartIcon size={12} color="var(--green-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />
                    : <SpellIcon size={12} color="var(--red-light)" style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />}
                {spell.name}
                {isCantrip && <span className="ml-1 text-xs" style={{ color:'var(--blue-light)', opacity:0.7 }}>戏法</span>}
              </span>
              <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                {spell.type==='damage' ? spell.damage : spell.heal}
              </span>
            </div>
            <div className="spell-rule-badges" aria-label={`法术规则 ${spell.name}`}>
              {badges.map(badge => <span key={`${badge.key}-${badge.label}`}>{badge.label}</span>)}
            </div>
            {targetFit.length > 0 && (
              <div className="spell-target-fit" aria-label={`目标适配 ${spell.name}`}>
                {targetFit.map(item => (
                  <span key={item.key} className={item.tone || ''} title={item.title || item.label}>
                    {item.label}
                  </span>
                ))}
              </div>
            )}
            {previewRows.length > 0 && (
              <div className="spell-rule-preview" aria-label={`法术预览 ${spell.name}`}>
                {previewRows.map(row => (
                  <span key={row.key}>
                    <b>{row.label}</b>
                    {row.value}
                  </span>
                ))}
              </div>
            )}
            {spell.desc && <p className="text-xs mt-0.5 line-clamp-1" style={{ color: 'var(--text-dim)' }}>{spell.desc}</p>}
          </div>
        )
      })}
    </div>
  )
}

function buildSpellTargetFit(spell = {}, { combat = null, playerId = null, selectedTarget = null } = {}) {
  if (!spell) return []

  if (spell.aoe) {
    return [{
      key: 'aoe-placement',
      label: '选落点',
      tone: 'warning',
      title: '范围法术通过战场落点决定目标。',
    }]
  }

  const targetText = String(spell.target_type || spell.targetType || spell.target || '').toLowerCase()
  const type = String(spell.type || '').toLowerCase()
  const selected = selectedTarget ? combat?.entities?.[selectedTarget] : null
  const selectedName = selected?.name || selectedTarget || ''
  const selectedIsSelf = selectedTarget && String(selectedTarget) === String(playerId)
  const selectedIsEnemy = selected?.is_enemy === true
  const selectedConditionFit = buildSelectedTargetConditionFit(selected)
  const wantsSelf = /self|自身/.test(targetText)
  const wantsAlly = type === 'heal' || /ally|friend|willing|队友|友方/.test(targetText)
  const wantsEnemy = type === 'damage' || /enemy|hostile|foe|敌/.test(targetText)

  if (wantsSelf) {
    return [{
      key: 'self-target',
      label: '自身',
      tone: 'good',
      title: '此法术以施法者为目标。',
    }]
  }

  if (!selectedTarget) {
    return [{
      key: 'target-needed',
      label: wantsAlly ? '选友方' : wantsEnemy ? '选敌方' : '选目标',
      tone: 'warning',
      title: '先在战场上选择一个适配目标。',
    }]
  }

  if (wantsAlly) {
    const fits = selectedIsSelf || selectedIsEnemy === false
    return [{
      key: fits ? 'target-fit' : 'target-mismatch',
      label: fits ? `目标 ${selectedName}` : '目标不匹配',
      tone: fits ? 'good' : 'bad',
      title: fits ? '当前目标可用于此法术。' : '当前选中敌方；治疗或友方法术需要队友或自己。',
    }, ...(fits ? selectedConditionFit : [])]
  }

  if (wantsEnemy) {
    const fits = selectedIsEnemy
    return [{
      key: fits ? 'target-fit' : 'target-mismatch',
      label: fits ? `目标 ${selectedName}` : '目标不匹配',
      tone: fits ? 'good' : 'bad',
      title: fits ? '当前目标可用于此法术。' : '当前选中友方；伤害或敌方法术需要敌方目标。',
    }, ...(fits ? selectedConditionFit : [])]
  }

  return selectedName
    ? [{
        key: 'target-fit',
        label: `目标 ${selectedName}`,
        tone: 'good',
        title: '当前已选择目标。',
      }, ...selectedConditionFit]
    : []
}

function buildSelectedTargetConditionFit(selected = null) {
  return buildConditionImpactTags(selected?.conditions || [], selected?.condition_durations || {})
    .slice(0, 3)
    .map(tag => ({
      key: `condition-${tag.key}`,
      label: tag.label,
      tone: tag.tone,
      title: tag.title,
    }))
}
