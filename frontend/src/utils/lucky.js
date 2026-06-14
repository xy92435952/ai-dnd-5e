export function getLuckyPointsRemaining(characterOrResources = null) {
  const resources = characterOrResources?.class_resources
    || characterOrResources?.classResources
    || characterOrResources
    || {}
  const value = Number(resources.lucky_points_remaining ?? resources.luckyPointsRemaining ?? 0)
  return Number.isFinite(value) ? Math.max(0, value) : 0
}

export function updateLuckyPointsRemaining(character = null, remaining = 0) {
  if (!character) return character
  const nextRemaining = Math.max(0, Number(remaining) || 0)
  return {
    ...character,
    class_resources: {
      ...(character.class_resources || {}),
      lucky_points_remaining: nextRemaining,
    },
  }
}
