import { formatConditionLabel } from './conditionRules'

const COVER_LABELS = {
  2: '半掩护 +2 AC',
  5: '3/4 掩护 +5 AC',
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
  if (coverBonus >= 99) return '全掩护'
  return `掩护 +${coverBonus} AC`
}

function coverTitle({ coverBonus, targetAc, effectiveAc, coverDetail = null }) {
  const rawBonus = asNumber(coverDetail?.raw_bonus ?? coverDetail?.rawBonus)
  const cells = coverCells(coverDetail)
  const path = cells.length > 0 ? `路径经过 ${cells.join(' / ')}。` : ''
  if (coverDetail?.ignored_by || coverDetail?.ignoredBy) {
    const ignoredBy = coverDetail.ignored_by || coverDetail.ignoredBy
    return `掩护原本会提供 +${rawBonus ?? coverBonus} AC，但被 ${ignoredBy} 忽略。${path}`
  }
  if (coverBonus >= 99) return '全掩护会阻挡普通远程攻击，除非有规则另行说明。'
  if (targetAc !== null && effectiveAc !== null && targetAc !== effectiveAc) {
    return `掩护使本次攻击的 AC 从 ${targetAc} 提升到 ${effectiveAc}。${path}`
  }
  return `掩护会提高本次攻击的目标 AC。${path}`
}

function modifierIsAlreadyExplained(modifier, explainedSources = []) {
  const text = normalizeLookup(modifier)
  const localizedText = normalizeLookup(localizeSourceText(modifier))
  if (!text) return true
  if (ADVANTAGE_NAMES.has(text) || DISADVANTAGE_NAMES.has(text)) return true
  if (COVER_NAMES.has(text)) return true
  if (SOURCE_MARKER_NAMES.has(text)) return true
  if (explainedSources.some(source => normalizeLookup(source) === text || normalizeLookup(source) === localizedText)) return true
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
  const coverDetail = prediction.cover_detail ?? prediction.coverDetail ?? null
  const rawCoverBonus = asNumber(coverDetail?.raw_bonus ?? coverDetail?.rawBonus)
  const ignoredCover = coverDetail && (coverDetail.ignored_by || coverDetail.ignoredBy) && rawCoverBonus > 0

  if ((hasAdvantage && hasDisadvantage) || hasCancelledSources) {
    pushUnique(tags, {
      key: 'flat-roll',
      label: '优势抵消',
      tone: 'neutral',
      title: rollStateTitle(
        '优势和劣势相互抵消，本次攻击只掷一个 d20。',
        advantageSources,
        disadvantageSources,
      ),
    })
  } else if (hasAdvantage) {
    pushUnique(tags, {
      key: 'advantage',
      label: '优势',
      tone: 'good',
      title: rollStateTitle('掷两个 d20，取较高结果。', advantageSources, []),
    })
  } else if (hasDisadvantage) {
    pushUnique(tags, {
      key: 'disadvantage',
      label: '劣势',
      tone: 'bad',
      title: rollStateTitle('掷两个 d20，取较低结果。', [], disadvantageSources),
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
      title: coverTitle({ coverBonus, targetAc, effectiveAc, coverDetail }),
    })
  } else if (ignoredCover) {
    pushUnique(tags, {
      key: 'cover-ignored',
      label: '忽略掩护',
      tone: 'good',
      title: coverTitle({ coverBonus: rawCoverBonus, targetAc, effectiveAc, coverDetail }),
    })
  }

  if (effectiveAc !== null) {
    pushUnique(tags, {
      key: 'effective-ac',
      label: `有效 AC ${effectiveAc}`,
      tone: coverBonus > 0 ? 'warning' : 'neutral',
      title: targetAc !== null && targetAc !== effectiveAc
        ? `基础 AC ${targetAc}；掩护和修正后本次攻击有效 AC ${effectiveAc}。`
        : `本次攻击有效 AC ${effectiveAc}。`,
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
      title: `攻击修正：${label}。`,
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
  if (typeof value === 'string') return localizeSourceText(value)
  if (!value || typeof value !== 'object') return ''
  return localizeSourceText(value.label || value.name || value.source || value.reason || value.condition)
}

function localizeSourceText(value) {
  const text = normalizeText(value)
  const match = text.match(/^(attacker|target)\s+([a-zA-Z][a-zA-Z0-9_\-\s]*)$/i)
  if (!match) return text

  const subject = match[1].toLowerCase() === 'attacker' ? '攻击者' : '目标'
  const rawCondition = match[2].trim()
  if (/^(state|condition|status)$/i.test(rawCondition)) return text
  const condition = formatConditionLabel(rawCondition)
  return condition ? `${subject}${condition}` : text
}

function rollStateTitle(base, advantageSources = [], disadvantageSources = []) {
  const parts = [base]
  if (advantageSources.length > 0) parts.push(`优势来源：${advantageSources.join(' / ')}。`)
  if (disadvantageSources.length > 0) parts.push(`劣势来源：${disadvantageSources.join(' / ')}。`)
  return parts.join('')
}

function sourceTag(key, prefix, sources, tone) {
  const labelPrefix = prefix === 'Adv' ? '优势' : '劣势'
  return {
    key,
    label: `${labelPrefix}: ${compactSourceSummary(sources)}`,
    sources,
    tone,
    title: `${labelPrefix}来源：${sources.join(' / ')}。`,
  }
}

function compactSourceSummary(sources) {
  if (sources.length <= 1) return sources[0]
  return `${sources[0]} +${sources.length - 1}`
}

function coverCells(coverDetail = null) {
  const cells = Array.isArray(coverDetail?.cells) ? coverDetail.cells : []
  return cells.slice(0, 4).map(cell => {
    if (typeof cell === 'string') return cell
    if (!cell || typeof cell !== 'object') return ''
    const name = normalizeText(cell.label || cell.name || cell.cell || '')
    const terrain = normalizeText(cell.terrain || cell.type || cell.kind || '')
    return terrain && name ? `${name} ${terrain}` : name || terrain
  }).filter(Boolean)
}
