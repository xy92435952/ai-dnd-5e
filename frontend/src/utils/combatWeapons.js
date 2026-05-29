function getWeaponProperties(weapon = {}) {
  const properties = weapon.properties || []
  if (typeof properties === 'string') return [properties.toLowerCase()]
  return properties.map(prop => String(prop).toLowerCase())
}

export function isAmmunitionWeapon(weapon = {}) {
  return getWeaponProperties(weapon).includes('ammunition')
}

export function isThrownWeapon(weapon = {}) {
  return getWeaponProperties(weapon).some(prop => prop.startsWith('thrown'))
}

export function isPureRangedWeapon(weapon = {}) {
  const type = String(weapon.type || '').toLowerCase()
  return (
    isAmmunitionWeapon(weapon)
    || type === 'simple_ranged'
    || type === 'martial_ranged'
    || type.includes('ranged')
  ) && !isThrownWeapon(weapon)
}

function isWeaponAvailable(weapon = {}) {
  if (isAmmunitionWeapon(weapon) && weapon.ammo != null) return Number(weapon.ammo) > 0
  if (isThrownWeapon(weapon)) return Number(weapon.quantity ?? 1) > 0
  return true
}

export function getAttackWeaponOptions(character, isRanged) {
  const weapons = character?.equipment?.weapons || []
  if (!Array.isArray(weapons)) return []

  const candidates = weapons.filter(weapon => {
    if (!weapon?.name) return false
    if (isRanged) {
      return (isPureRangedWeapon(weapon) || isThrownWeapon(weapon)) && isWeaponAvailable(weapon)
    }
    return !isPureRangedWeapon(weapon)
  })

  const byName = new Map()
  for (const weapon of candidates) {
    const existing = byName.get(weapon.name)
    const count = (existing?.count || 0) + Number(weapon.quantity ?? 1)
    byName.set(weapon.name, {
      name: weapon.name,
      label: weapon.zh || weapon.name,
      ammo: weapon.ammo,
      count,
    })
  }
  return Array.from(byName.values())
}
