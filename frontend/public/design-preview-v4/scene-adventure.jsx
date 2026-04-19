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

// ── 历史对话流（当前回合之前的所有交互） ──
const ADV_HISTORY = [
  { kind: 'scene', txt: '—— 章节 III · 银谷村的阴影 ——', time: '黄昏 · 低语者酒馆' },
  { kind: 'narration', txt: '你与同伴在驿道上追查失踪的信使，循着线索抵达银谷村。夜色渐浓，酒馆里弥漫着烤肉和麦酒的气息。' },
  { kind: 'npc', speaker: '酒馆老板', cls: 'commoner', letter: '酒', txt: '「客官远道而来，要点什么？小店的兔肉派是本地一绝。」' },
  { kind: 'player', speaker: '艾琳', letter: '艾', txt: '「一壶麦酒，四人份。——对了，最近村里可有外乡人？」', choice: '① 打听情况' },
  { kind: 'roll', label: '调查', dc: 12, roll: 15, mod: 3, total: 18, result: 'success', txt: '调查 +3 · 骰面 15 = 18 · 通过 DC 12' },
  { kind: 'npc', speaker: '酒馆老板', cls: 'commoner', letter: '酒', txt: '「有…有一位。角落那位戴兜帽的老者，独自坐了整整三天，一口吃食都没动。只喝水。」他压低声音，「眼神怪得很，您瞧着自己留心。」' },
  { kind: 'narration', txt: '你顺着他的目光望去。角落阴影里，兜帽老者仿佛察觉到了你的注视——他抬起头，两点幽蓝光芒在兜帽深处缓缓亮起。' },
  { kind: 'player', speaker: '艾琳', letter: '艾', txt: '（按住腰间的剑柄，缓步走向那个角落。）', choice: '② 主动接近' },
  { kind: 'npc', speaker: '兜帽老者', cls: 'warlock', letter: '影', txt: '「坐下吧，圣武士。」他的声音沙哑低沉，像砂砾摩擦石板，「我等你已经——七年了。」', emphasis: true },
  { kind: 'narration', txt: '你的同伴不自觉地聚拢过来。凯瑞丝的手指轻轻搭上匕首柄，索恩横开一步挡在薇拉身前。' },
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

function DialogueHistoryView({ onBack }) {
  const scrollRef = React.useRef(null);
  const [atBottom, setAtBottom] = React.useState(true);

  // 打开时直接滚到底部（最新记录）
  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  const handleScroll = (e) => {
    const el = e.target;
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 60);
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'linear-gradient(180deg, #0a0604 0%, #06040a 100%)' }}>
      {/* 顶部返回条 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '12px 20px',
        background: 'linear-gradient(180deg, rgba(16,10,4,.95), rgba(10,6,2,.85))',
        borderBottom: '1px solid rgba(138,90,24,.5)',
        boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15), 0 4px 10px -4px rgba(0,0,0,.8)',
        zIndex: 5,
      }}>
        <button className="btn-ghost" style={{ padding: '6px 14px', fontSize: 11, borderColor: 'rgba(127,232,248,.6)', color: 'var(--arcane-light)' }} onClick={onBack}>
          ◀ 返回对话
        </button>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.35em', opacity: .7 }}>DIALOGUE LOG</div>
          <div className="display-title" style={{ fontSize: 18, letterSpacing: '.12em', color: 'var(--parchment)' }}>对话史册 · 第三章</div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <button className="btn-ghost" style={{ padding: '6px 10px', fontSize: 10 }}>⤓ 导出</button>
          <button className="btn-ghost" style={{ padding: '6px 10px', fontSize: 10 }}>⚲ 搜索</button>
        </div>
      </div>

      {/* 章节目录（左侧）+ 内容（右侧）*/}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '180px 1fr', overflow: 'hidden' }}>

        {/* 左 · 章节目录 */}
        <div style={{
          borderRight: '1px solid rgba(138,90,24,.35)',
          background: 'rgba(10,6,2,.5)',
          padding: '16px 10px',
          overflow: 'auto',
        }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.25em', textTransform: 'uppercase', marginBottom: 10, padding: '0 6px' }}>章节目录</div>
          {[
            { i: 'I',   title: '启程之日',    cur: false, turns: 24 },
            { i: 'II',  title: '驿道追踪',    cur: false, turns: 18 },
            { i: 'III', title: '银谷村的阴影', cur: true,  turns: 10 },
          ].map(ch => (
            <div key={ch.i} className={`chapter-nav ${ch.cur ? 'current' : ''}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontFamily: 'var(--font-display)', fontSize: 12, color: ch.cur ? 'var(--amber)' : 'var(--parchment-dark)', letterSpacing: '.15em' }}>{ch.i}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--parchment-dark)', letterSpacing: '.1em' }}>{ch.turns} 轮</span>
              </div>
              <div style={{ fontSize: 12, color: ch.cur ? 'var(--parchment)' : 'rgba(232,200,160,.6)', marginTop: 2 }}>{ch.title}</div>
            </div>
          ))}

          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.25em', textTransform: 'uppercase', marginTop: 24, marginBottom: 10, padding: '0 6px' }}>筛选</div>
          {[
            { k: 'all',   n: '全部',   c: 52, active: true },
            { k: 'npc',   n: '仅 NPC 对话', c: 18 },
            { k: 'player',n: '仅玩家发言', c: 14 },
            { k: 'roll',  n: '仅检定结果', c: 8 },
            { k: 'narr',  n: '仅旁白',  c: 12 },
          ].map(f => (
            <div key={f.k} className={`filter-pill ${f.active ? 'active' : ''}`}>
              <span>{f.n}</span>
              <span className="count">{f.c}</span>
            </div>
          ))}
        </div>

        {/* 右 · 滚动对话流 */}
        <div ref={scrollRef} onScroll={handleScroll} className="adv-history-scroll" style={{ overflow: 'auto', position: 'relative' }}>
          <div className="dialogue-history" style={{ padding: '20px 40px 80px', maxWidth: 900, margin: '0 auto', width: '100%' }}>
            {ADV_HISTORY.map((h, i) => {
              if (h.kind === 'scene') {
                return (
                  <div key={i} className="hist-divider">
                    <span className="ornament">❦</span>
                    <span className="title">{h.txt}</span>
                    <span className="time">{h.time}</span>
                  </div>
                );
              }
              if (h.kind === 'narration') {
                return <p key={i} className="hist-narration">{h.txt}</p>;
              }
              if (h.kind === 'npc') {
                return (
                  <div key={i} className="hist-bubble npc">
                    <div className="hist-avatar npc" data-cls={h.cls}>{h.letter}</div>
                    <div className="hist-body">
                      <div className="hist-name">❖ {h.speaker}</div>
                      <p className={`hist-line ${h.emphasis ? 'emphasis' : ''}`}>{h.txt}</p>
                    </div>
                  </div>
                );
              }
              if (h.kind === 'player') {
                return (
                  <div key={i} className="hist-bubble player">
                    <div className="hist-body">
                      <div className="hist-name">◈ {h.speaker}</div>
                      {h.choice && <div className="hist-choice-tag">{h.choice}</div>}
                      <p className="hist-line">{h.txt}</p>
                    </div>
                    <div className="hist-avatar player">{h.letter}</div>
                  </div>
                );
              }
              if (h.kind === 'roll') {
                return (
                  <div key={i} className={`hist-roll ${h.result}`}>
                    <span className="die">🎲</span>
                    <span className="check">{h.label} · DC {h.dc}</span>
                    <span className="calc">{h.roll}{h.mod>=0?'+':''}{h.mod} = <b>{h.total}</b></span>
                    <span className={`outcome ${h.result}`}>{h.result==='success'?'✓ 通过':'✗ 失败'}</span>
                  </div>
                );
              }
              return null;
            })}

            {/* 当前对话标识（未结束）*/}
            <div className="hist-current-divider" style={{ marginTop: 24 }}>
              <span className="dot" /><span className="label">当前 · 对话进行中</span><span className="dot" />
            </div>
            <div style={{
              padding: '14px 18px',
              background: 'linear-gradient(180deg, rgba(40,26,14,.6), rgba(26,18,8,.4))',
              border: '1px dashed rgba(138,90,24,.5)',
              fontFamily: 'var(--font-script)',
              fontStyle: 'italic',
              color: 'var(--parchment-dark)',
              fontSize: 13,
              lineHeight: 1.7,
              textAlign: 'center',
            }}>
              等待你的回应…… 点击"返回对话"继续。
            </div>
          </div>

          {/* 浮动"回到最新" */}
          {!atBottom && (
            <button
              onClick={() => { scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }); }}
              className="scroll-to-latest"
            >
              ▼ 跳至最新
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function AdventureScene() {
  const [freeInput, setFreeInput] = React.useState('');
  const [showHistory, setShowHistory] = React.useState(false);

  if (showHistory) {
    return <DialogueHistoryView onBack={() => setShowHistory(false)} />;
  }

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
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10, borderColor: 'rgba(127,232,248,.5)', color: 'var(--arcane-light)' }} onClick={() => setShowHistory(true)}>☰ 对话历史</button>
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
