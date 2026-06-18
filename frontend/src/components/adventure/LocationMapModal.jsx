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
  const push = (label, tone = '') => badges.push({ label, tone })
  if (route.locked) push('locked', 'warn')
  if (route.oneWay) push('one-way')
  if (route.requiresKey) push(`key: ${route.requiresKey}`, 'warn')
  if (route.dc != null) push(`${route.checkType || 'check'} DC ${route.dc}`, 'warn')
  if (route.destinationActiveEncounter) push('active encounter', 'danger')
  else if (route.destinationEncounterCount > 0) push(`encounter ${route.destinationEncounterCount}`, 'danger')
  if (!badges.length && route.label) push(route.label)
  return badges
}

function RouteSummary({ routes }) {
  if (!routes?.length) return null
  const gated = routes.filter(route => route.locked || route.tone === 'gated').length
  const oneWay = routes.filter(route => route.oneWay).length
  const unvisited = routes.filter(route => !route.destinationVisited).length
  const encounters = routes.filter(route => route.destinationEncounterCount > 0).length
  return (
    <div className="location-map-route-summary" aria-label="Exit summary">
      <span><b>{routes.length}</b> exits</span>
      {gated > 0 && <span className="warn"><b>{gated}</b> gated</span>}
      {oneWay > 0 && <span><b>{oneWay}</b> one-way</span>}
      {unvisited > 0 && <span><b>{unvisited}</b> new</span>}
      {encounters > 0 && <span className="danger"><b>{encounters}</b> encounter route</span>}
    </div>
  )
}

function countLabel(count, singular) {
  return `${count} ${count === 1 ? singular : `${singular}s`}`
}

function SelectedLocationStatus({ node }) {
  if (!node) return null
  const routes = Array.isArray(node.routes) ? node.routes : []
  const encounterCount = Number(node.encounterCount || 0)
  const planTone = node.travelPlan?.tone || (node.current ? 'current' : 'muted')
  const planLabel = node.travelPlan?.label || (node.current ? 'Current location' : 'Route unknown')
  const items = [
    { label: 'Focus', value: node.current ? 'Current' : 'Selected', tone: node.current ? 'current' : '' },
    { label: 'Route', value: planLabel, tone: planTone },
    { label: 'Exits', value: countLabel(routes.length, 'exit') },
    {
      label: 'Templates',
      value: encounterCount > 0 ? countLabel(encounterCount, 'encounter template') : 'No encounter templates',
      tone: encounterCount > 0 ? 'danger' : 'muted',
    },
  ]

  return (
    <div
      className="location-map-selected-status"
      role="status"
      aria-live="polite"
      aria-label={`Selected location status for ${node.name || 'location'}`}
    >
      {items.map(item => (
        <span key={item.label} className={item.tone || ''}>
          <b>{item.label}</b>
          {item.value}
        </span>
      ))}
    </div>
  )
}

function RouteList({ routes, locationName = 'selected location' }) {
  if (!routes?.length) return <p className="location-map-muted">No exits recorded.</p>
  return (
    <>
      <RouteSummary routes={routes} />
      <ul className="location-map-route-list" aria-label={`Routes from ${locationName}`}>
        {routes.map(route => (
          <li key={`${route.id}-${route.destinationId}`} className={route.locked ? 'locked' : (route.tone || '')}>
            <div className="location-map-route-main">
              <span>{route.destinationName}</span>
              {route.guidance && <em>{route.guidance}</em>}
              {route.destinationEncounterNames.length > 0 && <em>{route.destinationEncounterNames.join(' / ')}</em>}
              {route.actionHint && <small>{route.actionHint}</small>}
            </div>
            <div className="location-map-route-meta">
              {routeBadges(route).map(badge => <b key={badge.label} className={badge.tone || ''}>{badge.label}</b>)}
            </div>
          </li>
        ))}
      </ul>
    </>
  )
}

function TravelPlanSummary({ plan }) {
  if (!plan) return null
  const path = Array.isArray(plan.path) ? plan.path.filter(Boolean) : []
  return (
    <div className={`location-map-travel-plan ${plan.tone || ''}`} aria-label="Route from current">
      <div className="location-map-travel-head">
        <span>{plan.label}</span>
        {plan.steps != null && <b>{plan.steps} step{plan.steps === 1 ? '' : 's'}</b>}
      </div>
      <p>{plan.detail}</p>
      {path.length > 1 && <em>{path.join(' -> ')}</em>}
      {plan.nextAction && <small>{plan.nextAction}</small>}
      {plan.encounterCue && <small className="encounter-cue">{plan.encounterCue}</small>}
    </div>
  )
}

function encounterHandoff(encounter, nodeCurrent, disabled, disabledReason) {
  if (disabled) return disabledReason || 'Encounter selection is paused.'
  if (encounter.selected) {
    return nodeCurrent ? 'Already armed for this location.' : 'Already armed away from the current location.'
  }
  if (encounter.status !== 'available') return 'This encounter cannot be armed right now.'
  return nodeCurrent ? 'Can arm this encounter for the next combat.' : 'Travel here before arming.'
}

function EncounterCard({
  encounter,
  selecting,
  nodeCurrent = false,
  disabled = false,
  disabledReason = '',
  onSelectEncounter,
}) {
  const canSelect = encounter.status === 'available' && !encounter.selected && onSelectEncounter && !disabled && nodeCurrent
  const locationSelectReason = 'Travel to this location before setting this encounter active.'
  const selectTitle = disabled ? disabledReason : !nodeCurrent ? locationSelectReason : undefined
  const handoff = encounterHandoff(encounter, nodeCurrent, disabled, disabledReason)
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
      {encounter.intel?.length > 0 && (
        <div className="location-encounter-intel" aria-label="Encounter readiness">
          {encounter.intel.map(item => (
            <span key={item.key} className={item.tone || ''}>
              <b>{item.label}</b>
              <em>{item.detail}</em>
            </span>
          ))}
        </div>
      )}
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
      <p className="location-map-muted location-encounter-handoff">{handoff}</p>
      {encounter.tactics && <p className="location-map-muted">{encounter.tactics}</p>}
      {onSelectEncounter && (
        <div className="location-encounter-action" role="group" aria-label={`Encounter action for ${encounter.name}`}>
          <button
            type="button"
            className="btn-fantasy location-encounter-select"
            disabled={!canSelect || selecting}
            title={selectTitle}
            onClick={() => onSelectEncounter(encounter.id)}
          >
            {selecting ? 'Setting...' : encounter.selected ? 'Active' : !nodeCurrent ? 'Travel first' : 'Set active'}
          </button>
        </div>
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
            {map.activeEncounter && (
              <span className="active-encounter" title={map.activeEncounter.locationName}>
                <b>Active</b> {map.activeEncounter.name}
              </span>
            )}
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
              <SelectedLocationStatus node={selectedNode} />
              <TravelPlanSummary plan={selectedNode?.travelPlan} />
              {selectedNode?.encounterCount > 0 && (
                <p className="location-map-muted">{selectedNode.encounterCount} encounter template at this location.</p>
              )}
            </section>
            <section>
              <h4>Exits</h4>
              <RouteList routes={selectedNode?.routes || []} locationName={selectedNode?.name} />
            </section>
          </div>

          {selectedNode?.encounters?.length > 0 && (
            <div className="location-encounter-list" aria-label="Selected encounter templates" aria-live="polite">
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
                  nodeCurrent={Boolean(selectedNode?.current)}
                  disabled={disabled}
                  disabledReason={blockReason}
                  onSelectEncounter={onSelectEncounter}
                />
              ))}
            </div>
          )}

          {map.nodes.some(node => node.encounterCount > 0) && (
            <div className="location-map-encounters" role="group" aria-label="Mapped encounters">
              {map.nodes.filter(node => node.encounterCount > 0).map(node => (
                <button
                  key={node.id}
                  type="button"
                  className={String(selectedNode?.id) === String(node.id) ? 'selected' : ''}
                  aria-label={`Focus ${node.name} encounters`}
                  aria-pressed={String(selectedNode?.id) === String(node.id)}
                  title={node.encounterNames.join(' / ') || `${node.encounterCount} encounter`}
                  onClick={() => setSelectedId(node.id)}
                >
                  <b>{node.name}</b>
                  {node.encounterNames.length > 0 ? node.encounterNames.join(' / ') : `${node.encounterCount} encounter`}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </Overlay>
  )
}
