export default function AdventureQuestHud({ questLine, clues }) {
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
      <div style={{ display: 'flex', gap: 6, overflow: 'hidden' }}>
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
    </div>
  )
}
