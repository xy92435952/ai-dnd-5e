// ════════════════════════════════════════════════════════════
// Portrait component — 职业纹章肖像
// ════════════════════════════════════════════════════════════
function Portrait({ cls = 'fighter', size = 'md', wounded = false, style, onClick }) {
  const sizeClass = { sm: 'portrait-sm', md: '', lg: 'portrait-lg', xl: 'portrait-xl' }[size] || '';
  return (
    <div className={`portrait portrait-${cls} ${sizeClass} ${wounded ? 'is-wounded' : ''}`} style={style} onClick={onClick}>
      {Crest[cls] || Crest.fighter}
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// Shared: dice badge, tag, divider
// ════════════════════════════════════════════════════════════
function Divider({ children }) {
  return (
    <div className="divider">
      <span className="divider-glyph">{children || '✦ ❧ ✦'}</span>
    </div>
  );
}

function DiceBadge({ children, crit, fumble }) {
  const cls = crit ? 'dice-badge crit' : fumble ? 'dice-badge fumble' : 'dice-badge';
  return <span className={cls}>🎲 {children}</span>;
}

// ════════════════════════════════════════════════════════════
// HP bar (with high/mid/low color shift)
// ════════════════════════════════════════════════════════════
function HpBar({ cur, max }) {
  const pct = Math.max(0, Math.min(100, (cur / max) * 100));
  const tone = pct > 60 ? 'high' : pct > 30 ? 'mid' : 'low';
  return (
    <div>
      <div className={`hp-bar ${tone}`}>
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginTop: 3, fontFamily: 'var(--font-mono)', color: 'var(--parchment-dark)' }}>
        <span>HP {cur}/{max}</span>
        <span>{tone === 'low' ? '⚠ 危急' : tone === 'mid' ? '受伤' : '健康'}</span>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// Character card — 侧栏角色状态
// ════════════════════════════════════════════════════════════
function CharCard({ char, active }) {
  return (
    <div className={`char-card ${active ? 'char-card-active' : ''}`}>
      <div className="char-card-row">
        <Portrait cls={char.cls} size="sm" wounded={char.hp_cur / char.hp_max < 0.35} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="char-card-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{char.name}</div>
          <div className="char-card-sub">{char.race} · {char.classLabel} Lv{char.level}</div>
        </div>
        {char.isPlayer && <span className="tag tag-gold">你</span>}
      </div>
      <HpBar cur={char.hp_cur} max={char.hp_max} />
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--parchment-dark)' }}>
        <span>AC <b style={{ color: 'var(--parchment)' }}>{char.ac}</b></span>
        <span style={{ opacity: .4 }}>|</span>
        <span>先攻 <b style={{ color: 'var(--parchment)' }}>{char.init >= 0 ? '+' : ''}{char.init}</b></span>
      </div>
      {char.slots && (
        <div>
          <div style={{ fontSize: 9, letterSpacing: '.2em', color: 'var(--parchment-dark)', textTransform: 'uppercase', marginBottom: 4 }}>法术位</div>
          {Object.entries(char.slots).map(([lvl, [cur, max]]) => (
            <div key={lvl} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <span style={{ fontSize: 9, color: 'var(--amethyst-light)', width: 18, fontFamily: 'var(--font-mono)' }}>{lvl}环</span>
              <div className="spell-slots">
                {Array.from({ length: max }).map((_, i) => (
                  <div key={i} className={`slot-gem ${i >= cur ? 'used' : ''}`} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {char.conditions && char.conditions.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {char.conditions.map(c => <span key={c} className="tag tag-danger" style={{ fontSize: 9 }}>{c}</span>)}
        </div>
      )}
    </div>
  );
}

window.Portrait = Portrait;
window.Divider = Divider;
window.DiceBadge = DiceBadge;
window.HpBar = HpBar;
window.CharCard = CharCard;
