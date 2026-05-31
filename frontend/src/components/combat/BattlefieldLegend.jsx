export default function BattlefieldLegend({
  walls = new Set(),
  hazards = new Set(),
  objectives = new Set(),
  threatCells = new Set(),
  aoeCells = { ring: new Set(), center: null },
  moveMode = false,
  helpMode = false,
  aoePreview = null,
}) {
  const items = [
    walls.size > 0 && { key: 'cover', label: 'Cover', count: walls.size },
    hazards.size > 0 && { key: 'hazard', label: 'Hazard', count: hazards.size },
    objectives.size > 0 && { key: 'objective', label: 'Objective', count: objectives.size },
    threatCells.size > 0 && { key: 'threat', label: 'Threat', count: threatCells.size },
    (aoePreview || aoeCells?.ring?.size > 0 || aoeCells?.center) && {
      key: 'aoe',
      label: 'AoE',
      count: aoeCells?.ring?.size || null,
    },
    moveMode && { key: 'move', label: 'Move' },
    helpMode && { key: 'help', label: 'Help' },
  ].filter(Boolean)

  if (!items.length) return null

  return (
    <aside className="battlefield-legend" aria-label="Battlefield legend">
      {items.map(item => (
        <span key={item.key} className={`battlefield-legend-item ${item.key}`}>
          <i aria-hidden="true" />
          <b>{item.label}</b>
          {item.count ? <em>{item.count}</em> : null}
        </span>
      ))}
    </aside>
  )
}
