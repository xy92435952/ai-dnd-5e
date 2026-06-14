export function getBardicInspiration(characterOrResources = null) {
  const resources = characterOrResources?.class_resources
    || characterOrResources?.classResources
    || characterOrResources
    || {}
  const inspiration = resources.bardic_inspiration || resources.bardicInspiration || null
  if (!inspiration || typeof inspiration !== 'object') return null
  const uses = Number(inspiration.uses_remaining ?? inspiration.usesRemaining ?? 0)
  if (!Number.isFinite(uses) || uses <= 0) return null
  const die = String(inspiration.die || 'd6').toLowerCase()
  const faces = Number(die.replace(/^d/i, ''))
  return {
    ...inspiration,
    die,
    faces: Number.isFinite(faces) && faces > 0 ? faces : 6,
    uses_remaining: uses,
  }
}

export function hasBardicInspiration(characterOrResources = null) {
  return Boolean(getBardicInspiration(characterOrResources))
}

export function updateBardicInspirationUses(character = null, usesRemaining = 0) {
  if (!character) return character
  const current = character.class_resources?.bardic_inspiration || {}
  return {
    ...character,
    class_resources: {
      ...(character.class_resources || {}),
      bardic_inspiration: {
        ...current,
        uses_remaining: Math.max(0, Number(usesRemaining) || 0),
      },
    },
  }
}
