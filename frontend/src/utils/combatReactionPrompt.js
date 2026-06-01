export function isReactionPromptForCharacter(prompt, characterId) {
  if (!prompt) return false
  const reactorId = prompt.reactor_character_id
  if (!reactorId || !characterId) return true
  return String(reactorId) === String(characterId)
}

export function normalizeReactionOptions(prompt = {}) {
  const reactions = prompt.available_reactions || []
  const reactionsByType = new Map()
  reactions.forEach(reaction => {
    if (reaction.id) reactionsByType.set(reaction.id, reaction)
    if (reaction.type) reactionsByType.set(reaction.type, reaction)
  })
  const rawOptions = prompt.options || reactions.map(reaction => ({
    type: reaction.id || reaction.type,
    target_id: prompt.target_id || prompt.attacker_id,
    character_id: prompt.reactor_character_id,
    label: `${reaction.name || reaction.id}${reaction.effect ? ` - ${reaction.effect}` : ''}`,
    cost: reaction.cost,
    damage_prevented: reaction.damage_prevented,
  }))

  return rawOptions.map(option => {
    const reaction = reactionsByType.get(option.type) || {}
    const enriched = {
      ...option,
      cost: option.cost ?? reaction.cost,
      damage_prevented: option.damage_prevented ?? reaction.damage_prevented,
      target_id: option.target_id || prompt.target_id || prompt.attacker_id,
      character_id: option.character_id || prompt.reactor_character_id,
    }
    return {
      ...enriched,
      ...withHpPreview(prompt, enriched),
    }
  })
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function withHpPreview(prompt, option) {
  const outcome = getReactionOptionOutcome(prompt, option)
  return outcome ? { hp_preview: outcome.hp_preview, hp_outcome: outcome } : {}
}

export function getReactionOptionHpPreview(prompt = {}, option = {}) {
  return getReactionOptionOutcome(prompt, option)?.hp_preview || null
}

export function getReactionOptionOutcome(prompt = {}, option = {}) {
  const prevented = toNumber(option.damage_prevented)
  if (!prevented || prevented <= 0) return null

  const hpBefore = toNumber(prompt.target_hp_before_damage ?? prompt.hp_before)
  const incoming = toNumber(prompt.incoming_damage)
  if (hpBefore === null || incoming === null) {
    return {
      prevented,
      prevented_label: `减免 ${prevented} 伤害`,
      hp_preview: `预计减免 ${prevented} 伤害`,
    }
  }

  const hp_without_reaction = Math.max(0, hpBefore - incoming)
  const hp_after_reaction = Math.min(hpBefore, hp_without_reaction + prevented)
  if (hp_after_reaction <= hp_without_reaction) return null

  return {
    prevented,
    prevented_label: `减免 ${prevented} 伤害`,
    hp_before: hpBefore,
    incoming_damage: incoming,
    hp_without_reaction,
    hp_after_reaction,
    no_reaction_label: `不反应 HP ${hpBefore} -> ${hp_without_reaction}`,
    reaction_label: `使用后 HP ${hpBefore} -> ${hp_after_reaction}`,
    risk_label: hp_without_reaction <= 0 && hp_after_reaction > 0
      ? '可避免倒地'
      : hp_after_reaction <= 0
        ? '仍可能倒地'
        : '',
    hp_preview: `不反应 HP ${hpBefore} -> ${hp_without_reaction}；使用后 HP ${hpBefore} -> ${hp_after_reaction}`,
  }
}

export function getReactionPromptContext(prompt = {}) {
  if (prompt.context) return prompt.context
  if (prompt.trigger === 'spell_cast' && prompt.spell_name) {
    return `${prompt.attacker_name || prompt.caster_name || '敌人'} 正在施放 ${prompt.spell_name}`
  }
  if (prompt.incoming_damage !== undefined) {
    return `${prompt.attacker_name || '敌人'} 的攻击造成 ${prompt.incoming_damage} 点待处理伤害`
  }
  return '选择反应'
}

export function getReactionPromptMeta(prompt = {}) {
  const items = []
  if (prompt.attack_roll !== undefined && prompt.player_ac !== undefined) {
    items.push(`攻击 ${prompt.attack_roll} vs AC${prompt.player_ac}`)
  }
  if (prompt.incoming_damage !== undefined) {
    items.push(`伤害 ${prompt.incoming_damage}`)
  }
  const hpBefore = toNumber(prompt.target_hp_before_damage ?? prompt.hp_before)
  const incoming = toNumber(prompt.incoming_damage)
  if (hpBefore !== null && incoming !== null) {
    items.push(`HP ${hpBefore} -> ${Math.max(0, hpBefore - incoming)}`)
  }
  if (prompt.spell_level !== undefined && prompt.spell_name) {
    items.push(`${prompt.spell_name} ${prompt.spell_level}环`)
  }
  return items
}
