export function getLocationGraphSummary(graph) {
  const rawNodes = Array.isArray(graph?.nodes) ? graph.nodes : []
  if (!rawNodes.length) return null

  const currentId = graph.current_location_id || rawNodes.find(node => node.visited)?.id || rawNodes[0].id
  const nodes = getVisibleNodes(rawNodes, currentId)
  if (!nodes.length) return null

  const current = nodes.find(node => String(node.id) === String(currentId)) || nodes[0]
  const visited = nodes.filter(node => node.visited)
  const edges = getVisibleEdges(graph, nodes)
  const templates = getVisibleEncounterTemplates(graph, current.id)
  const currentTemplateIds = new Set(
    Array.isArray(current.encounter_template_ids)
      ? current.encounter_template_ids.map(id => String(id))
      : [],
  )
  const linkedIds = new Set()

  edges.forEach(edge => {
    if (String(edge.from) === String(current.id)) linkedIds.add(String(edge.to))
    if (String(edge.to) === String(current.id)) linkedIds.add(String(edge.from))
  })

  const linkedNames = nodes
    .filter(node => linkedIds.has(String(node.id)))
    .map(node => node.name)
    .filter(Boolean)
  const encounterTemplates = templates.filter(template => {
    const idMatches = currentTemplateIds.has(String(template.id))
    const locationMatches = String(template.location_id) === String(current.id)
    return idMatches || locationMatches
  })
  const nextEncounter = encounterTemplates.find(template => template.status === 'available') || encounterTemplates[0] || null

  return {
    currentName: current.name || '当前位置',
    currentDescription: current.description || '',
    visitedCount: visited.length || 1,
    totalCount: nodes.length,
    linkedNames,
    encounterCount: encounterTemplates.length,
    nextEncounterName: nextEncounter?.name || '',
    nextEncounterDifficulty: nextEncounter?.difficulty_hint || '',
    nextEncounterEnemies: Array.isArray(nextEncounter?.enemy_names) ? nextEncounter.enemy_names : [],
  }
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function cleanId(value, fallback) {
  const text = String(value ?? '').trim()
  return text || fallback
}

function getCurrentLocationId(graph, nodes) {
  return cleanId(
    graph?.current_location_id || nodes.find(node => node?.visited)?.id || nodes[0]?.id,
    nodes[0]?.id || 'location_0',
  )
}

function isVisibleNode(node, currentId) {
  return Boolean(
    node?.visited
    || node?.discovered
    || node?.revealed
    || node?.public
    || String(node?.id) === String(currentId),
  )
}

function getVisibleNodes(nodes, currentId) {
  const visible = nodes.filter(node => isVisibleNode(node, currentId))
  if (visible.length > 0) return visible
  const current = nodes.find(node => String(node?.id) === String(currentId)) || nodes[0]
  return current ? [{ ...current, visited: true }] : []
}

function isPublicEncounter(template) {
  const status = String(template?.status || 'hidden')
  if (status === 'claimed' || status === 'resolved' || status === 'triggered') return true
  if (status !== 'available') return false
  return Boolean(template?.discovered || template?.revealed || template?.public)
}

function getVisibleEncounterTemplates(graph, currentId) {
  const currentNode = asArray(graph?.nodes).find(node => String(node?.id) === String(currentId))
  const currentTemplateIds = new Set(
    Array.isArray(currentNode?.encounter_template_ids)
      ? currentNode.encounter_template_ids.map(id => String(id))
      : [],
  )

  return asArray(graph?.encounter_templates)
    .filter(template => template && template.status !== 'resolved' && isPublicEncounter(template))
    .filter(template => {
      const locationId = cleanId(template?.location_id, '')
      const templateId = String(template?.id || '')
      return String(locationId) === String(currentId) || currentTemplateIds.has(templateId)
    })
}

function edgeLabel(edge) {
  if (edge?.label) return String(edge.label)
  if (edge?.name) return String(edge.name)
  const type = String(edge?.type || 'route').replace(/[_-]+/g, ' ')
  return type || 'route'
}

function isEdgeLocked(edge) {
  return Boolean(edge?.locked || edge?.requires_key || edge?.status === 'locked' || edge?.type === 'locked')
}

function isEdgeHidden(edge) {
  return Boolean(edge?.hidden || edge?.secret || edge?.status === 'hidden' || edge?.type === 'hidden')
}

function getVisibleEdges(graph, nodes) {
  const nodeIds = new Set(nodes.map(node => String(node.id)))
  return asArray(graph?.edges)
    .map((edge, index) => ({
      id: cleanId(edge?.id, `edge_${index}`),
      from: cleanId(edge?.from, ''),
      to: cleanId(edge?.to, ''),
      type: String(edge?.type || 'route'),
      label: edgeLabel(edge),
      locked: isEdgeLocked(edge),
      hidden: isEdgeHidden(edge),
      oneWay: Boolean(edge?.one_way || edge?.oneWay),
      requiresKey: edge?.requires_key ? String(edge.requires_key) : '',
      dc: edge?.dc ?? null,
      checkType: edge?.check_type ? String(edge.check_type) : '',
    }))
    .filter(edge => nodeIds.has(String(edge.from)) && nodeIds.has(String(edge.to)) && !edge.hidden)
}

function getNodeRoutes(nodeId, nodes, edges) {
  const nodeById = new Map(nodes.map(node => [String(node.id), node]))
  return edges
    .map(edge => {
      let destinationId = ''
      let oneWayOut = false
      if (String(edge.from) === String(nodeId)) {
        destinationId = String(edge.to)
        oneWayOut = Boolean(edge.oneWay)
      } else if (String(edge.to) === String(nodeId) && !edge.oneWay) {
        destinationId = String(edge.from)
      }
      if (!destinationId) return null
      const destination = nodeById.get(destinationId)
      if (!destination) return null
      return {
        id: edge.id,
        destinationId,
        destinationName: destination.name,
        destinationVisited: Boolean(destination.visited),
        label: edge.label,
        type: edge.type,
        locked: Boolean(edge.locked),
        oneWay: oneWayOut,
        requiresKey: edge.requiresKey,
        dc: edge.dc,
        checkType: edge.checkType,
      }
    })
    .filter(Boolean)
}

function mapNodePosition(index, total) {
  const columns = Math.min(4, Math.max(1, Math.ceil(Math.sqrt(total))))
  const rows = Math.max(1, Math.ceil(total / columns))
  const row = Math.floor(index / columns)
  const col = index % columns
  const displayCol = row % 2 === 1 ? columns - 1 - col : col
  const x = columns === 1 ? 50 : 12 + displayCol * (76 / (columns - 1))
  const y = rows === 1 ? 50 : 16 + row * (68 / (rows - 1))
  return { x, y }
}

function encounterView(template, selectedTemplateId = '') {
  const environmentPressure = template?.environment_pressure || template?.party_balance?.environment_pressure || {}
  return {
    id: String(template?.id || template?.name || ''),
    name: String(template?.name || 'Encounter'),
    status: String(template?.status || 'available'),
    selected: Boolean(template?.selected || (selectedTemplateId && String(template?.id) === String(selectedTemplateId))),
    difficulty: String(template?.difficulty_hint || ''),
    xpBudget: template?.xp_budget ?? null,
    enemyNames: asArray(template?.enemy_names).map(String),
    enemyRoles: asArray(template?.enemy_roles).map(role => ({
      name: String(role?.name || ''),
      role: String(role?.role || ''),
    })).filter(role => role.name || role.role),
    terrain: asArray(template?.terrain).map(String),
    cover: asArray(template?.cover).map(String),
    objectives: asArray(template?.objectives).map(String),
    hazards: asArray(template?.hazards).map(String),
    rewardHints: asArray(template?.reward_hints).map(String),
    tactics: String(template?.tactics || ''),
    environmentPressure: String(environmentPressure?.pressure || ''),
    environmentPressureTags: environmentPressureTags(environmentPressure),
  }
}

function environmentPressureTags(pressure = {}) {
  const level = String(pressure?.pressure || '')
  if (!level || level === 'none') return []
  const tags = [`Env ${level}`]
  if (pressure.hazards) tags.push(`hazards ${pressure.hazards}`)
  if (pressure.objectives) tags.push(`objectives ${pressure.objectives}`)
  if (pressure.cover || pressure.terrain) {
    tags.push(`terrain ${Number(pressure.cover || 0) + Number(pressure.terrain || 0)}`)
  }
  if (pressure.authored_cells) tags.push(`cells ${pressure.authored_cells}`)
  return tags
}

export function getLocationGraphMap(graph) {
  const rawNodes = Array.isArray(graph?.nodes) ? graph.nodes : []
  if (!rawNodes.length) return null

  const currentId = getCurrentLocationId(graph, rawNodes)
  const nodesSource = getVisibleNodes(rawNodes, currentId)
  const selectedTemplateId = String(graph?.selected_encounter_template_id || '')
  const templates = getVisibleEncounterTemplates(graph, currentId)
  const templateIdsByNode = new Map()
  templates.forEach(template => {
    const locationId = cleanId(template?.location_id, '')
    if (!locationId) return
    const bucket = templateIdsByNode.get(locationId) || []
    bucket.push(template)
    templateIdsByNode.set(locationId, bucket)
  })

  const nodes = nodesSource.map((node, index) => {
    const id = cleanId(node?.id, `location_${index}`)
    const directTemplates = templateIdsByNode.get(id) || []
    const nodeTemplateIds = asArray(node?.encounter_template_ids).map(String)
    const referencedTemplates = templates.filter(template => nodeTemplateIds.includes(String(template?.id)))
    const linkedTemplates = [
      ...new Map(
        [...directTemplates, ...referencedTemplates]
          .map((template, templateIndex) => [String(template?.id || template?.name || templateIndex), template]),
      ).values(),
    ]
    const position = mapNodePosition(index, nodesSource.length)
    return {
      id,
      name: String(node?.name || `Location ${index + 1}`),
      description: String(node?.description || ''),
      visited: Boolean(node?.visited),
      current: String(id) === String(currentId),
      source: String(node?.source || ''),
      encounterCount: linkedTemplates.length,
      encounters: linkedTemplates.map(template => encounterView(template, selectedTemplateId)),
      encounterNames: [...new Set(linkedTemplates.map(template => template?.name).filter(Boolean).map(String))],
      x: position.x,
      y: position.y,
    }
  })

  const edges = getVisibleEdges(graph, nodes)
  const nodesWithRoutes = nodes.map(node => ({
    ...node,
    routes: getNodeRoutes(node.id, nodes, edges),
  }))

  const currentNode = nodesWithRoutes.find(node => node.current) || nodesWithRoutes[0]
  return {
    currentId,
    currentNode,
    nodes: nodesWithRoutes,
    edges,
    visitedCount: nodesWithRoutes.filter(node => node.visited).length || 1,
    totalCount: nodesWithRoutes.length,
    encounterCount: templates.length,
  }
}
