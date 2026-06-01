import { useMemo, useState } from 'react'
import Overlay from './Overlay'
import { getLocationGraphMap } from '../../utils/locationGraph'

function findNode(nodes, id) {
  return nodes.find(node => String(node.id) === String(id))
}

function edgeClass(edge) {
  return [
    'location-map-edge',
    edge.locked ? 'locked' : '',
    edge.hidden ? 'hidden' : '',
  ].filter(Boolean).join(' ')
}

function valueList(values) {
  return Array.isArray(values) ? values.filter(Boolean) : []
}

function DetailPills({ values, empty = 'None' }) {
  const items = valueList(values)
  if (!items.length) return <p className="location-map-muted">{empty}</p>
  return (
    <div className="location-map-pill-list">
      {items.map(value => <span key={value}>{value}</span>)}
    </div>
  )
}

function routeBadges(route) {
  const badges = []
  if (route.locked) badges.push('locked')
  if (route.oneWay) badges.push('one-way')
  if (route.requiresKey) badges.push(`key: ${route.requiresKey}`)
  if (route.dc != null) badges.push(`${route.checkType || 'check'} DC ${route.dc}`)
  if (!badges.length && route.label) badges.push(route.label)
  return badges
}

function RouteList({ routes }) {
  if (!routes?.length) return <p className="location-map-muted">No exits recorded.</p>
  return (
    <ul className="location-map-route-list">
      {routes.map(route => (
        <li key={`${route.id}-${route.destinationId}`} className={route.locked ? 'locked' : ''}>
          <span>{route.destinationName}</span>
          <div className="location-map-route-meta">
            {routeBadges(route).map(badge => <b key={badge}>{badge}</b>)}
          </div>
        </li>
      ))}
    </ul>
  )
}

function EncounterCard({ encounter, selecting, disabled = false, disabledReason = '', onSelectEncounter }) {
  const canSelect = encounter.status === 'available' && !encounter.selected && onSelectEncounter && !disabled
  return (
    <article className="location-encounter-card">
      <div className="location-encounter-card-head">
        <strong>{encounter.name}</strong>
        <span>{encounter.selected ? 'active' : encounter.status}</span>
      </div>
      <div className="location-encounter-meta">
        {encounter.difficulty && <span>{encounter.difficulty}</span>}
        {encounter.xpBudget != null && <span>{encounter.xpBudget} XP</span>}
        {encounter.environmentPressureTags.map(tag => <span key={tag}>{tag}</span>)}
      </div>
      <DetailPills values={encounter.enemyNames} empty="No enemies listed." />
      {encounter.enemyRoles.length > 0 && (
        <p className="location-map-muted">
          {encounter.enemyRoles.map(role => `${role.name}${role.role ? `: ${role.role}` : ''}`).join(' / ')}
        </p>
      )}
      <div className="location-encounter-columns">
        <div>
          <h5>Terrain</h5>
          <DetailPills values={[...encounter.terrain, ...encounter.cover]} />
        </div>
        <div>
          <h5>Objectives</h5>
          <DetailPills values={encounter.objectives} />
        </div>
        <div>
          <h5>Hazards</h5>
          <DetailPills values={encounter.hazards} />
        </div>
        <div>
          <h5>Rewards</h5>
          <DetailPills values={encounter.rewardHints} />
        </div>
      </div>
      {encounter.tactics && <p className="location-map-muted">{encounter.tactics}</p>}
      {onSelectEncounter && (
        <button
          type="button"
          className="btn-fantasy location-encounter-select"
          disabled={!canSelect || selecting}
          title={disabled ? disabledReason : undefined}
          onClick={() => onSelectEncounter(encounter.id)}
        >
          {selecting ? 'Setting...' : encounter.selected ? 'Active' : 'Set active'}
        </button>
      )}
    </article>
  )
}

function NodeMarker({ node, selected, onSelect }) {
  const className = [
    'location-map-node',
    node.current ? 'current' : '',
    selected ? 'selected' : '',
    node.visited ? 'visited' : 'unknown',
    node.encounterCount > 0 ? 'has-encounter' : '',
  ].filter(Boolean).join(' ')

  return (
    <button
      type="button"
      className={className}
      style={{ left: `${node.x}%`, top: `${node.y}%` }}
      title={[node.name, node.description, node.encounterNames.join(' / ')].filter(Boolean).join('\n')}
      aria-label={`${node.name}${node.current ? ' current' : ''}${node.visited ? ' visited' : ' unvisited'}`}
      aria-pressed={selected}
      onClick={() => onSelect(node.id)}
    >
      <span className="location-map-node-dot" />
      <span className="location-map-node-name">{node.name}</span>
      {node.encounterCount > 0 && <span className="location-map-node-badge">{node.encounterCount}</span>}
    </button>
  )
}

export default function LocationMapModal({
  graph,
  selectingTemplateId = '',
  disabled = false,
  disabledReason = '',
  onSelectEncounter,
  onClose,
}) {
  const map = getLocationGraphMap(graph)
  const blockReason = disabledReason || '房间正在重新同步，请恢复连接后再选择遭遇。'
  const [selectedId, setSelectedId] = useState(map?.currentId || '')
  const selectedNode = useMemo(() => (
    map?.nodes.find(node => String(node.id) === String(selectedId)) || map?.currentNode || null
  ), [map, selectedId])

  return (
    <Overlay onClose={onClose}>
      <div className="location-map-head">
        <div>
          <h3>Map</h3>
          <p>{map?.currentNode?.name || 'No mapped location'}</p>
        </div>
        <button onClick={onClose} aria-label="Close map">x</button>
      </div>

      {!map ? (
        <p className="checkpoint-empty">No location graph is available yet.</p>
      ) : (
        <>
          <div className="location-map-summary" aria-label="Map summary">
            <span><b>{map.visitedCount}</b> visited</span>
            <span><b>{map.totalCount}</b> locations</span>
            {map.encounterCount > 0 && <span><b>{map.encounterCount}</b> encounters</span>}
          </div>

          <div className="location-map-canvas" aria-label="Location map">
            <svg className="location-map-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              {map.edges.map(edge => {
                const from = findNode(map.nodes, edge.from)
                const to = findNode(map.nodes, edge.to)
                if (!from || !to) return null
                return (
                  <line
                    key={edge.id}
                    className={edgeClass(edge)}
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                  />
                )
              })}
            </svg>
            {map.nodes.map(node => (
              <NodeMarker
                key={node.id}
                node={node}
                selected={String(selectedNode?.id) === String(node.id)}
                onSelect={setSelectedId}
              />
            ))}
          </div>

          <div className="location-map-detail-grid">
            <section>
              <h4>{selectedNode?.current ? 'Current' : 'Selected'}</h4>
              <strong>{selectedNode?.name}</strong>
              {selectedNode?.description && <p>{selectedNode.description}</p>}
              {selectedNode?.encounterCount > 0 && (
                <p className="location-map-muted">{selectedNode.encounterCount} encounter template at this location.</p>
              )}
            </section>
            <section>
              <h4>Exits</h4>
              <RouteList routes={selectedNode?.routes || []} />
            </section>
          </div>

          {selectedNode?.encounters?.length > 0 && (
            <div className="location-encounter-list" aria-label="Selected encounter templates">
              {disabled && onSelectEncounter && (
                <div role="status" className="multiplayer-sync-guard" style={{ margin: '0 0 10px' }}>
                  <strong>同步暂停</strong>
                  <span>{blockReason}</span>
                </div>
              )}
              {selectedNode.encounters.map(encounter => (
                <EncounterCard
                  key={encounter.id || encounter.name}
                  encounter={encounter}
                  selecting={String(selectingTemplateId) === String(encounter.id)}
                  disabled={disabled}
                  disabledReason={blockReason}
                  onSelectEncounter={onSelectEncounter}
                />
              ))}
            </div>
          )}

          {map.nodes.some(node => node.encounterCount > 0) && (
            <div className="location-map-encounters" aria-label="Mapped encounters">
              {map.nodes.filter(node => node.encounterCount > 0).map(node => (
                <span key={node.id}>
                  <b>{node.name}</b>
                  {node.encounterNames.length > 0 ? node.encounterNames.join(' / ') : `${node.encounterCount} encounter`}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </Overlay>
  )
}
