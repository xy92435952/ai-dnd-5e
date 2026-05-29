const COMBAT_ENDED_PATTERNS = [
  /当前没有进行中的战斗/,
  /没有进行中的战斗/,
  /not.*in combat/i,
  /combat.*not.*active/i,
  /combat state.*not.*exist/i,
  /战斗状态不存在/,
]

export function combatEndedMessage(error) {
  if (typeof error === 'string') return error
  return error?.message || error?.detail || String(error || '')
}

export function isCombatEndedError(error) {
  const message = combatEndedMessage(error)
  return COMBAT_ENDED_PATTERNS.some(pattern => pattern.test(message))
}
