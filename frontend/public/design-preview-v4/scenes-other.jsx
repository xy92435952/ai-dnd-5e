// ════════════════════════════════════════════════════════════
// Character Sheet + Class Gallery + Login/Home/Create/Room
// ════════════════════════════════════════════════════════════

const ALL_CLASSES = [
  { key: 'fighter', name: '战士', desc: '战阵中屹立不倒的钢铁意志' },
  { key: 'wizard', name: '法师', desc: '奥术研习者，操纵纯粹的魔法' },
  { key: 'cleric', name: '牧师', desc: '神祇的仆从，神圣的治愈者' },
  { key: 'rogue', name: '游荡者', desc: '阴影之间的敏捷刺客' },
  { key: 'paladin', name: '圣武士', desc: '誓言所铸的神圣战士' },
  { key: 'ranger', name: '游侠', desc: '荒野的守望与追踪者' },
  { key: 'barbarian', name: '蛮战士', desc: '狂暴怒火的原始力量' },
  { key: 'bard', name: '吟游诗人', desc: '用乐符编织魔法的艺人' },
  { key: 'druid', name: '德鲁伊', desc: '自然的守护者与变形者' },
  { key: 'sorcerer', name: '术士', desc: '血脉之中流淌的魔力' },
  { key: 'warlock', name: '契约师', desc: '与异界存在缔结契约' },
  { key: 'monk', name: '武僧', desc: '身体即武器，修行成道' },
];

function ClassGallery() {
  return (
    <div style={{ padding: '32px 28px', height: '100%', overflow: 'auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <div className="eyebrow">☙ 职业纹章图鉴 ❧</div>
        <div className="display-title" style={{ fontSize: 28, marginTop: 4 }}>十二道英雄之路</div>
        <div style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)', marginTop: 6, fontSize: 13 }}>
          ~ 每个职业都有专属的纹章与配色，替代无辨识度的通用头像 ~
        </div>
      </div>
      <Divider>⚜ Classes ⚜</Divider>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 16, maxWidth: 1100, margin: '16px auto 0' }}>
        {ALL_CLASSES.map(c => (
          <div key={c.key} className="panel-ornate" style={{ padding: '18px 14px', textAlign: 'center', transition: 'var(--transition)' }}>
            <Portrait cls={c.key} size="lg" style={{ margin: '0 auto 10px' }} />
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, color: 'var(--parchment)', marginBottom: 3 }}>{c.name}</div>
            <div className="eyebrow" style={{ fontSize: 9 }}>{c.key.toUpperCase()}</div>
            <div style={{ fontFamily: 'var(--font-script)', fontSize: 12, color: 'var(--parchment-dark)', fontStyle: 'italic', marginTop: 6, lineHeight: 1.5 }}>
              "{c.desc}"
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Character Sheet ────────────────────────────────────
function CharacterSheet() {
  return (
    <div style={{ padding: 28, height: '100%', overflow: 'auto', maxWidth: 1000, margin: '0 auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 24, alignItems: 'start' }}>
        {/* 左 — 肖像 + 基本信息 */}
        <div className="panel-ornate" style={{ padding: '22px 18px', textAlign: 'center', position: 'sticky', top: 0 }}>
          <Portrait cls="paladin" size="xl" style={{ margin: '0 auto 14px' }} />
          <div className="display-title" style={{ fontSize: 20 }}>艾琳·晨光</div>
          <div className="eyebrow" style={{ marginTop: 4 }}>半精灵 · 圣武士 · 5级</div>
          <div style={{ margin: '14px 0', padding: '10px 8px', borderTop: '1px solid var(--bark-light)', borderBottom: '1px solid var(--bark-light)' }}>
            <div style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', fontSize: 12, color: 'var(--parchment-dark)', lineHeight: 1.6 }}>
              "以晨光之名，<br/>驱散世间阴霾。"
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 10 }}>
            <StatPill label="HP" value="42/48" tone="ok" />
            <StatPill label="AC" value="18" tone="gold" />
            <StatPill label="先攻" value="+2" />
            <StatPill label="速度" value="30ft" />
            <StatPill label="经验" value="6,500" tone="gold" />
            <StatPill label="熟练" value="+3" />
          </div>
        </div>

        {/* 右 — 详细 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* 能力值 */}
          <Section title="✦ 能力值 ✦">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
              {[['力量', 16, 3], ['敏捷', 10, 0], ['体质', 14, 2], ['智力', 10, 0], ['感知', 13, 1], ['魅力', 16, 3]].map(([l, s, m]) => (
                <div key={l} className="ability-card">
                  <div className="label">{l}</div>
                  <div className="score">{s}</div>
                  <div className={`mod ${m < 0 ? 'neg' : ''}`}>{m >= 0 ? '+' : ''}{m}</div>
                </div>
              ))}
            </div>
          </Section>

          {/* 已备法术 */}
          <Section title="✧ 已备法术 · 第1环 ✧">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 8 }}>
              {['治疗伤口', '祝福', '神圣斥喝', '护盾术', '庇护术', '英勇术'].map(s => (
                <div key={s} style={{
                  padding: '8px 12px',
                  background: 'linear-gradient(180deg, rgba(138,79,212,.12), rgba(58,16,90,.18))',
                  border: '1px solid var(--amethyst)',
                  borderRadius: 'var(--radius)',
                  fontFamily: 'var(--font-script)',
                  fontSize: 13, color: 'var(--amethyst-light)',
                  textAlign: 'center',
                  position: 'relative',
                }}>
                  ✦ {s}
                </div>
              ))}
            </div>
          </Section>

          {/* 装备 */}
          <Section title="⚔ 装备 ⚔">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {[['⚔', '+1 长剑', 'gold'], ['🛡', '圣徽盾', 'info'], ['👘', '板甲', 'info'], ['🧪', '治疗药水×3', 'ok'], ['✦', '祝福圣物', 'magic'], ['💰', '280 gp', 'gold']].map(([i, n, t]) => (
                <span key={n} className={`tag tag-${t}`} style={{ fontSize: 11, padding: '4px 12px' }}>
                  <span style={{ marginRight: 4 }}>{i}</span>{n}
                </span>
              ))}
            </div>
          </Section>

          {/* 特性 */}
          <Section title="❖ 职业特性 ❖">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[['神性感知', '感知30尺内的天界、邪魔、不死生物'],
                ['圣疗之触', '用双手疗愈伤势，每日25点'],
                ['神圣打击', '消耗法术位造成辐光伤害'],
                ['誓言守护', '第3级誓言 · 保护弱者']].map(([n, d]) => (
                <div key={n} style={{ padding: '10px 12px', background: 'rgba(58,36,22,.4)', borderLeft: '2px solid var(--amber)', borderRadius: 4 }}>
                  <div style={{ fontFamily: 'var(--font-heading)', fontSize: 13, color: 'var(--amber)' }}>{n}</div>
                  <div style={{ fontSize: 12, color: 'var(--parchment)', marginTop: 2, fontStyle: 'italic' }}>{d}</div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--amber)', letterSpacing: '.15em' }}>{title}</span>
        <span style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, var(--amber), transparent)', opacity: .4 }} />
      </div>
      {children}
    </div>
  );
}

function StatPill({ label, value, tone }) {
  const color = tone === 'gold' ? 'var(--amber)' : tone === 'ok' ? 'var(--emerald-light)' : 'var(--parchment)';
  return (
    <div style={{ padding: '6px 8px', background: 'rgba(10,6,2,.5)', border: '1px solid var(--bark-light)', borderRadius: 4, textAlign: 'center' }}>
      <div style={{ fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.15em', fontFamily: 'var(--font-mono)' }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 15, color, fontWeight: 700, marginTop: 2 }}>{value}</div>
    </div>
  );
}

// ─── Login ────────────────────────────────────────────
function LoginScene() {
  return (
    <div style={{ height: '100%', display: 'grid', placeItems: 'center', padding: 24, position: 'relative', overflow: 'hidden' }}>
      {/* 背景符文 */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: .18 }}>
        <div className="rune-ring" style={{ position: 'absolute', top: '10%', left: '-60px', width: 240, height: 240 }} />
        <div className="rune-ring" style={{ position: 'absolute', bottom: '-80px', right: '5%', width: 320, height: 320, animationDuration: '90s' }} />
      </div>
      <div className="panel-ornate" style={{ padding: '42px 48px', width: 420, maxWidth: '92vw', position: 'relative', textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>⚜</div>
        <div className="display-title" style={{ fontSize: 26, letterSpacing: '.15em' }}>龙与编年史</div>
        <div className="eyebrow" style={{ marginTop: 8 }}>✦ AI 地下城 · D&D 5e ✦</div>
        <div style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', fontSize: 13, color: 'var(--parchment-dark)', margin: '14px 0 22px', lineHeight: 1.8 }}>
          "推开厚重的橡木门，<br/>你的传奇将由此开启..."
        </div>
        <Divider>❧</Divider>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 18 }}>
          <input className="input-fantasy" placeholder="英雄之名" defaultValue="艾琳" />
          <input className="input-fantasy" type="password" placeholder="秘语密印" defaultValue="••••••" />
          <button className="btn-gold" style={{ padding: '14px', marginTop: 6, fontSize: 14, letterSpacing: '.2em' }}>✦ 进入传说 ✦</button>
          <button className="btn-ghost">创建新的英雄档案</button>
        </div>
      </div>
    </div>
  );
}

// ─── Home ─────────────────────────────────────────────
function HomeScene() {
  const modules = [
    { name: '银谷村的阴影', prog: '第 3 章 · 低语者酒馆', lvl: 'Lv 3-6', players: '1-4', featured: true },
    { name: '深渊之钟', prog: '未开始', lvl: 'Lv 7-10', players: '2-4' },
    { name: '永夜之冬', prog: '第 1 章 · 雪原', lvl: 'Lv 1-3', players: '3-5' },
  ];
  const saves = [
    { name: '艾琳的圣战', cls: 'paladin', chapter: '第 3 章', time: '2小时前' },
    { name: '薇拉的觉醒', cls: 'wizard', chapter: '第 2 章', time: '昨日' },
    { name: '索恩的复仇', cls: 'fighter', chapter: '序章', time: '3 日前' },
  ];
  return (
    <div style={{ padding: '24px 32px', height: '100%', overflow: 'auto' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <div className="eyebrow">❧ 英雄大厅 ❧</div>
          <div className="display-title" style={{ fontSize: 32, marginTop: 4 }}>欢迎归来，艾琳</div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn-ghost">☰ 多人房间</button>
          <button className="btn-ghost">⚙ 设置</button>
          <Portrait cls="paladin" size="sm" />
        </div>
      </header>

      <Divider>⚜ 选择你的冒险 ⚜</Divider>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 16, marginTop: 20 }}>
        {modules.map((m, i) => (
          <div key={m.name} className="panel-ornate" style={{ padding: 20, gridColumn: i === 0 ? 'span 1' : undefined, minHeight: i === 0 ? 200 : 160, position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            {i === 0 && (
              <div style={{ position: 'absolute', top: 12, right: 12 }}>
                <span className="tag tag-gold" style={{ fontSize: 10 }}>★ 进行中</span>
              </div>
            )}
            <div>
              <div style={{ fontSize: i === 0 ? 32 : 22, marginBottom: 10 }}>{i === 0 ? '🏰' : i === 1 ? '🔔' : '❄'}</div>
              <div className="display-title" style={{ fontSize: i === 0 ? 22 : 17 }}>{m.name}</div>
              <div style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', fontSize: 12, color: 'var(--parchment-dark)', marginTop: 6 }}>{m.prog}</div>
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
              <span className="tag tag-info" style={{ fontSize: 10 }}>{m.lvl}</span>
              <span className="tag tag-blue" style={{ fontSize: 10 }}>{m.players} 人</span>
            </div>
            <button className={i === 0 ? 'btn-gold' : 'btn-ghost'} style={{ marginTop: 14, fontSize: 11 }}>
              {i === 0 ? '继续冒险 ►' : '开始 ►'}
            </button>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 32 }}>
        <Divider>❦ 存档档案 ❦</Divider>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px,1fr))', gap: 12, marginTop: 14 }}>
          {saves.map(s => (
            <div key={s.name} className="panel" style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'center', cursor: 'pointer' }}>
              <Portrait cls={s.cls} size="sm" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: 'var(--font-heading)', fontSize: 13, color: 'var(--parchment)', fontWeight: 600 }}>{s.name}</div>
                <div style={{ fontSize: 11, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)' }}>{s.chapter} · {s.time}</div>
              </div>
              <span style={{ color: 'var(--amber)' }}>►</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Room Lobby ───────────────────────────────────────
function RoomScene() {
  const members = [
    { name: '艾琳·晨光', cls: 'paladin', host: true, online: true, ready: true },
    { name: '索恩·石拳', cls: 'fighter', online: true, ready: true },
    { name: '薇拉·月语', cls: 'wizard', online: true, ready: false },
    { name: '凯瑞丝', cls: 'rogue', online: false, ready: false },
  ];
  return (
    <div style={{ padding: 28, height: '100%', overflow: 'auto', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 18 }}>
        <div className="eyebrow">✦ 多人房间 ✦</div>
        <div className="display-title" style={{ fontSize: 28, marginTop: 4 }}>银谷村的阴影</div>
        <div style={{ marginTop: 10, display: 'inline-flex', gap: 10, alignItems: 'center', padding: '6px 16px', background: 'rgba(10,6,2,.6)', border: '1px solid var(--amber)', borderRadius: 24 }}>
          <span className="eyebrow" style={{ fontSize: 10 }}>房间码</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 18, color: 'var(--amber)', fontWeight: 700, letterSpacing: '.3em' }}>D4-7Z9K</span>
          <button style={{ background: 'transparent', border: 'none', color: 'var(--parchment-dark)', cursor: 'pointer', fontSize: 13 }}>⎘</button>
        </div>
      </div>

      <Divider>❧ 冒险者们 ❧</Divider>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14, marginTop: 18 }}>
        {members.map(m => (
          <div key={m.name} className="panel-ornate" style={{ padding: 14, display: 'flex', gap: 14, alignItems: 'center', opacity: m.online ? 1 : .5 }}>
            <div style={{ position: 'relative' }}>
              <Portrait cls={m.cls} size="md" />
              <span style={{
                position: 'absolute', bottom: 0, right: 0,
                width: 14, height: 14, borderRadius: '50%',
                background: m.online ? 'var(--emerald-light)' : 'var(--bark-light)',
                border: '2px solid var(--void)',
                boxShadow: m.online ? '0 0 8px var(--emerald-light)' : 'none',
              }} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontFamily: 'var(--font-heading)', color: 'var(--parchment)', fontSize: 14, fontWeight: 600 }}>{m.name}</span>
                {m.host && <span className="tag tag-gold" style={{ fontSize: 9 }}>★ 主持</span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                {m.online ? (m.ready ? '✓ 已就绪' : '○ 准备中...') : '◌ 离线'}
              </div>
            </div>
            {m.online && m.ready && <span style={{ color: 'var(--emerald-light)', fontSize: 20 }}>✓</span>}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 22, textAlign: 'center' }}>
        <button className="btn-gold" style={{ padding: '12px 32px', fontSize: 14 }}>✦ 开启冒险 ✦</button>
      </div>
    </div>
  );
}

window.ClassGallery = ClassGallery;
window.CharacterSheet = CharacterSheet;
window.LoginScene = LoginScene;
window.HomeScene = HomeScene;
window.RoomScene = RoomScene;
