// ════════════════════════════════════════════════════════════
// Adventure Scene — 深度重构 · 电影剧本式对话
// 布局：舞台横幅 → 核心叙事流（剧院风） → 意图编辑器
// ════════════════════════════════════════════════════════════

const ADV_PARTY = [
  { name: '艾琳·晨光', race: '半精灵', cls: 'paladin', classLabel: '圣武士', level: 5, hp_cur: 42, hp_max: 48, ac: 18, init: 2, isPlayer: true, slots: { '1st': [3, 4], '2nd': [1, 2] } },
  { name: '索恩·石拳', race: '山地矮人', cls: 'fighter', classLabel: '战士', level: 5, hp_cur: 38, hp_max: 52, ac: 19, init: 1 },
  { name: '薇拉·月语', race: '高等精灵', cls: 'wizard', classLabel: '法师', level: 5, hp_cur: 14, hp_max: 28, ac: 13, init: 4, slots: { '1st': [2, 4], '2nd': [2, 3], '3rd': [1, 2] }, conditions: ['虚弱'] },
  { name: '凯瑞丝', race: '轻足半身人', cls: 'rogue', classLabel: '游荡者', level: 5, hp_cur: 32, hp_max: 36, ac: 15, init: 5 },
];

const NPC_DB = {
  hooded: { name: '兜帽老者', alias: '无名议会信使', cls: 'warlock', rel: 'unknown', clue: '袖口有螺旋烙印' },
  barkeep:{ name: '格雷森', alias: '低语者酒馆老板', cls: 'fighter', rel: 'friendly', clue: '听过徽章传闻' },
};

const ADV_NARRATIVE = [
  {
    kind: 'scene',
    title: '低语者酒馆 · 黄昏',
    mood: '炉火摇曳 · 低语潺潺 · 鹿角烛台在梁木间投下长影',
  },
  {
    kind: 'narration',
    content: '你推开酒馆沉重的橡木门。火光与笑语扑面而来，空气里浮着烤野猪与陈年麦酒的气息。一名戴着兜帽的老者独坐于角落的阴影里，他的眼睛在兜帽下闪着古怪的蓝光——那是你在任何人类身上都未曾见过的颜色。',
  },
  {
    kind: 'narration',
    content: '他用沙哑的嗓音，极轻地，念出了你的真名。',
  },
  {
    kind: 'action',
    actor: { name: '艾琳·晨光', cls: 'paladin', isPlayer: true },
    intent: '交谈 · 警觉',
    content: '我走向他，右手按在剑柄上，礼貌但警觉地询问：「你是谁？你怎么会知道我的名字？」',
  },
  {
    kind: 'check',
    skill: '洞察',
    ability: 'wis',
    dc: 14,
    d20: 17,
    mod: 3,
    total: 20,
    success: true,
    outcome: '你敏锐地察觉——他袖口下有一道螺旋形的刻痕，那是"无名议会"的烙印。',
  },
  {
    kind: 'dialogue',
    speaker: { name: '兜帽老者', cls: 'warlock' },
    content: '「因为，年轻的圣武士，我等你已经七年了。」他缓缓摊开手掌，一枚银色徽章静静躺在掌心，徽章表面浮现出淡蓝色的符文。',
  },
  {
    kind: 'dialogue',
    speaker: { name: '索恩·石拳', cls: 'fighter', isAlly: true },
    tone: '低声 · 警惕',
    content: '（低声）「小心点，朋友。议会的人从来不会无故现身。」他的手已悄悄摸向腰间的战斧。',
  },
];

function AdventureScene() {
  const [input, setInput] = React.useState('我接过那枚徽章，仔细查看上面的纹路。');
  const [intent, setIntent] = React.useState('investigate');
  const [showParty, setShowParty] = React.useState(true);
  const [showNpc, setShowNpc] = React.useState(true);

  return (
    <div style={{ position: 'relative', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ══ 顶部：章节横幅 ══ */}
      <AdvChapterBanner />

      {/* ══ 舞台横幅 —— 当前场景的空间感 ══ */}
      <AdvSceneStage />

      {/* ══ 三栏主体 ══ */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: `${showParty ? '230px ' : '32px '}1fr ${showNpc ? '240px' : '32px'}`, overflow: 'hidden', transition: 'grid-template-columns .3s' }}>
        {/* 左：队伍 */}
        <aside style={{
          borderRight: '1px solid rgba(212,168,71,.25)',
          overflow: 'hidden',
          background: 'linear-gradient(180deg, rgba(10,6,2,.45), rgba(10,6,2,.15))',
          position: 'relative',
          display: 'flex', flexDirection: 'column',
        }}>
          <CollapseTab side="left" open={showParty} onClick={() => setShowParty(!showParty)} label="队伍" />
          {showParty && (
            <div style={{ padding: '14px 12px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, flex: 1 }}>
              <div className="eyebrow" style={{ padding: '0 6px 4px', textAlign: 'center' }}>※ 冒险队伍 ※</div>
              {ADV_PARTY.map((c, i) => <CharCard key={i} char={c} active={i === 0} />)}
              <div style={{ marginTop: 'auto', padding: 10, textAlign: 'center', fontSize: 11, fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)', lineHeight: 1.6, opacity: .7 }}>
                "当月光洒在剑刃上——"
              </div>
            </div>
          )}
        </aside>

        {/* 中：叙事流（核心） */}
        <main style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
          <div className="narrative-stream" style={{
            flex: 1, overflowY: 'auto',
            padding: '22px 44px 30px',
            display: 'flex', flexDirection: 'column', gap: 22,
          }}>
            {ADV_NARRATIVE.map((entry, i) => <NarrativeEntry key={i} entry={entry} index={i} />)}
            <DmThinking />
          </div>

          {/* ══ 意图编辑器 ══ */}
          <AdvIntentEditor input={input} setInput={setInput} intent={intent} setIntent={setIntent} />
        </main>

        {/* 右：NPC & 线索 */}
        <aside style={{
          borderLeft: '1px solid rgba(212,168,71,.25)',
          overflow: 'hidden',
          background: 'linear-gradient(180deg, rgba(10,6,2,.45), rgba(10,6,2,.15))',
          display: 'flex', flexDirection: 'column',
        }}>
          <CollapseTab side="right" open={showNpc} onClick={() => setShowNpc(!showNpc)} label="卷宗" />
          {showNpc && <AdvCodex />}
        </aside>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// 顶部章节横幅
// ════════════════════════════════════════════════════════════
function AdvChapterBanner() {
  return (
    <header style={{
      position: 'relative',
      padding: '14px 24px',
      borderBottom: '1px solid rgba(212,168,71,.3)',
      background: 'linear-gradient(180deg, rgba(16,10,4,.95), rgba(10,6,2,.6))',
      display: 'grid',
      gridTemplateColumns: '1fr auto 1fr',
      alignItems: 'center',
      zIndex: 3,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button className="btn-ghost" style={{ padding: '6px 14px', fontSize: 11 }}>◄ 主页</button>
        <span className="tag tag-gold" style={{ fontSize: 10 }}>自动存档 ● 2分钟前</span>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div className="eyebrow" style={{ fontSize: 10 }}>✦ 战役 ✦</div>
        <div className="display-title" style={{ fontSize: 20, letterSpacing: '.15em', marginTop: 2 }}>银谷村的阴影</div>
        <div style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', fontSize: 12, color: 'var(--parchment-dark)', marginTop: 3, letterSpacing: '.08em' }}>
          — 第三章 · 低语者酒馆 —
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <button className="btn-ghost" style={{ padding: '6px 10px', fontSize: 10 }}>✧ 备法</button>
        <button className="btn-ghost" style={{ padding: '6px 10px', fontSize: 10 }}>☾ 休息</button>
        <button className="btn-ghost" style={{ padding: '6px 10px', fontSize: 10 }}>☰ 编年史</button>
      </div>
    </header>
  );
}

// ════════════════════════════════════════════════════════════
// 舞台横幅 —— 当前场景氛围（窄条，强气氛）
// ════════════════════════════════════════════════════════════
function AdvSceneStage() {
  return (
    <div style={{
      position: 'relative',
      padding: '10px 36px',
      background:
        'linear-gradient(90deg, rgba(138,60,20,.25) 0%, rgba(20,12,6,.7) 30%, rgba(20,12,6,.7) 70%, rgba(138,60,20,.25) 100%)',
      borderBottom: '1px solid rgba(212,168,71,.2)',
      overflow: 'hidden',
    }}>
      {/* 远景图层 — 纯 CSS 剪影 */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background:
          'radial-gradient(ellipse at 15% 100%, rgba(212,120,40,.25) 0%, transparent 40%),' +
          'radial-gradient(ellipse at 85% 100%, rgba(180,90,40,.2) 0%, transparent 40%)',
        opacity: .6,
      }} />
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ fontSize: 22, filter: 'drop-shadow(0 0 6px rgba(240,184,64,.6))' }}>🜂</span>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, color: 'var(--amber)', letterSpacing: '.15em' }}>低语者酒馆</div>
            <div style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', fontSize: 11, color: 'var(--parchment-dark)', marginTop: 2 }}>
              炉火摇曳 · 鹿角烛台 · 陈年麦酒的气息
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 16, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--parchment-dark)' }}>
          <MoodStat icon="☀" label="时辰" value="黄昏" />
          <MoodStat icon="☁" label="天气" value="阴" />
          <MoodStat icon="♪" label="气氛" value="紧张" warn />
          <MoodStat icon="⚠" label="危险" value="潜在" warn />
        </div>
      </div>
    </div>
  );
}

function MoodStat({ icon, label, value, warn }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ color: warn ? 'var(--ember)' : 'var(--amber)' }}>{icon}</span>
      <span style={{ opacity: .6 }}>{label}</span>
      <span style={{ color: warn ? 'var(--blood-light)' : 'var(--parchment)', fontWeight: 600 }}>{value}</span>
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// 叙事条目 —— 五种类型：scene / narration / action / check / dialogue
// ════════════════════════════════════════════════════════════
function NarrativeEntry({ entry, index }) {
  if (entry.kind === 'scene') return <SceneHeader entry={entry} />;
  if (entry.kind === 'narration') return <Narration content={entry.content} index={index} />;
  if (entry.kind === 'action') return <PlayerAction entry={entry} />;
  if (entry.kind === 'check') return <CheckRecord entry={entry} />;
  if (entry.kind === 'dialogue') return <Dialogue entry={entry} />;
  return null;
}

// ── 场景标题（大分隔） ─────────────────────────────────
function SceneHeader({ entry }) {
  return (
    <div style={{ textAlign: 'center', padding: '8px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'center' }}>
        <span style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, var(--amber) 60%, var(--amber))', opacity: .5, maxWidth: 180 }} />
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 13, color: 'var(--amber)', letterSpacing: '.3em' }}>✦ {entry.title} ✦</span>
        <span style={{ flex: 1, height: 1, background: 'linear-gradient(-90deg, transparent, var(--amber) 60%, var(--amber))', opacity: .5, maxWidth: 180 }} />
      </div>
      <div style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', fontSize: 13, color: 'var(--parchment-dark)', marginTop: 6, letterSpacing: '.05em' }}>
        ~ {entry.mood} ~
      </div>
    </div>
  );
}

// ── DM 旁白 —— 全宽、无气泡，像电影字幕 ───────────────
function Narration({ content, index }) {
  const isFirst = index === 1;
  return (
    <div style={{ position: 'relative', padding: '4px 0 4px 28px', maxWidth: 760, margin: '0 auto', width: '100%' }}>
      {/* 左侧金色长边线 */}
      <span style={{
        position: 'absolute', left: 0, top: 4, bottom: 4, width: 2,
        background: 'linear-gradient(180deg, transparent, var(--amber) 20%, var(--amber) 80%, transparent)',
        opacity: .5,
      }} />
      {/* 左上角 小首字母花饰（仅首段） */}
      {isFirst && (
        <span style={{
          position: 'absolute', left: -6, top: -4,
          fontFamily: 'var(--font-display)', fontSize: 48, lineHeight: 1,
          color: 'var(--amber)', textShadow: '0 0 14px rgba(240,184,64,.5)',
          background: 'var(--gold-gradient)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
        }}>
        </span>
      )}
      <p style={{
        fontFamily: 'var(--font-script)',
        fontSize: 16,
        lineHeight: 1.85,
        color: 'var(--parchment)',
        margin: 0,
        letterSpacing: '.01em',
        textIndent: isFirst ? '1.4em' : 0,
      }}>
        {content}
      </p>
    </div>
  );
}

// ── 玩家行动 —— 带意图标签 + 右侧对齐 ─────────────────
function PlayerAction({ entry }) {
  return (
    <div style={{ maxWidth: 760, margin: '0 auto', width: '100%', display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
      <div style={{ maxWidth: '82%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, justifyContent: 'flex-end' }}>
          <span className="eyebrow" style={{ fontSize: 10, color: 'var(--sapphire-light)' }}>{entry.actor.name}</span>
          <span className="tag tag-blue" style={{ fontSize: 9 }}>{entry.intent}</span>
        </div>
        <div className="bubble bubble-player" style={{ fontSize: 14, lineHeight: 1.7 }}>
          {entry.content}
        </div>
      </div>
      <Portrait cls={entry.actor.cls} size="sm" />
    </div>
  );
}

// ── 检定记录 —— 精致卡片 ────────────────────────────
function CheckRecord({ entry }) {
  return (
    <div style={{ maxWidth: 620, margin: '0 auto', width: '100%' }}>
      <div style={{
        position: 'relative',
        padding: '12px 18px',
        background: 'linear-gradient(135deg, rgba(138,79,212,.12) 0%, rgba(60,30,100,.22) 100%)',
        border: '1px solid rgba(138,79,212,.4)',
        borderRadius: 8,
        boxShadow: '0 0 22px -6px rgba(138,79,212,.25), inset 0 0 22px -10px rgba(138,79,212,.2)',
      }}>
        {/* 左侧宝石条 */}
        <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: 'linear-gradient(180deg, var(--amethyst-light), var(--amethyst))', borderRadius: '8px 0 0 8px' }} />

        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 14, alignItems: 'center' }}>
          {/* 骰子面 */}
          <div style={{
            width: 48, height: 48,
            background: 'radial-gradient(circle at 30% 30%, #c8a0ff, #5a2a9a 70%)',
            borderRadius: 8, transform: 'rotate(-6deg)',
            display: 'grid', placeItems: 'center',
            fontFamily: 'var(--font-display)',
            fontSize: 18,
            fontWeight: 700,
            color: '#fff',
            boxShadow: '0 4px 14px -2px rgba(138,79,212,.5), inset 0 -3px 6px rgba(0,0,0,.3), inset 0 2px 3px rgba(255,255,255,.2)',
          }}>
            {entry.d20}
          </div>
          {/* 描述 */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontSize: 14, color: 'var(--amethyst-light)', fontWeight: 700, letterSpacing: '.06em' }}>
                {entry.skill}检定
              </span>
              <span className="tag tag-magic" style={{ fontSize: 9 }}>DC {entry.dc}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--parchment-dark)' }}>
                d20 = <b style={{ color: 'var(--amethyst-light)' }}>{entry.d20}</b> {entry.mod >= 0 ? '+' : ''}{entry.mod} = <b style={{ color: 'var(--amber)' }}>{entry.total}</b>
              </span>
            </div>
            <div style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', fontSize: 13, color: 'var(--parchment)', marginTop: 6, lineHeight: 1.6 }}>
              {entry.outcome}
            </div>
          </div>
          {/* 结果徽章 */}
          <div style={{
            fontFamily: 'var(--font-display)',
            fontSize: 12,
            letterSpacing: '.15em',
            padding: '6px 12px',
            borderRadius: 20,
            color: entry.success ? 'var(--emerald-light)' : 'var(--blood-light)',
            border: `1px solid ${entry.success ? 'var(--emerald)' : 'var(--blood)'}`,
            background: entry.success ? 'rgba(58,122,72,.18)' : 'rgba(138,26,26,.18)',
            boxShadow: `0 0 12px -4px ${entry.success ? 'rgba(95,168,120,.5)' : 'rgba(200,56,56,.5)'}`,
            whiteSpace: 'nowrap',
          }}>
            {entry.success ? '✓ 成功' : '✗ 失败'}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 角色对话（NPC 或队友） ───────────────────────────
function Dialogue({ entry }) {
  const isAlly = entry.speaker.isAlly;
  return (
    <div style={{ maxWidth: 760, margin: '0 auto', width: '100%', display: 'flex', gap: 14 }}>
      <Portrait cls={entry.speaker.cls} size="sm" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span className="eyebrow" style={{ fontSize: 10, color: isAlly ? 'var(--emerald-light)' : 'var(--amber)' }}>
            {isAlly ? '◈' : '❖'} {entry.speaker.name}
          </span>
          {entry.tone && <span className="tag tag-info" style={{ fontSize: 9 }}>{entry.tone}</span>}
          <span style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${isAlly ? 'var(--emerald-light)' : 'var(--amber)'}, transparent)`, opacity: .3 }} />
        </div>
        <div className={`bubble ${isAlly ? 'bubble-ally' : 'bubble-dm'}`} style={{ fontSize: 14, lineHeight: 1.75 }}>
          {entry.content}
        </div>
      </div>
    </div>
  );
}

// ── DM 思考中 ────────────────────────────────────────
function DmThinking() {
  return (
    <div style={{ maxWidth: 760, margin: '0 auto', width: '100%', display: 'flex', gap: 12, alignItems: 'center', opacity: .65, padding: '4px 0' }}>
      <Portrait cls="dm" size="sm" />
      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <span style={{ fontFamily: 'var(--font-script)', fontStyle: 'italic', fontSize: 13, color: 'var(--parchment-dark)' }}>
          地下城主正在编织故事
        </span>
        <span style={{ display: 'inline-flex', gap: 3, marginLeft: 6 }}>
          <DotAnim d={0} />
          <DotAnim d={.15} />
          <DotAnim d={.3} />
        </span>
      </div>
    </div>
  );
}
function DotAnim({ d }) {
  return <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--amber)', animation: `pulse 1.4s ease-in-out ${d}s infinite` }} />;
}

// ════════════════════════════════════════════════════════════
// 意图编辑器 —— 底部三段：意图 tabs + 文本 + 快捷
// ════════════════════════════════════════════════════════════
const INTENTS = [
  { k: 'speak',       label: '✎ 说话/对话',  color: 'var(--sapphire-light)', hint: '「...」告诉对方你想说的内容' },
  { k: 'investigate', label: '☉ 调查/感知',  color: 'var(--amethyst-light)', hint: '描述你想观察或研究什么' },
  { k: 'action',      label: '⚔ 行动/战斗',  color: 'var(--blood-light)',    hint: '直接描述攻击、推开、跳跃等' },
  { k: 'stealth',     label: '❋ 潜行/隐秘',  color: 'var(--emerald-light)',  hint: '你小心翼翼，不被发现地...' },
  { k: 'magic',       label: '✦ 施法',       color: 'var(--amethyst-light)', hint: '指定法术和目标' },
  { k: 'rest',        label: '☾ 休息/等待',  color: 'var(--parchment-dark)', hint: '让时间流逝或恢复体力' },
];

function AdvIntentEditor({ input, setInput, intent, setIntent }) {
  const cur = INTENTS.find(i => i.k === intent) || INTENTS[0];
  return (
    <div style={{
      borderTop: '1px solid rgba(212,168,71,.3)',
      background: 'linear-gradient(180deg, rgba(18,10,6,.4), rgba(10,6,2,.85))',
      padding: '10px 36px 14px',
      position: 'relative',
    }}>
      {/* 顶部细金条 */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 2, background: 'linear-gradient(90deg, transparent, var(--amber), transparent)', opacity: .5 }} />

      {/* 意图 tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
        {INTENTS.map(it => (
          <button key={it.k} onClick={() => setIntent(it.k)} style={{
            padding: '5px 14px',
            background: intent === it.k ? `linear-gradient(180deg, ${it.color}33, transparent)` : 'transparent',
            border: `1px solid ${intent === it.k ? it.color : 'var(--bark-light)'}`,
            color: intent === it.k ? it.color : 'var(--parchment-dark)',
            fontFamily: 'var(--font-heading)',
            fontSize: 11,
            letterSpacing: '.08em',
            cursor: 'pointer',
            borderRadius: 4,
            transition: 'var(--transition)',
            fontWeight: intent === it.k ? 600 : 400,
            boxShadow: intent === it.k ? `0 0 12px -4px ${it.color}` : 'none',
          }}>
            {it.label}
          </button>
        ))}
      </div>

      {/* 快捷行动建议 */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
        <span style={{ fontSize: 10, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', alignSelf: 'center', letterSpacing: '.1em' }}>建议 »</span>
        {['审视徽章', '询问任务细节', '拒绝并离开', '要求酬劳', '与队友低声商议'].map((a, i) => (
          <button key={i} className="skill-chip">{a}</button>
        ))}
      </div>

      {/* 输入卷轴 */}
      <div className="scroll-input" style={{ alignItems: 'center' }}>
        <span style={{
          padding: '6px 12px',
          fontFamily: 'var(--font-heading)',
          fontSize: 11,
          letterSpacing: '.1em',
          color: cur.color,
          borderRight: '1px solid var(--bark-light)',
          marginRight: 4,
          whiteSpace: 'nowrap',
        }}>
          {cur.label.split(' ')[0]}
        </span>
        <textarea
          rows={1}
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={cur.hint}
        />
        <button className="skill-chip" style={{ padding: '6px 12px', height: 32, alignSelf: 'center' }} title="掷个骰子">🎲 骰</button>
        <button className="send" title="发送">➤</button>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--parchment-dark)' }}>
        <span>↵ 发送 · Shift+↵ 换行</span>
        <span>字数 {input.length} / 500</span>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// 右侧卷宗：当前场景 NPC + 线索 + 目标
// ════════════════════════════════════════════════════════════
function AdvCodex() {
  return (
    <div style={{ padding: '14px 12px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
      <div className="eyebrow" style={{ textAlign: 'center' }}>❖ 本幕卷宗 ❖</div>

      {/* 当前NPC */}
      <div>
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: 11, color: 'var(--amber)', letterSpacing: '.15em', marginBottom: 6, textTransform: 'uppercase' }}>在场角色</div>
        <NpcCard name="兜帽老者" sub="无名议会信使？" cls="warlock" rel="unknown" />
        <NpcCard name="格雷森" sub="酒馆老板" cls="fighter" rel="friendly" />
      </div>

      {/* 线索 */}
      <div>
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: 11, color: 'var(--amber)', letterSpacing: '.15em', marginBottom: 6, textTransform: 'uppercase' }}>线索 3</div>
        <ClueItem glyph="⌁" text="兜帽老者袖口有螺旋烙印" isNew />
        <ClueItem glyph="❖" text="银色徽章上浮现淡蓝符文" />
        <ClueItem glyph="✧" text="议会信使称等待了「七年」" />
      </div>

      {/* 当前目标 */}
      <div>
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: 11, color: 'var(--amber)', letterSpacing: '.15em', marginBottom: 6, textTransform: 'uppercase' }}>当前目标</div>
        <div style={{ padding: '10px 12px', background: 'linear-gradient(180deg, rgba(138,26,26,.12), rgba(74,10,10,.04))', border: '1px solid rgba(200,56,56,.35)', borderRadius: 6, fontSize: 12 }}>
          <div style={{ color: 'var(--blood-light)', fontWeight: 600, marginBottom: 4 }}>◆ 弄清老者来意</div>
          <div style={{ color: 'var(--parchment-dark)', fontStyle: 'italic', lineHeight: 1.55, fontSize: 11 }}>
            他为何知你真名？徽章有何意义？
          </div>
        </div>
      </div>

      {/* 同队友秘密频道 */}
      <button className="btn-ghost" style={{ fontSize: 10, padding: '6px 10px', marginTop: 4 }}>⚑ 队伍密语</button>
    </div>
  );
}

function NpcCard({ name, sub, cls, rel }) {
  const relColor = { friendly: 'var(--emerald-light)', unknown: 'var(--parchment-dark)', hostile: 'var(--blood-light)' }[rel];
  const relLabel = { friendly: '友善', unknown: '未知', hostile: '敌对' }[rel];
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '8px 10px', marginBottom: 6,
      background: 'linear-gradient(180deg, rgba(26,18,10,.5), rgba(10,6,2,.3))',
      border: '1px solid rgba(90,60,34,.5)',
      borderRadius: 6,
      cursor: 'pointer',
      transition: 'var(--transition)',
    }}>
      <Portrait cls={cls} size="sm" style={{ width: 32, height: 32 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: 12, color: 'var(--parchment)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</div>
        <div style={{ fontSize: 10, color: 'var(--parchment-dark)', fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sub}</div>
      </div>
      <span style={{ fontSize: 9, color: relColor, fontFamily: 'var(--font-mono)', letterSpacing: '.1em' }}>{relLabel}</span>
    </div>
  );
}

function ClueItem({ glyph, text, isNew }) {
  return (
    <div style={{
      display: 'flex', gap: 8, alignItems: 'flex-start',
      padding: '7px 10px', marginBottom: 4,
      background: isNew ? 'linear-gradient(90deg, rgba(212,168,71,.14), transparent)' : 'transparent',
      border: isNew ? '1px solid rgba(212,168,71,.3)' : '1px solid transparent',
      borderRadius: 4,
      fontSize: 11,
      lineHeight: 1.55,
      color: 'var(--parchment)',
      position: 'relative',
    }}>
      <span style={{ color: isNew ? 'var(--amber)' : 'var(--parchment-dark)', fontSize: 13 }}>{glyph}</span>
      <span style={{ flex: 1, fontStyle: 'italic' }}>{text}</span>
      {isNew && <span style={{ fontSize: 8, color: 'var(--amber)', border: '1px solid var(--amber)', padding: '1px 5px', borderRadius: 8, letterSpacing: '.1em', fontFamily: 'var(--font-mono)' }}>NEW</span>}
    </div>
  );
}

// ════════════════════════════════════════════════════════════
// 可折叠侧栏把手
// ════════════════════════════════════════════════════════════
function CollapseTab({ side, open, onClick, label }) {
  if (open) return (
    <button onClick={onClick} title="收起" style={{
      position: 'absolute', [side === 'left' ? 'right' : 'left']: 4, top: 10,
      width: 20, height: 32, background: 'transparent', border: 'none',
      color: 'var(--parchment-dark)', cursor: 'pointer', fontSize: 14, zIndex: 2,
    }}>
      {side === 'left' ? '◄' : '►'}
    </button>
  );
  return (
    <button onClick={onClick} style={{
      width: '100%', height: '100%', background: 'transparent', border: 'none',
      color: 'var(--parchment-dark)', cursor: 'pointer',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8,
      fontFamily: 'var(--font-heading)', fontSize: 11, letterSpacing: '.25em',
      writingMode: 'vertical-rl',
    }}>
      {side === 'left' ? '► ' : '◄ '}{label}
    </button>
  );
}

window.AdventureScene = AdventureScene;
