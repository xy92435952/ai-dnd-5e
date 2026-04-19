// ════════════════════════════════════════════════════════════
// Adventure Scene — RPG 游戏化版本
// CRPG 舞台 + 大头像 + 编号对话选项（带检定/职业标签）+ 底部HUD队伍条
// ════════════════════════════════════════════════════════════

const ADV_PARTY = [
  { id: 'p1', name: '艾琳',   cls: 'paladin', letter: '艾', hp: 38, max: 48, active: true },
  { id: 'p2', name: '凯瑞丝', cls: 'rogue',   letter: '凯', hp: 32, max: 36 },
  { id: 'p3', name: '薇拉',   cls: 'wizard',  letter: '薇', hp: 14, max: 28 },
  { id: 'p4', name: '索恩',   cls: 'fighter', letter: '索', hp: 45, max: 52 },
];

const ADV_LINES = [
  { kind: 'narration', txt: '你推开酒馆沉重的橡木门。火光与笑语扑面而来，空气里浮着烤野猪与陈年麦酒的气息。' },
  { kind: 'narration', txt: '角落阴影里坐着一名戴兜帽的老者，眼睛在兜帽下闪着古怪的蓝光。他沙哑地，极轻地——念出了你的真名。' },
];

const ADV_DIALOGUE = {
  speaker: { name: '兜帽老者', title: '无名议会信使？', role: 'npc', letter: '影', cls: 'warlock' },
  line: '「年轻的圣武士，我等你已经七年了。」他缓缓摊开手掌，一枚银色徽章静静躺在掌心，徽章表面浮现出淡蓝色的符文。',
};

const ADV_CHOICES = [
  { idx: 1, tags: [{ t: '洞察', k: 'insight', dc: 14 }], txt: '仔细观察他的神情——他是真心的，还是在设局？', skillCheck: true },
  { idx: 2, tags: [{ t: '圣武士', k: 'class' }, { t: '劝说', k: 'persuade', dc: 12 }], txt: '「以我的誓言发问：你服从于哪一位神？」', skillCheck: true },
  { idx: 3, tags: [{ t: '历史', k: 'check', dc: 15 }], txt: '「无名议会」——你在古籍里读过这个名字吗？', skillCheck: true },
  { idx: 4, tags: [], txt: '接过徽章，指尖顺着符文纹路抚过。' },
  { idx: 5, tags: [{ t: '威吓', k: 'intim', dc: 16 }], txt: '「在我拔剑之前，老实说出你的来意。」', skillCheck: true, action: true },
  { idx: 6, tags: [{ t: '队伍', k: 'class' }], txt: '（转头）低声对索恩说：「觉得他可信吗？」' },
  { idx: 7, tags: [{ t: '失败', k: 'fail' }], txt: '拒绝并转身离开酒馆。', ended: true },
];

function AdventureScene() {
  const [freeInput, setFreeInput] = React.useState('');

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#06040a' }}>

      {/* 顶部章节条 */}
      <div style={{
        position: 'relative',
        padding: '10px 20px',
        display: 'grid',
        gridTemplateColumns: '1fr auto 1fr',
        alignItems: 'center',
        background: 'linear-gradient(180deg, rgba(16,10,4,.95), rgba(10,6,2,.7))',
        borderBottom: '1px solid rgba(138,90,24,.4)',
        boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
        zIndex: 4,
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }}>◄ 主页</button>
          <span className="tag tag-gold" style={{ fontSize: 9 }}>● 自动存档</span>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.3em', opacity: .7 }}>CHAPTER III</div>
          <div className="display-title" style={{ fontSize: 18, letterSpacing: '.12em' }}>银谷村的阴影</div>
        </div>
        <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }}>☰ 日志</button>
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }}>☾ 休息</button>
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }}>✧ 法术</button>
        </div>
      </div>

      {/* ═══ 主舞台区 ═══ */}
      <div style={{ flex: 1, display: 'grid', gridTemplateRows: '1fr auto auto', overflow: 'hidden' }}>

        {/* 剧场舞台 —— 背景 + 两侧大头像 */}
        <div className="dialogue-stage" style={{ position: 'relative' }}>
          <div className="stage-letterbox top" />

          {/* NPC 大头像（左） */}
          <div className="stage-figure left" style={{ '--c-light': '#7a4fc4' }}>
            <div className="silhouette" style={{ background: 'radial-gradient(circle at 40% 30%, #7a4fc4, #1a0a3a 75%)' }}>
              <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', fontFamily: 'var(--font-display)', fontSize: 72, color: '#d8c8ff', textShadow: '0 4px 12px #000', filter: 'drop-shadow(0 0 12px rgba(168,144,232,.6))' }}>影</div>
              {/* 发光的眼睛 */}
              <span style={{ position: 'absolute', left: '35%', top: '35%', width: 6, height: 3, borderRadius: 2, background: '#7fe8f8', boxShadow: '0 0 10px #7fe8f8' }} />
              <span style={{ position: 'absolute', right: '35%', top: '35%', width: 6, height: 3, borderRadius: 2, background: '#7fe8f8', boxShadow: '0 0 10px #7fe8f8' }} />
            </div>
            <div className="nameplate">❖ 兜帽老者</div>
          </div>

          {/* 玩家大头像（右） */}
          <div className="stage-figure right">
            <div className="silhouette" style={{ background: 'radial-gradient(circle at 40% 30%, #e8d070, #6a5020 75%)' }}>
              <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', fontFamily: 'var(--font-display)', fontSize: 72, color: '#fff8dd', textShadow: '0 4px 12px #000' }}>艾</div>
            </div>
            <div className="nameplate" style={{ background: 'linear-gradient(180deg, #3ec8d8, #14444e)', color: '#04181c', boxShadow: '0 0 0 1px rgba(127,232,248,.6), 0 0 12px -2px var(--arcane-light)' }}>◈ 艾琳·晨光</div>
          </div>

          {/* 中间粒子 / 徽章特效 */}
          <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', pointerEvents: 'none' }}>
            <div style={{ width: 54, height: 54, borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(127,232,248,.8), transparent 70%)',
              filter: 'blur(6px)', animation: 'breathe 2s ease-in-out infinite' }} />
          </div>

          {/* 场景信息（左上角角标） */}
          <div style={{ position: 'absolute', top: 12, left: 16, display: 'flex', gap: 10, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--parchment-dark)', letterSpacing: '.15em', zIndex: 4 }}>
            <span>🜂 低语者酒馆</span>
            <span style={{ opacity: .5 }}>|</span>
            <span>☀ 黄昏</span>
            <span style={{ opacity: .5 }}>|</span>
            <span style={{ color: 'var(--blood-light)' }}>⚠ 紧张</span>
          </div>

          <div className="stage-letterbox bottom" />
        </div>

        {/* CRPG 对话框 —— 锁定在舞台下方 */}
        <div style={{ overflow: 'auto' }}>
          {/* 旁白段 */}
          <div style={{ padding: '10px 28px 0', maxWidth: 820, margin: '0 auto' }}>
            {ADV_LINES.map((l, i) => (
              <p key={i} style={{
                fontFamily: 'var(--font-script)',
                fontStyle: 'italic',
                color: 'var(--parchment-dark)',
                fontSize: 14,
                lineHeight: 1.7,
                margin: '6px 0',
                padding: '0 0 0 14px',
                borderLeft: '2px solid rgba(138,90,24,.4)',
              }}>{l.txt}</p>
            ))}
          </div>

          {/* 发言主气泡 */}
          <div className="crpg-dialogue" style={{ margin: '10px 24px 0' }}>
            <div className="speaker-tab npc">❖ {ADV_DIALOGUE.speaker.name} · {ADV_DIALOGUE.speaker.title}</div>
            <p className="line">{ADV_DIALOGUE.line}</p>

            {/* ── 编号选项列表（CRPG 核心） ── */}
            <div style={{ borderTop: '1px solid rgba(138,90,24,.35)', paddingTop: 12, marginTop: 6 }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--arcane-light)', letterSpacing: '.25em', textTransform: 'uppercase', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ flex: 0, color: 'var(--parchment-dark)' }}>▼</span>
                <span>你的回应</span>
                <span style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(127,232,248,.4), transparent)' }} />
                <span style={{ color: 'var(--parchment-dark)' }}>1–7 快捷键</span>
              </div>

              <div className="choice-list">
                {ADV_CHOICES.map(c => (
                  <button key={c.idx} className={`choice ${c.action ? 'action' : ''} ${c.ended ? 'ended' : ''}`}>
                    <span className="idx">{c.idx}</span>
                    <span className="body">
                      {c.tags.length > 0 && (
                        <span className="tags">
                          {c.tags.map((t, ti) => (
                            <span key={ti} className={`tag-mini tm-${t.k}`}>
                              [{t.t}{t.dc ? ` · DC${t.dc}` : ''}]
                            </span>
                          ))}
                        </span>
                      )}
                      <span>{c.txt}</span>
                      {c.skillCheck && (
                        <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', letterSpacing: '.1em' }}>
                          🎲
                        </span>
                      )}
                    </span>
                  </button>
                ))}
              </div>

              {/* 自由输入 */}
              <div className="free-speak">
                <span className="label">✎ 自由行动</span>
                <input
                  value={freeInput}
                  onChange={e => setFreeInput(e.target.value)}
                  placeholder="或直接描述你的行动..."
                />
                <button className="skill-chip" style={{ padding: '4px 10px', fontSize: 10 }}>🎲 掷骰</button>
                <button className="skill-chip" style={{ padding: '4px 10px', fontSize: 10, background: 'linear-gradient(180deg, #3ec8d8, #14444e)', color: '#04181c', borderColor: '#2a7a88' }}>➤ 发送</button>
              </div>
            </div>
          </div>
        </div>

        {/* ═══ 底部 HUD：队伍条 + 卷宗 + 目标 ═══ */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr auto',
          gap: 12,
          padding: '10px 20px 12px',
          background: 'linear-gradient(180deg, transparent, rgba(10,6,4,.95) 40%, rgba(10,6,4,1) 100%)',
          borderTop: '1px solid rgba(138,90,24,.5)',
          boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
        }}>
          {/* 队伍条 */}
          <div className="party-hud">
            {ADV_PARTY.map(p => {
              const pct = (p.hp / p.max) * 100;
              const tone = pct < 34 ? 'low' : pct < 67 ? 'mid' : '';
              return (
                <div key={p.id} className={`party-slot ${p.active ? 'active' : ''} ${tone}`}>
                  <div className="frame" />
                  <div style={{
                    position: 'absolute', inset: 2,
                    borderRadius: '50%',
                    background: `radial-gradient(circle at 35% 30%, ${p.cls === 'paladin' ? '#e8d070' : p.cls === 'rogue' ? '#8a94aa' : p.cls === 'wizard' ? '#a070e8' : '#c46a48'}, ${p.cls === 'paladin' ? '#6a5020' : p.cls === 'rogue' ? '#1a1e2a' : p.cls === 'wizard' ? '#3a1a6a' : '#6a1818'} 75%)`,
                    display: 'grid', placeItems: 'center',
                    fontFamily: 'var(--font-display)', color: '#fff', fontWeight: 700, fontSize: 18,
                    textShadow: '0 2px 4px rgba(0,0,0,.9)',
                  }}>{p.letter}</div>
                  <div className="hp-micro"><div className="fill" style={{ width: `${pct}%` }} /></div>
                </div>
              );
            })}
          </div>

          {/* 线索 / 卷宗 快捷条 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '6px 12px',
            background: 'linear-gradient(180deg, rgba(26,18,8,.8), rgba(10,6,4,.6))',
            border: '1px solid rgba(138,90,24,.4)',
            boxShadow: 'inset 0 1px 0 rgba(240,208,96,.12)',
            overflow: 'hidden',
          }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>◆ 目标</span>
            <span style={{ color: 'var(--blood-light)', fontSize: 12, fontFamily: 'var(--font-body)' }}>弄清兜帽老者来意</span>
            <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--arcane-light)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>❖ 线索 3</span>
            <div style={{ display: 'flex', gap: 6, overflow: 'hidden' }}>
              <span style={{ fontSize: 11, color: 'var(--parchment-dark)', fontStyle: 'italic', whiteSpace: 'nowrap' }}>袖口螺旋烙印</span>
              <span style={{ fontSize: 11, color: 'var(--parchment-dark)', fontStyle: 'italic', whiteSpace: 'nowrap' }}>· 银徽淡蓝符文</span>
              <span style={{ fontSize: 11, color: 'var(--amber)', fontStyle: 'italic', whiteSpace: 'nowrap' }}>· 等了七年</span>
              <span style={{ fontSize: 8, color: 'var(--amber)', border: '1px solid var(--amber)', padding: '0 5px', letterSpacing: '.15em', fontFamily: 'var(--font-mono)', alignSelf: 'center' }}>NEW</span>
            </div>
          </div>

          {/* 快捷 */}
          <div style={{ display: 'flex', gap: 4 }}>
            <button className="skill-chip" style={{ padding: '6px 12px', fontSize: 10 }}>⚑ 密语</button>
            <button className="skill-chip" style={{ padding: '6px 12px', fontSize: 10 }}>☰ 卷宗</button>
          </div>
        </div>
      </div>
    </div>
  );
}

window.AdventureScene = AdventureScene;
