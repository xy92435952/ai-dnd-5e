const COVER_LABELS = {
  2: 'Half cover +2 AC',
  5: '3/4 cover +5 AC',
}

const COVER_NAMES = new Set([
  'cover',
  'half cover',
  'half_cover',
  'three quarters cover',
  'three-quarters cover',
  'three_quarters_cover',
  '3/4 cover',
  'total cover',
  'total_cover',
  '掩护',
  '半掩护',
  '四分之三掩护',
  '全掩护',
])

const ADVANTAGE_NAMES = new Set(['advantage', '优势'])
const DISADVANTAGE_NAMES = new Set(['disadvantage', '劣势'])
const SOURCE_MARKER_NAMES = new Set(['攻击者状态+', '目标状态+', 'attacker state', 'target state'].map(normalizeLookup))

function asNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function normalizeText(value) {
  return String(value || '').trim()
}

function normalizeLookup(value) {
  return normalizeText(value).toLowerCase().replace(/\s+/g, ' ')
}

function pushUnique(tags, tag) {
  if (!tag?.label) return
  if (tags.some(existing => existing.key === tag.key || existing.label === tag.label)) return
  tags.push(tag)
}

function coverLabel(coverBonus) {
  if (COVER_LABELS[coverBonus]) return COVER_LABELS[coverBonus]
  if (coverBonus >= 99) return 'Total cover'
  return `Cover +${coverBonus} AC`
}

function coverTitle({ coverBonus, targetAc, effectiveAc }) {
  if (coverBonus >= 99) return 'Total cover blocks ordinary ranged attacks unless a rule says otherwise.'
  if (targetAc !== null && effectiveAc !== null && targetAc !== effectiveAc) {
    return `Cover raises AC from ${targetAc} to ${effectiveAc} for this attack.`
  }
  return 'Cover raises the target AC for this attack.'
}

function modifierIsAlreadyExplained(modifier, explainedSources = []) {
  const text = normalizeLookup(modifier)
  if (!text) return true
  if (ADVANTAGE_NAMES.has(text) || DISADVANTAGE_NAMES.has(text)) return true
  if (COVER_NAMES.has(text)) return true
  if (SOURCE_MARKER_NAMES.has(text)) return true
  if (explainedSources.some(source => normalizeLookup(source) === text)) return true
  if (text.includes('cover') || text.includes('掩护')) return true
  return false
}

export function buildCombatRuleTags(prediction = null, target = null) {
  if (!prediction) return []

  const tags = []
  const hasAdvantage = Boolean(prediction.advantage)
  const hasDisadvantage = Boolean(prediction.disadvantage)
  const advantageSources = sourceList(prediction.advantage_sources ?? prediction.advantageSources)
  const disadvantageSources = sourceList(prediction.disadvantage_sources ?? prediction.disadvantageSources)
  const hasCancelledSources = !hasAdvantage && !hasDisadvantage && advantageSources.length > 0 && disadvantageSources.length > 0
  const targetAc = asNumber(prediction.target_ac ?? prediction.target?.ac ?? target?.ac)
  const effectiveAc = asNumber(prediction.effective_target_ac ?? targetAc)
  const coverBonus = asNumber(prediction.cover_bonus)

  if ((hasAdvantage && hasDisadvantage) || hasCancelledSources) {
    pushUnique(tags, {
      key: 'flat-roll',
      label: 'Flat roll',
      tone: 'neutral',
      title: rollStateTitle(
        'Advantage and disadvantage cancel, so the attack rolls one d20.',
        advantageSources,
        disadvantageSources,
      ),
    })
  } else if (hasAdvantage) {
    pushUnique(tags, {
      key: 'advantage',
      label: 'Advantage',
      tone: 'good',
      title: rollStateTitle('Roll two d20 and use the higher result.', advantageSources, []),
    })
  } else if (hasDisadvantage) {
    pushUnique(tags, {
      key: 'disadvantage',
      label: 'Disadvantage',
      tone: 'bad',
      title: rollStateTitle('Roll two d20 and use the lower result.', [], disadvantageSources),
    })
  }

  if (advantageSources.length > 0) {
    pushUnique(tags, sourceTag('advantage-source', 'Adv', advantageSources, 'good'))
  }
  if (disadvantageSources.length > 0) {
    pushUnique(tags, sourceTag('disadvantage-source', 'Dis', disadvantageSources, 'bad'))
  }

  if (coverBonus > 0) {
    pushUnique(tags, {
      key: `cover-${coverBonus}`,
      label: coverLabel(coverBonus),
      tone: 'bad',
      title: coverTitle({ coverBonus, targetAc, effectiveAc }),
    })
  }

  if (effectiveAc !== null) {
    pushUnique(tags, {
      key: 'effective-ac',
      label: `Eff AC ${effectiveAc}`,
      tone: coverBonus > 0 ? 'warning' : 'neutral',
      title: targetAc !== null && targetAc !== effectiveAc
        ? `Base AC ${targetAc}; effective AC ${effectiveAc} after cover and modifiers.`
        : `Effective AC ${effectiveAc} for this attack.`,
    })
  }

  const modifiers = Array.isArray(prediction.modifiers) ? prediction.modifiers : []
  const explainedSources = [...advantageSources, ...disadvantageSources]
  for (const modifier of modifiers) {
    const label = normalizeText(modifier)
    if (!label || modifierIsAlreadyExplained(label, explainedSources)) continue
    pushUnique(tags, {
      key: `modifier-${normalizeLookup(label).replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-')}`,
      label,
      tone: 'neutral',
      title: `Attack modifier: ${label}.`,
    })
    if (tags.length >= 6) break
  }

  return tags.slice(0, 6)
}

function sourceList(value) {
  const values = Array.isArray(value) ? value : value ? [value] : []
  return values
    .map(sourceLabel)
    .filter(Boolean)
}

function sourceLabel(value) {
  if (typeof value === 'string') return normalizeText(value)
  if (!value || typeof value !== 'object') return ''
  return normalizeText(value.label || value.name || value.source || value.reason || value.condition)
}

function rollStateTitle(base, advantageSources = [], disadvantageSources = []) {
  const parts = [base]
  if (advantageSources.length > 0) parts.push(`Advantage sources: ${advantageSources.join(' / ')}.`)
  if (disadvantageSources.length > 0) parts.push(`Disadvantage sources: ${disadvantageSources.join(' / ')}.`)
  return parts.join(' ')
}

function sourceTag(key, prefix, sources, tone) {
  return {
    key,
    label: `${prefix}: ${compactSourceSummary(sources)}`,
    tone,
    title: `${prefix === 'Adv' ? 'Advantage' : 'Disadvantage'} sources: ${sources.join(' / ')}.`,
  }
}

function compactSourceSummary(sources) {
  if (sources.length <= 1) return sources[0]
  return `${sources[0]} +${sources.length - 1}`
}
