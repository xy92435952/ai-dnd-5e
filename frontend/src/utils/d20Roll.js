function asD20(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return null
  const rounded = Math.round(number)
  if (rounded < 1 || rounded > 20) return null
  return rounded
}

function fallbackD20() {
  return Math.floor(Math.random() * 20) + 1
}

export function selectD20Roll(rollResult = {}, mode = 'normal') {
  const needsPair = mode === 'advantage' || mode === 'disadvantage'
  const rawRolls = Array.isArray(rollResult.rolls) ? rollResult.rolls : []
  const rolls = rawRolls.map(asD20).filter(value => value !== null)
  const total = asD20(rollResult.total)

  if (!rolls.length && total !== null) rolls.push(total)
  if (!rolls.length) rolls.push(fallbackD20())
  if (needsPair) {
    while (rolls.length < 2) rolls.push(fallbackD20())
  }

  const first = rolls[0]
  const second = needsPair ? rolls[1] : null
  const selected = mode === 'advantage'
    ? Math.max(first, second)
    : mode === 'disadvantage'
      ? Math.min(first, second)
      : first

  return {
    d20: first,
    secondD20: second,
    selected,
    rolls: needsPair ? [first, second] : [first],
  }
}
