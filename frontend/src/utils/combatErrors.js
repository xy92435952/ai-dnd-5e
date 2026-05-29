const RULES = [
  {
    test: /token is stale|stale.*token|refresh combat state/i,
    message: '战斗状态已经更新，请稍等刷新后再操作。',
  },
  {
    test: /not your turn|不是你的回合|当前不是你|不能结束.*回合|cannot.*turn/i,
    message: '现在还不是你的回合，请等待当前行动者完成行动。',
  },
  {
    test: /out of range|range|距离|射程|够不着|不在.*范围/i,
    message: '目标不在可达范围内，请靠近、换目标，或选择远程/法术行动。',
  },
  {
    test: /bonus.*used|附赠动作已用|bonus action/i,
    message: '本回合的附赠动作已经用过了。',
  },
  {
    test: /reaction.*used|反应已用|reaction/i,
    message: '本轮反应已经用过了，等到你的下个回合开始后会恢复。',
  },
  {
    test: /movement.*used|movement.*remaining|移动力|speed|no movement/i,
    message: '本回合移动力不足，请选择更近的位置或结束回合。',
  },
  {
    test: /action.*used|行动已用|动作已用|本回合行动已用尽|no action/i,
    message: '本回合的动作已经用过了，请选择附赠动作、移动或结束回合。',
  },
  {
    test: /spell slot|no slot|slot.*not enough|法术位|没有.*法术位/i,
    message: '可用法术位不足，请改用戏法、低环法术或其他行动。',
  },
  {
    test: /target.*dead|dead target|目标.*死亡|目标.*倒下|target.*0 hp/i,
    message: '这个目标已经倒下，不能再作为该行动的目标。',
  },
  {
    test: /target.*missing|target.*not found|invalid target|目标不存在|请选择.*目标/i,
    message: '目标无效，请重新选择一个可见且合法的目标。',
  },
  {
    test: /incapacitated|stunned|paralyzed|unconscious|dead|stable|昏迷|震慑|麻痹|失能|倒地不起|濒死|死亡/i,
    message: '当前状态阻止你执行这个行动，请先解除状态或等待队友援助。',
  },
  {
    test: /pending.*expired|待处理.*过期|已过期/i,
    message: '这次待处理行动已经过期，请重新发起行动。',
  },
]

export function combatErrorMessage(raw) {
  const text = typeof raw === 'string'
    ? raw
    : raw?.message || raw?.detail || String(raw || '')
  const trimmed = text.trim()
  if (!trimmed) return '战斗行动失败，请重试。'

  const rule = RULES.find(({ test }) => test.test(trimmed))
  return rule?.message || trimmed
}

export function formatCombatError(error) {
  return combatErrorMessage(error)
}
