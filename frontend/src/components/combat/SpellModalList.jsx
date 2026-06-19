import React from 'react'
import { SpellIcon, HeartIcon } from '../Icons'
import { buildConditionImpactTags } from '../../utils/conditionRules'
import { buildSpellAttackDefenseSummary, buildSpellSaveDefenseSummary } from '../../utils/spellCastPlan'
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
  const listStatus = level === 0 ? '未习得戏法' : '当前法术位不足或无可用法术'
  const selectSpell = (spell, isSelected) => {
    setSelectedSpell(isSelected ? null : spell)
  }
  const handleSpellKeyDown = (event, spell, isSelected) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    selectSpell(spell, isSelected)
  }

  if (shownSpells.length === 0) {
    return (
      <div className="spell-modal-list spell-modal-list-empty" role="status" aria-label="法术列表状态">
        {listStatus}
      </div>
    )
  }

  return (
    <div className="spell-modal-list" role="listbox" aria-label="可选法术">
      {shownSpells.map(spell => {
        const isSel = selectedSpell?.name === spell.name
        const isCantrip = spell.level === 0 || cantrips?.includes(spell.name)
        const spellType = String(spell.type || '').toLowerCase()
        const toneClass = isCantrip ? 'is-cantrip' : spellType === 'heal' ? 'is-heal' : 'is-damage'
        const badges = buildSpellRuleBadges(spell, { isCantrip })
        const previewRows = buildSpellRulePreview(spell, { caster })
        const targetFit = buildSpellTargetFit(spell, { combat, playerId, selectedTarget })
        const spellOutput = spellType === 'damage' ? spell.damage : spell.heal
        return (
          <div
            key={spell.name}
            role="option"
            aria-selected={isSel}
            aria-label={`${isSel ? '已选择' : '选择'} ${spell.name}`}
            tabIndex={0}
            className={`spell-modal-list-item ${toneClass} ${isSel ? 'selected' : ''}`}
            onClick={() => selectSpell(spell, isSel)}
            onKeyDown={(event) => handleSpellKeyDown(event, spell, isSel)}
            onMouseEnter={() => onSpellHover?.(spell)}
            onMouseLeave={() => onSpellHover?.(null)}
            onFocus={() => onSpellHover?.(spell)}
            onBlur={() => onSpellHover?.(null)}
          >
            <div className="spell-modal-list-head">
              <span className="spell-modal-list-name">
                {isCantrip
                  ? <SpellIcon size={12} className="spell-modal-list-icon is-cantrip" />
                  : spellType === 'heal'
                    ? <HeartIcon size={12} className="spell-modal-list-icon is-heal" />
                    : <SpellIcon size={12} className="spell-modal-list-icon is-damage" />}
                {spell.name}
                {isCantrip && <span className="spell-modal-list-cantrip">戏法</span>}
              </span>
              {spellOutput && <span className="spell-modal-list-output">{spellOutput}</span>}
            </div>
            <div className="spell-rule-badges" role="list" aria-label={`法术规则 ${spell.name}`}>
              {badges.map(badge => (
                <span key={`${badge.key}-${badge.label}`} role="listitem">
                  {badge.label}
                </span>
              ))}
            </div>
            {targetFit.length > 0 && (
              <div className="spell-target-fit" role="list" aria-label={`目标适配 ${spell.name}`}>
                {targetFit.map(item => (
                  <span key={item.key} role="listitem" className={item.tone || ''} title={item.title || item.label}>
                    {item.label}
                  </span>
                ))}
              </div>
            )}
            {previewRows.length > 0 && (
              <div className="spell-rule-preview" role="list" aria-label={`法术预览 ${spell.name}`}>
                {previewRows.map(row => (
                  <span key={row.key} role="listitem">
                    <b>{row.label}</b>
                    {row.value}
                  </span>
                ))}
              </div>
            )}
            {spell.desc && <p className="spell-modal-list-desc">{spell.desc}</p>}
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
  const selectedDefenseFit = buildSelectedTargetDefenseFit(spell, { combat, playerId, selectedTarget })
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
    }, ...(fits ? selectedDefenseFit : []), ...(fits ? selectedConditionFit : [])]
  }

  if (wantsEnemy) {
    const fits = selectedIsEnemy
    return [{
      key: fits ? 'target-fit' : 'target-mismatch',
      label: fits ? `目标 ${selectedName}` : '目标不匹配',
      tone: fits ? 'good' : 'bad',
      title: fits ? '当前目标可用于此法术。' : '当前选中友方；伤害或敌方法术需要敌方目标。',
    }, ...(fits ? selectedDefenseFit : []), ...(fits ? selectedConditionFit : [])]
  }

  return selectedName
    ? [{
        key: 'target-fit',
        label: `目标 ${selectedName}`,
        tone: 'good',
        title: '当前已选择目标。',
      }, ...selectedDefenseFit, ...selectedConditionFit]
    : []
}

function buildSelectedTargetDefenseFit(spell, { combat = null, playerId = null, selectedTarget = null } = {}) {
  const summary = buildSpellSaveDefenseSummary({ spell, combat, playerId, targetId: selectedTarget })
    || buildSpellAttackDefenseSummary({ spell, combat, playerId, targetId: selectedTarget })
  return summary
    ? [{
        key: 'target-defense',
        label: summary.compactLabel,
        tone: summary.tone,
        title: summary.title,
      }]
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
