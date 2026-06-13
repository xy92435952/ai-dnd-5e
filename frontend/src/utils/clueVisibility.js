const HIDDEN_STATUS_VALUES = new Set([
  'hidden',
  'secret',
  'private',
  'dm_only',
  'dm-only',
  'dmonly',
  'unrevealed',
  'undiscovered',
  'unknown',
  'locked',
  'future',
])

const PRIVATE_SCOPE_VALUES = new Set([
  'dm',
  'dm_only',
  'dm-only',
  'dmonly',
  'private',
  'group',
  'party',
  'limited',
])

function cleanText(value) {
  return String(value || '').trim()
}

function normalizeStatus(value) {
  return cleanText(value).toLowerCase().replace(/\s+/g, '_')
}

function normalizeIdentity(value) {
  return cleanText(value)
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function clueIdentityValues(clue) {
  if (!clue || typeof clue !== 'object' || Array.isArray(clue)) return []
  return [
    clue.id,
    clue.key,
    clue.clue_id,
    clue.clueId,
    clue.text,
    clue.label,
    clue.name,
  ].map(normalizeIdentity).filter(Boolean)
}

function clueUpdateIdentityValues(update) {
  if (!update || typeof update !== 'object' || Array.isArray(update)) return []
  return [
    update.clue_id,
    update.clueId,
    update.clue,
    update.id,
    update.key,
    update.text,
    update.label,
    update.name,
  ].map(normalizeIdentity).filter(Boolean)
}

function isClueUpdate(update) {
  return normalizeStatus(update?.type) === 'clue'
}

function isTrueMarker(value) {
  if (value === true) return true
  const normalized = normalizeStatus(value)
  return normalized === 'true' || normalized === '1' || normalized === 'yes' || normalized === 'y'
}

function isFalseMarker(value) {
  if (value === false) return true
  const normalized = normalizeStatus(value)
  return normalized === 'false' || normalized === '0' || normalized === 'no' || normalized === 'n'
}

function isHiddenStatus(value) {
  return HIDDEN_STATUS_VALUES.has(normalizeStatus(value))
}

function hasExplicitPublicVisibility(value) {
  return [
    value?.public,
    value?.visible,
    value?.revealed,
    value?.discovered,
    value?.player_visible,
    value?.playerVisible,
  ].some(isTrueMarker)
}

function isHiddenVisibilityObject(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false

  if ([
    value.hidden,
    value.secret,
    value.private,
    value.dm_only,
    value.dmOnly,
  ].some(isTrueMarker)) return true

  if ([
    value.public,
    value.visible,
    value.revealed,
    value.discovered,
    value.player_visible,
    value.playerVisible,
  ].some(isFalseMarker)) return true

  if ([
    value.status,
    value.state,
    value.scope,
    value.audience,
    value.access,
  ].some(isHiddenStatus)) return true

  const scope = normalizeStatus(value.scope || value.audience || value.access)
  if (PRIVATE_SCOPE_VALUES.has(scope) && !hasExplicitPublicVisibility(value)) return true

  return false
}

export function isPublicClue(clue) {
  if (!clue || typeof clue !== 'object' || Array.isArray(clue)) return false
  if (!cleanText(clue.text)) return false

  if ([
    clue.hidden,
    clue.secret,
    clue.private,
    clue.dm_only,
    clue.dmOnly,
  ].some(isTrueMarker)) return false

  if ([
    clue.visible,
    clue.revealed,
    clue.discovered,
    clue.public,
    clue.player_visible,
    clue.playerVisible,
  ].some(isFalseMarker)) return false

  if ([clue.status, clue.state].some(isHiddenStatus)) return false

  if (typeof clue.visibility === 'string' && isHiddenStatus(clue.visibility)) return false
  if (isHiddenVisibilityObject(clue.visibility)) return false

  return true
}

export function filterPublicClues(clues) {
  return Array.isArray(clues) ? clues.filter(isPublicClue) : []
}

export function isPublicRecentUpdate(update, clues = []) {
  if (!update || typeof update !== 'object' || Array.isArray(update)) return false
  if (!isClueUpdate(update)) return true

  const displayText = cleanText(
    update.text
    || update.label
    || update.name
    || update.detail
    || update.clue_id
    || update.clueId
    || update.id
    || update.key,
  )
  if (!isPublicClue({ ...update, text: displayText })) return false

  const allClues = Array.isArray(clues) ? clues : []
  if (allClues.length === 0) return true

  const publicIdentitySet = new Set(
    filterPublicClues(allClues).flatMap(clueIdentityValues),
  )
  const updateIdentities = clueUpdateIdentityValues(update)
  if (updateIdentities.length === 0) return true

  return updateIdentities.some(value => publicIdentitySet.has(value))
}

export function filterPublicRecentUpdates(updates, clues = []) {
  return Array.isArray(updates)
    ? updates.filter(update => isPublicRecentUpdate(update, clues))
    : []
}
