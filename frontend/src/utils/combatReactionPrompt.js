export function isReactionPromptForCharacter(prompt, characterId) {
  if (!prompt) return false
  const reactorId = prompt.reactor_character_id
  if (!reactorId || !characterId) return true
  return String(reactorId) === String(characterId)
}

export function normalizeReactionOptions(prompt = {}) {
  const rawOptions = prompt.options || (prompt.available_reactions || []).map(reaction => ({
    type: reaction.id || reaction.type,
    target_id: prompt.target_id || prompt.attacker_id,
    character_id: prompt.reactor_character_id,
    label: `${reaction.name || reaction.id}${reaction.effect ? ` - ${reaction.effect}` : ''}`,
    cost: reaction.cost,
    damage_prevented: reaction.damage_prevented,
  }))

  return rawOptions.map(option => ({
    ...option,
    target_id: option.target_id || prompt.target_id || prompt.attacker_id,
    character_id: option.character_id || prompt.reactor_character_id,
  }))
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
  if (prompt.spell_level !== undefined && prompt.spell_name) {
    items.push(`${prompt.spell_name} ${prompt.spell_level}环`)
  }
  return items
}
