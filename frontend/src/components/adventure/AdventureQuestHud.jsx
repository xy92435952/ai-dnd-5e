const RECENT_TYPE_LABELS = {
  quest: '任务',
  clue: '线索',
  decision: '决定',
  npc: 'NPC',
  world: '后果',
}

export default function AdventureQuestHud({
  questLine,
  clues,
  npcUpdates = [],
  keyDecisions = [],
  recentConsequences = [],
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '6px 12px',
      background: 'linear-gradient(180deg, rgba(26,18,8,.8), rgba(10,6,4,.6))',
      border: '1px solid rgba(138,90,24,.4)',
      boxShadow: 'inset 0 1px 0 rgba(240,208,96,.12)',
      overflow: 'hidden',
    }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>◆ 目标</span>
      <span style={{ color: questLine ? 'var(--blood-light)' : 'var(--parchment-dark)', fontSize: 12, fontFamily: 'var(--font-body)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {questLine?.quest || '继续冒险'}
      </span>
      <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--arcane-light)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>❖ 线索 {clues.length}</span>
      <div style={{ display: 'flex', gap: 6, overflow: 'hidden', minWidth: 0 }}>
        {clues.map((c, i) => (
          <span key={i} style={{
            fontSize: 11,
            color: c.is_new ? 'var(--amber)' : 'var(--parchment-dark)',
            fontStyle: 'italic', whiteSpace: 'nowrap',
          }}>
            {i > 0 ? '· ' : ''}{c.text}
            {c.is_new && (
              <span style={{ fontSize: 8, color: 'var(--amber)', border: '1px solid var(--amber)', padding: '0 5px', letterSpacing: '.15em', fontFamily: 'var(--font-mono)', marginLeft: 4 }}>
                NEW
              </span>
            )}
          </span>
        ))}
      </div>
      {(npcUpdates.length > 0 || keyDecisions.length > 0) && (
        <>
          <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.18em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>记忆</span>
          <div style={{ display: 'flex', gap: 6, overflow: 'hidden', minWidth: 0 }}>
            {npcUpdates.map(npc => (
              <span key={`npc-${npc.name}`} title={(npc.keyFacts || []).join('；')} style={{
                fontSize: 11,
                color: 'var(--parchment-light)',
                whiteSpace: 'nowrap',
              }}>
                {npc.name}:{npc.relationship}
              </span>
            ))}
            {keyDecisions.slice(-1).map(decision => (
              <span key={`decision-${decision}`} title={decision} style={{
                fontSize: 11,
                color: 'var(--amber)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: 180,
              }}>
                · {decision}
              </span>
            ))}
          </div>
        </>
      )}
      {recentConsequences.length > 0 && (
        <>
          <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.18em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>最近</span>
          <div className="quest-recent-list">
            {recentConsequences.map((item, index) => {
              const type = item.type || 'note'
              const typeLabel = RECENT_TYPE_LABELS[type] || '记录'
              const detail = item.detail ? `：${item.detail}` : ''
              return (
                <span
                  key={`${type}-${item.label}-${index}`}
                  className={`quest-recent-item ${type}`}
                  title={`${typeLabel} ${item.label}${detail}`}
                >
                  <b>{typeLabel}</b>{item.label}{detail}
                </span>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
