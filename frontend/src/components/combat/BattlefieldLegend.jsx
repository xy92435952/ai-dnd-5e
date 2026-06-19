import { buildCombatRuleTags } from '../../utils/combatRuleTags'

export default function BattlefieldLegend({
  walls = new Set(),
  hazards = new Set(),
  objectives = new Set(),
  threatCells = new Set(),
  aoeCells = { ring: new Set(), center: null },
  moveMode = false,
  helpMode = false,
  aoePreview = null,
  aoeLockedCenter = null,
  prediction = null,
}) {
  const coverPathItem = buildCoverPathLegendItem(prediction)
  const items = [
    coverPathItem,
    walls.size > 0 && { key: 'cover', label: '掩护', count: walls.size },
    hazards.size > 0 && { key: 'hazard', label: '危险', count: hazards.size },
    objectives.size > 0 && { key: 'objective', label: '目标点', count: objectives.size },
    threatCells.size > 0 && { key: 'threat', label: '威胁区', count: threatCells.size },
    (aoePreview || aoeCells?.ring?.size > 0 || aoeCells?.center) && {
      key: 'aoe',
      label: buildAoeLegendLabel({ aoePreview, aoeCells, aoeLockedCenter }),
      count: aoeCells?.ring?.size || null,
    },
    moveMode && { key: 'move', label: '移动' },
    helpMode && { key: 'help', label: '协助' },
  ].filter(Boolean)

  if (!items.length) return null

  return (
    <aside className="battlefield-legend" aria-label="战场图例" role="list">
      {items.map(item => (
        <span
          key={item.key}
          className={`battlefield-legend-item ${item.key}`}
          role="listitem"
          aria-label={legendItemLabel(item)}
          title={item.title || undefined}
        >
          <i aria-hidden="true" />
          <b>{item.label}</b>
          {item.count ? <em>{item.count}</em> : null}
        </span>
      ))}
    </aside>
  )
}

function legendItemLabel(item = {}) {
  const parts = [item.label]
  if (item.count) parts.push(`${item.count} 格`)
  if (item.title) parts.push(item.title)
  return parts.join('：')
}

function buildCoverPathLegendItem(prediction) {
  const cells = prediction?.cover_detail?.cells || prediction?.coverDetail?.cells || []
  if (!Array.isArray(cells) || cells.length === 0) return null
  const coverTag = buildCombatRuleTags(prediction, {}).find(tag => String(tag.key || '').startsWith('cover-'))
  if (!coverTag) return null
  return {
    key: 'cover-path',
    label: `${coverTag.label} 路径`,
    title: coverTag.title,
  }
}

function buildAoeLegendLabel({ aoePreview, aoeCells, aoeLockedCenter }) {
  const template = aoeCells?.template || aoePreview?.template || ''
  const templateLabel = ({
    sphere: '球形',
    cone: '锥形',
    line: '直线',
    cube: '立方',
    aura: '光环',
  })[template] || ''
  const parts = ['范围']
  if (templateLabel) parts.push(templateLabel)
  if (aoeLockedCenter) parts.push('已锁定')
  return parts.join(' ')
}
