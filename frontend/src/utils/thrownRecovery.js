const THROWN_RECOVERY_POOL_KEY = 'thrown_weapon_recovery_pool'

export function getRecoverableThrownWeapons(session, characterId) {
  const items = session?.game_state?.[THROWN_RECOVERY_POOL_KEY]?.items
  if (!Array.isArray(items) || !characterId) return []
  return items.filter(item => (
    item
    && item.status === 'available'
    && String(item.character_id) === String(characterId)
  ))
}

export function formatThrownRecoverySummary(items = []) {
  if (!Array.isArray(items) || items.length === 0) return ''
  return items
    .map(item => {
      const name = item?.weapon || item?.item?.name || 'Thrown weapon'
      const quantity = positiveQuantity(item?.quantity ?? item?.item?.quantity)
      return `${name} x${quantity}`
    })
    .join(', ')
}

export function mergeThrownRecoveryResultIntoSession(session, result) {
  if (!session || !result) return session
  const characterId = result.character_id
  const equipment = result.equipment
  const gameState = {
    ...(session.game_state || {}),
    ...(result.recovery_pool ? { [THROWN_RECOVERY_POOL_KEY]: result.recovery_pool } : {}),
  }
  return {
    ...session,
    game_state: gameState,
    player: mergeCharacterEquipment(session.player, characterId, equipment),
    characters: mergeCharacterList(session.characters, characterId, equipment),
    companions: mergeCharacterList(session.companions, characterId, equipment),
    party: mergeCharacterList(session.party, characterId, equipment),
  }
}

function mergeCharacterList(list, characterId, equipment) {
  if (!Array.isArray(list)) return list
  return list.map(character => mergeCharacterEquipment(character, characterId, equipment))
}

function mergeCharacterEquipment(character, characterId, equipment) {
  if (!character || !characterId || !equipment) return character
  if (String(character.id) !== String(characterId)) return character
  return {
    ...character,
    equipment,
  }
}

function positiveQuantity(value) {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? number : 1
}
