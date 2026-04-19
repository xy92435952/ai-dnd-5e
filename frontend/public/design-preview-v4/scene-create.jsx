// ════════════════════════════════════════════════════════════
// CreateScene — 6-step character creation wizard
// 视觉重构：羊皮纸 + 金饰 + 纹章肖像
// ════════════════════════════════════════════════════════════

const RACES = [
  { key: 'human',    zh: '人类',   speed: 30, size: '中型', bonus: { str:1,dex:1,con:1,int:1,wis:1,cha:1 }, desc: '适应力强的全能者，各项属性均衡提升。' },
  { key: 'elf',      zh: '精灵',   speed: 30, size: '中型', bonus: { dex:2, int:1 }, desc: '优雅、长寿，黑暗视觉与对魅惑的韧性。' },
  { key: 'dwarf',    zh: '矮人',   speed: 25, size: '中型', bonus: { con:2, str:2 }, desc: '坚韧的山地工匠，对毒素有天然抗性。' },
  { key: 'halfling', zh: '半身人', speed: 25, size: '小型', bonus: { dex:2, cha:1 }, desc: '灵巧而幸运，失利的重骰者。' },
  { key: 'half-elf', zh: '半精灵', speed: 30, size: '中型', bonus: { cha:2 }, desc: '双重血脉的外交者，魅力天赋出众。' },
  { key: 'dragonborn',zh: '龙裔',  speed: 30, size: '中型', bonus: { str:2, cha:1 }, desc: '龙血后裔，可喷吐元素之息。' },
  { key: 'tiefling', zh: '提夫林', speed: 30, size: '中型', bonus: { cha:2, int:1 }, desc: '魔裔血统，天生抗火且具备秘术。' },
  { key: 'gnome',    zh: '侏儒',   speed: 25, size: '小型', bonus: { int:2, con:1 }, desc: '好奇的发明家，智力敏锐。' },
];

const CLASSES = [
  { key: 'fighter',   zh: '战士',     hd: 10, prim: '力量/敏捷', save: ['str','con'], skills: 2, caster: false, armor: '全部', desc: '战阵中屹立不倒的钢铁意志' },
  { key: 'paladin',   zh: '圣武士',   hd: 10, prim: '力量/魅力', save: ['wis','cha'], skills: 2, caster: true,  armor: '全部 + 盾', desc: '誓言所铸的神圣战士', fightingStyle: true },
  { key: 'ranger',    zh: '游侠',     hd: 10, prim: '敏捷/感知', save: ['str','dex'], skills: 3, caster: true,  armor: '轻甲/中甲 + 盾', desc: '荒野的守望与追踪者', fightingStyle: true },
  { key: 'barbarian', zh: '蛮战士',   hd: 12, prim: '力量',       save: ['str','con'], skills: 2, caster: false, armor: '轻甲/中甲 + 盾', desc: '狂暴怒火的原始力量' },
  { key: 'rogue',     zh: '游荡者',   hd: 8,  prim: '敏捷',       save: ['dex','int'], skills: 4, caster: false, armor: '轻甲', desc: '阴影之间的敏捷刺客' },
  { key: 'monk',      zh: '武僧',     hd: 8,  prim: '敏捷/感知', save: ['str','dex'], skills: 2, caster: false, armor: '无', desc: '身体即武器，修行成道' },
  { key: 'cleric',    zh: '牧师',     hd: 8,  prim: '感知',       save: ['wis','cha'], skills: 2, caster: true,  armor: '轻甲/中甲 + 盾', desc: '神祇的仆从，神圣的治愈者' },
  { key: 'druid',     zh: '德鲁伊',   hd: 8,  prim: '感知',       save: ['int','wis'], skills: 2, caster: true,  armor: '轻甲/中甲（非金属）', desc: '自然的守护者与变形者' },
  { key: 'bard',      zh: '吟游诗人', hd: 8,  prim: '魅力',       save: ['dex','cha'], skills: 3, caster: true,  armor: '轻甲', desc: '用乐符编织魔法的艺人' },
  { key: 'warlock',   zh: '契约师',   hd: 8,  prim: '魅力',       save: ['wis','cha'], skills: 2, caster: true,  armor: '轻甲', desc: '与异界存在缔结契约' },
  { key: 'sorcerer',  zh: '术士',     hd: 6,  prim: '魅力',       save: ['con','cha'], skills: 2, caster: true,  armor: '无', desc: '血脉之中流淌的魔力' },
  { key: 'wizard',    zh: '法师',     hd: 6,  prim: '智力',       save: ['int','wis'], skills: 2, caster: true,  armor: '无', desc: '奥术研习者，操纵纯粹的魔法' },
];

const SUBCLASSES = {
  paladin:  ['奉献圣契', '古迹守护', '复仇誓约'],
  fighter:  ['战斗大师', '鬼斗士', '秘能骑士'],
  wizard:   ['塑能系', '咒法系', '祀法系', '预言系'],
  rogue:    ['秘术诡术师', '刺客', '秘士'],
  cleric:   ['生命领域', '光明领域', '战争领域'],
  barbarian:['狂战士之路', '图腾战士'],
};

const ALIGNMENTS = ['守序善良','中立善良','混乱善良','守序中立','绝对中立','混乱中立','守序邪恶','中立邪恶','混乱邪恶'];
const BACKGROUNDS = ['侍僧','艺人','民间英雄','弄臣','佣兵','贵族','流浪者','赛场斗士','圣职者','学者','罪犯','水手','骑士','士兵','江湖郎中'];
const ABILITY_KEYS = ['str','dex','con','int','wis','cha'];
const ABILITY_ZH = { str:'力量', dex:'敏捷', con:'体质', int:'智力', wis:'感知', cha:'魅力' };

const SKILLS = [
  { k: '运动', ab: 'str' }, { k: '体操', ab: 'dex' }, { k: '巧手', ab: 'dex' }, { k: '隐匿', ab: 'dex' },
  { k: '调查', ab: 'int' }, { k: '奥秘', ab: 'int' }, { k: '历史', ab: 'int' }, { k: '自然', ab: 'int' }, { k: '宗教', ab: 'int' },
  { k: '察觉', ab: 'wis' }, { k: '洞察', ab: 'wis' }, { k: '医疗', ab: 'wis' }, { k: '驯兽', ab: 'wis' }, { k: '求生', ab: 'wis' },
  { k: '说服', ab: 'cha' }, { k: '欺瞒', ab: 'cha' }, { k: '威吓', ab: 'cha' }, { k: '表演', ab: 'cha' },
];

const FIGHTING_STYLES = [
  { k: 'defense',    zh: '防御',     desc: '穿着护甲时 AC +1' },
  { k: 'dueling',    zh: '决斗',     desc: '单手武器且副手空时 伤害 +2' },
  { k: 'great',      zh: '巨武',     desc: '双手武器重骰 1/2 的伤害骰' },
  { k: 'archery',    zh: '精擅射艺', desc: '远程武器攻击检定 +2' },
  { k: 'protection', zh: '守护',     desc: '举盾时，可施反应令敌方劣势' },
];

const CANTRIPS = {
  wizard:   ['火焰箭', '魔法飞弹', '奥秘之眼', '冻射', '魔手', '次级幻象', '电爪', '毒喷'],
  sorcerer: ['火焰箭', '电爪', '毒喷', '魔法飞弹', '寒冰刃', '次级幻象'],
  cleric:   ['神圣之火', '诱导', '修复', '治愈之手', '光亮', '灵光矢'],
  druid:    ['修复', '毒喷', '荆棘鞭', '塑造水流', '构造火焰'],
  bard:     ['次级幻象', '讯息', '嘲弄之语', '塑造水流'],
  warlock:  ['蛊惑之触', '奥秘脉冲', '次级幻象', '毒喷'],
};
const SPELLS = {
  wizard:   ['魔法护盾', '燃烧之手', '油滑术', '魔法飞弹', '睡眠术', '虚化侍者', '侦测魔法', '识破伪装'],
  sorcerer: ['魔法护盾', '燃烧之手', '魔法飞弹', '致残射线', '侦测魔法', '迷乱人心'],
  cleric:   ['祝福', '治疗术', '防护法术', '圣言', '侦测邪恶与善良', '神圣惩击'],
  druid:    ['缠绕术', '治疗术', '蛊惑野兽', '侦测魔法', '妖火', '变形术'],
  bard:     ['嘲弄之语', '治疗术', '睡眠术', '蛊惑人类', '迷乱人心', '隐形变'],
  warlock:  ['地狱责罚', '蛊惑人类', '魔法护盾', '隐形仆役'],
  paladin:  ['祝福', '神佑', '恩典庇护', '圣言'],
  ranger:   ['猎者印记', '诅咒伤害', '幽静', '治愈之语'],
};

function modifier(s) { return Math.floor((s - 10) / 2); }
function modStr(n)   { return n >= 0 ? `+${n}` : `${n}`; }

// ══════════════════════════════════════════════
function CreateScene() {
  const [step, setStep] = React.useState(1);
  const [form, setForm] = React.useState({
    name: '艾琳·晨光', race: 'half-elf', cls: 'paladin', subclass: '',
    level: 3, alignment: '守序善良', background: '贵族',
    multiEnabled: false, multiCls: '',
  });
  const [scoreMethod, setScoreMethod] = React.useState('pointbuy');
  const POINTS = 27;
  const COSTS = { 8:0, 9:1, 10:2, 11:3, 12:4, 13:5, 14:7, 15:9 };
  const ARRAY = [15, 14, 13, 12, 10, 8];
  const [scores, setScores] = React.useState({ str:13, dex:10, con:14, int:8, wis:12, cha:15 });
  const [assigned, setAssigned] = React.useState({});
  const [skills, setSkills] = React.useState([]);
  const [cantrips, setCantrips] = React.useState([]);
  const [spellsSel, setSpellsSel] = React.useState([]);
  const [fStyle, setFStyle] = React.useState('');
  const [equipChoice, setEquipChoice] = React.useState(0);

  const cls = CLASSES.find(c => c.key === form.cls);
  const race = RACES.find(r => r.key === form.race);
  const isCaster = cls?.caster;
  const hasSubclass = SUBCLASSES[form.cls] && form.level >= (form.cls === 'wizard' ? 2 : 3);
  const hasFStyle = cls?.fightingStyle && form.level >= 1;
  const needsASI = form.level >= 4;

  const STEPS = ['基础信息', '能力值', '技能', '装备'];
  if (isCaster) STEPS.push('法术');
  if (needsASI) STEPS.push('专长');
  STEPS.push('队伍');
  const partyStep = STEPS.length;

  const racialBonus = race?.bonus || {};
  const baseScores = scoreMethod === 'pointbuy' ? scores :
    Object.fromEntries(ABILITY_KEYS.map(k => [k, assigned[k] !== undefined ? ARRAY[assigned[k]] : 8]));
  const finalScores = Object.fromEntries(ABILITY_KEYS.map(k => [k, (baseScores[k] || 8) + (racialBonus[k] || 0)]));
  const pointsSpent = Object.values(scores).reduce((s, v) => s + (COSTS[v] || 0), 0);
  const pointsLeft = POINTS - pointsSpent;

  const cantripCount = isCaster ? 3 : 0;
  const spellCount = isCaster && !['paladin','ranger'].includes(form.cls) ? 4 : (['paladin','ranger'].includes(form.cls) && form.level >= 2 ? 2 : 0);

  // ─── Step Indicator ───────────────────────────
  const StepDots = () => (
    <div className="create-steps">
      {STEPS.map((lbl, i) => {
        const n = i + 1;
        const done = step > n, cur = step === n;
        return (
          <React.Fragment key={i}>
            <div className={`step-dot ${done ? 'done' : cur ? 'cur' : ''}`}>
              <div className="dot">{done ? '✓' : n}</div>
              <div className="lbl">{lbl}</div>
            </div>
            {i < STEPS.length - 1 && <div className={`step-line ${done ? 'done' : ''}`} />}
          </React.Fragment>
        );
      })}
    </div>
  );

  const Field = ({ label, hint, children }) => (
    <div className="create-field">
      <label className="lbl">{label}</label>
      {children}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );

  // ═══ Steps ═══════════════════════════════════
  const renderStep = () => {
    if (step === 1) return <Step1 form={form} setForm={setForm} race={race} cls={cls} hasSubclass={hasSubclass} hasFStyle={hasFStyle} fStyle={fStyle} setFStyle={setFStyle} Field={Field} finalScores={finalScores} />;
    if (step === 2) return <Step2 scoreMethod={scoreMethod} setScoreMethod={setScoreMethod} scores={scores} setScores={setScores} assigned={assigned} setAssigned={setAssigned} racialBonus={racialBonus} finalScores={finalScores} pointsLeft={pointsLeft} POINTS={POINTS} COSTS={COSTS} ARRAY={ARRAY} cls={cls} form={form} />;
    if (step === 3) return <Step3 cls={cls} skills={skills} setSkills={setSkills} />;
    if (step === 4) return <Step4 cls={cls} equipChoice={equipChoice} setEquipChoice={setEquipChoice} Field={Field} />;
    if (step === 5 && isCaster) return <Step5 form={form} cantrips={cantrips} setCantrips={setCantrips} cantripCount={cantripCount} spellsSel={spellsSel} setSpellsSel={setSpellsSel} spellCount={spellCount} />;
    if ((isCaster && step === 6 && needsASI) || (!isCaster && step === 5 && needsASI)) return <Step6 level={form.level} />;
    if (step === partyStep) return <Step7 form={form} cls={cls} race={race} finalScores={finalScores} />;
    return null;
  };

  return (
    <div className="create-scene">
      {/* 顶栏 */}
      <div className="create-header">
        <div>
          <div className="eyebrow">◈ 英雄铸造 · Character Forge ◈</div>
          <div className="display-title" style={{ fontSize: 26, letterSpacing: '.1em', marginTop: 2 }}>书写你的传奇</div>
        </div>
        {/* 右侧·英雄预览卡 */}
        <div className="hero-preview">
          <Portrait cls={form.cls} size="md" />
          <div>
            <div className="name">{form.name || '未命名英雄'}</div>
            <div className="sub">{race?.zh || '—'} · {cls?.zh || '—'} · Lv{form.level}</div>
            <div className="align">{form.alignment}</div>
          </div>
        </div>
      </div>

      <StepDots />

      {/* 主内容·羊皮纸卷轴 */}
      <div className="create-scroll">
        <div className="scroll-ornament top">✦ ❧ ✦</div>
        {renderStep()}
        <div className="scroll-ornament bottom">✦ ❧ ✦</div>
      </div>

      {/* 底部导航 */}
      <div className="create-nav">
        <button className="btn-ghost" disabled={step === 1}
          onClick={() => setStep(s => Math.max(1, s - 1))}>
          ◀ 上一步
        </button>
        <div className="step-counter">{step} / {STEPS.length}</div>
        {step < partyStep ? (
          <button className="btn-gold" onClick={() => setStep(s => Math.min(partyStep, s + 1))}>
            {STEPS[step]} ▶
          </button>
        ) : (
          <button className="btn-gold" style={{ padding: '10px 32px' }}>
            ✦ 开始冒险 ✦
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Step 1: 基础信息 ─────────────────────────
function Step1({ form, setForm, race, cls, hasSubclass, hasFStyle, fStyle, setFStyle, Field, finalScores }) {
  return (
    <div className="step-pane">
      <div className="step-title">✧ 第一章 · 身世与血脉 ✧</div>
      <div className="step-sub">姓名决定传说，血脉决定起点，职业决定道路。</div>

      <Field label="英雄之名">
        <input className="input-fantasy" value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          placeholder="输入你的名字…" />
      </Field>

      {/* 种族 · 大卡片网格 */}
      <div className="create-field">
        <label className="lbl">血脉 · 种族</label>
        <div className="race-grid">
          {RACES.map(r => {
            const sel = form.race === r.key;
            return (
              <div key={r.key} className={`race-card ${sel ? 'sel' : ''}`}
                onClick={() => setForm(f => ({ ...f, race: r.key }))}>
                <div className="race-name">{r.zh}</div>
                <div className="race-meta">{r.size} · 速度 {r.speed}</div>
                <div className="race-bonus">
                  {Object.entries(r.bonus).map(([k, v]) => (
                    <span key={k}>{ABILITY_ZH[k]} +{v}</span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
        {race && <div className="hint"><em>"{race.desc}"</em></div>}
      </div>

      {/* 职业 · 大卡片网格（纹章） */}
      <div className="create-field">
        <label className="lbl">使命 · 职业</label>
        <div className="class-grid">
          {CLASSES.map(c => {
            const sel = form.cls === c.key;
            return (
              <div key={c.key} className={`class-card ${sel ? 'sel' : ''}`}
                onClick={() => setForm(f => ({ ...f, cls: c.key, subclass: '' }))}>
                <Portrait cls={c.key} size="sm" style={{ margin: '0 auto 6px' }} />
                <div className="class-name">{c.zh}</div>
                <div className="class-prim">{c.prim}</div>
              </div>
            );
          })}
        </div>
        {cls && (
          <div className="class-details">
            <div className="row"><span className="tag tag-gold">生命骰 d{cls.hd}</span><span className="tag">{cls.prim}</span><span className="tag">豁免 {cls.save.map(s => ABILITY_ZH[s]).join('/')}</span><span className="tag">可选 {cls.skills} 项技能</span></div>
            <p className="desc"><em>"{cls.desc}"</em></p>
            <div className="row-muted">护甲：{cls.armor}{cls.caster ? ' · 施法职业' : ''}</div>
          </div>
        )}
      </div>

      {/* 子职业 */}
      {hasSubclass && SUBCLASSES[form.cls] && (
        <div className="create-field">
          <label className="lbl">{form.cls === 'wizard' ? '奥术学派' : '专精'}（Lv{form.cls === 'wizard' ? 2 : 3} 解锁）</label>
          <div className="sub-grid">
            {SUBCLASSES[form.cls].map(sc => (
              <div key={sc} className={`sub-chip ${form.subclass === sc ? 'sel' : ''}`}
                onClick={() => setForm(f => ({ ...f, subclass: f.subclass === sc ? '' : sc }))}>
                {sc}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 战斗风格 */}
      {hasFStyle && (
        <div className="create-field">
          <label className="lbl">战斗风格</label>
          <div className="fstyle-grid">
            {FIGHTING_STYLES.map(s => (
              <div key={s.k} className={`fstyle-card ${fStyle === s.k ? 'sel' : ''}`}
                onClick={() => setFStyle(fStyle === s.k ? '' : s.k)}>
                <div className="n">{s.zh}</div>
                <div className="d">{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Field label={`等级（1–20）· 当前 Lv ${form.level}`}>
          <input type="range" min={1} max={20} value={form.level}
            onChange={e => setForm(f => ({ ...f, level: +e.target.value }))}
            className="range-gold" />
        </Field>
        <Field label="阵营">
          <select className="input-fantasy" value={form.alignment}
            onChange={e => setForm(f => ({ ...f, alignment: e.target.value }))}>
            {ALIGNMENTS.map(a => <option key={a}>{a}</option>)}
          </select>
        </Field>
      </div>

      <Field label="背景（决定起始技能与装备倾向）">
        <select className="input-fantasy" value={form.background}
          onChange={e => setForm(f => ({ ...f, background: e.target.value }))}>
          {BACKGROUNDS.map(b => <option key={b}>{b}</option>)}
        </select>
      </Field>
    </div>
  );
}

// ─── Step 2: 能力值 ───────────────────────────
function Step2({ scoreMethod, setScoreMethod, scores, setScores, assigned, setAssigned, racialBonus, finalScores, pointsLeft, POINTS, COSTS, ARRAY, cls, form }) {
  const adj = (k, d) => {
    const cur = scores[k], next = cur + d;
    if (next < 8 || next > 15) return;
    if (d > 0 && (COSTS[next] - COSTS[cur]) > pointsLeft) return;
    setScores(s => ({ ...s, [k]: next }));
  };
  const assign = (k, idx) => {
    if (Object.entries(assigned).some(([a, i]) => a !== k && i === idx)) return;
    setAssigned(p => ({ ...p, [k]: idx }));
  };

  const prof = 2 + Math.floor((form.level - 1) / 4);
  const hp = (cls?.hd || 8) + modifier(finalScores.con) + Math.max(0, form.level - 1) * (Math.floor((cls?.hd || 8) / 2) + 1 + modifier(finalScores.con));

  return (
    <div className="step-pane">
      <div className="step-title">✧ 第二章 · 天赋与禀性 ✧</div>
      <div className="step-sub">六项能力决定你能做什么、擅长什么。</div>

      {/* 方法切换 */}
      <div className="method-tabs">
        {[['pointbuy', '点数购买', '更自由 · 27 点'], ['standard', '标准数组', '经典 · 15/14/13/12/10/8']].map(([k, n, d]) => (
          <div key={k} className={`method-tab ${scoreMethod === k ? 'sel' : ''}`}
            onClick={() => { setScoreMethod(k); setAssigned({}); }}>
            <div className="n">{n}</div>
            <div className="d">{d}</div>
          </div>
        ))}
      </div>

      {scoreMethod === 'pointbuy' && (
        <div className="points-bar">
          <div className="label">剩余点数</div>
          <div className="points-big" style={{ color: pointsLeft === 0 ? 'var(--emerald-light)' : 'var(--amber)' }}>{pointsLeft}</div>
          <div className="track"><div className="fill" style={{ width: `${((POINTS - pointsLeft) / POINTS) * 100}%`, background: pointsLeft === 0 ? 'var(--emerald-light)' : 'var(--gold-gradient)' }} /></div>
          <div className="label">{pointsLeft === 0 ? '✓ 已分配完毕' : `${POINTS - pointsLeft} / ${POINTS}`}</div>
        </div>
      )}

      {/* 六项能力卡 */}
      <div className="ability-grid">
        {ABILITY_KEYS.map(k => {
          const base = scoreMethod === 'pointbuy' ? scores[k] : (assigned[k] !== undefined ? ARRAY[assigned[k]] : 8);
          const bonus = racialBonus[k] || 0;
          const final = base + bonus;
          const mod = modifier(final);
          return (
            <div key={k} className="ability-plaque">
              <div className="plaque-top">
                <div className="ab-name">{ABILITY_ZH[k]}</div>
                <div className="ab-key">{k.toUpperCase()}</div>
              </div>
              <div className="plaque-main">
                <div className="score">{final}</div>
                <div className="mod">{modStr(mod)}</div>
              </div>
              {bonus > 0 && (
                <div className="bonus-badge">基础 {base} · 种族 +{bonus}</div>
              )}
              {scoreMethod === 'pointbuy' ? (
                <div className="adj">
                  <button onClick={() => adj(k, -1)} disabled={base <= 8}>−</button>
                  <div className="val">{base}</div>
                  <button onClick={() => adj(k, 1)} disabled={base >= 15 || pointsLeft < (COSTS[base + 1] - COSTS[base])}>+</button>
                </div>
              ) : (
                <div className="array-row">
                  {ARRAY.map((v, i) => {
                    const used = Object.entries(assigned).some(([a, idx]) => a !== k && idx === i);
                    const sel = assigned[k] === i;
                    return (
                      <button key={i} disabled={used} className={`arr ${sel ? 'sel' : ''}`}
                        onClick={() => assign(k, i)}>{v}</button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 衍生属性预览 */}
      <div className="derived-row">
        <div className="der"><div className="t">最大生命</div><div className="v">{Math.max(1, hp)}</div></div>
        <div className="der"><div className="t">先攻</div><div className="v">{modStr(modifier(finalScores.dex))}</div></div>
        <div className="der"><div className="t">熟练</div><div className="v">+{prof}</div></div>
        <div className="der"><div className="t">攻击</div><div className="v">{modStr(prof + Math.max(modifier(finalScores.str), modifier(finalScores.dex)))}</div></div>
        <div className="der"><div className="t">AC</div><div className="v">{10 + modifier(finalScores.dex)}</div></div>
      </div>
    </div>
  );
}

// ─── Step 3: 技能 ──────────────────────────────
function Step3({ cls, skills, setSkills }) {
  const count = cls?.skills || 2;
  const toggle = s => {
    if (skills.includes(s)) setSkills(skills.filter(x => x !== s));
    else if (skills.length < count) setSkills([...skills, s]);
  };
  return (
    <div className="step-pane">
      <div className="step-title">✧ 第三章 · 所学所长 ✧</div>
      <div className="step-sub">{cls?.zh} 可选择 <b style={{ color: 'var(--amber)' }}>{count}</b> 项技能熟练 · 已选 <b style={{ color: skills.length === count ? 'var(--emerald-light)' : 'var(--amber)' }}>{skills.length}</b></div>

      <div className="skill-grid">
        {SKILLS.map(({ k, ab }) => {
          const sel = skills.includes(k);
          const dis = !sel && skills.length >= count;
          return (
            <div key={k} className={`skill-card ${sel ? 'sel' : ''} ${dis ? 'dis' : ''}`}
              onClick={() => !dis && toggle(k)}>
              <div className="s-check">{sel ? '✓' : '○'}</div>
              <div className="s-name">{k}</div>
              <div className="s-ab">{ABILITY_ZH[ab]}</div>
            </div>
          );
        })}
      </div>

      <div className="create-note">
        <span className="lead">豁免熟练</span>
        （由 {cls?.zh} 自动获得）：
        {cls?.save.map(s => ABILITY_ZH[s]).join(' · ')}
      </div>
    </div>
  );
}

// ─── Step 4: 装备 ──────────────────────────────
function Step4({ cls, equipChoice, setEquipChoice, Field }) {
  const equipOptions = {
    paladin: [
      { label: '方案 A · 剑盾圣契', items: ['长剑', '盾牌', '链甲', '圣徽', '背包 + 旅行工具'] },
      { label: '方案 B · 双手战锤', items: ['战锤（双手）', '链甲', '圣徽', '背包 + 旅行工具'] },
    ],
    fighter: [
      { label: '方案 A · 链甲 + 长剑 + 盾', items: ['链甲', '长剑', '盾牌', '手弩 + 20 支弩箭'] },
      { label: '方案 B · 皮甲 + 长弓', items: ['皮甲', '长弓', '20 支箭矢', '短剑 × 2'] },
    ],
    wizard: [
      { label: '方案 A · 法师手抄本', items: ['法师法杖', '法术书', '短剑', '组件包'] },
      { label: '方案 B · 学者', items: ['法杖', '法术书', '匕首', '学者包'] },
    ],
    rogue: [
      { label: '方案 A · 灵巧出击', items: ['皮甲', '短剑 × 2', '短弓 + 20 支箭', '盗贼工具'] },
    ],
  };
  const opts = equipOptions[cls?.key] || equipOptions.fighter;
  return (
    <div className="step-pane">
      <div className="step-title">✧ 第四章 · 起始装备 ✧</div>
      <div className="step-sub">这是你踏上旅程时所携之物。</div>

      <div className="equip-list">
        {opts.map((opt, i) => {
          const sel = equipChoice === i;
          return (
            <div key={i} className={`equip-card ${sel ? 'sel' : ''}`} onClick={() => setEquipChoice(i)}>
              <div className="equip-head">
                <div className={`radio ${sel ? 'on' : ''}`}>{sel && <div className="dot" />}</div>
                <div className="equip-name">{opt.label}</div>
              </div>
              <div className="equip-items">
                {opt.items.map((it, j) => <span key={j} className="item-chip">◈ {it}</span>)}
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-feat">
        <div className="bf-title">◈ 背景特性 · 贵族的权势 ◈</div>
        <div className="bf-desc">
          人们视你为有地位的人，所到之处受到礼遇。在城镇中可免费获得与你地位相符的住所，并可向地方官员求取会面。
        </div>
        <div className="bf-tags">
          <span className="tag tag-gold">⚔ 历史</span>
          <span className="tag tag-gold">⚔ 说服</span>
          <span className="tag">◈ 游戏套装</span>
          <span className="tag">◈ 额外语言 × 1</span>
        </div>
      </div>
    </div>
  );
}

// ─── Step 5: 法术 ──────────────────────────────
function Step5({ form, cantrips, setCantrips, cantripCount, spellsSel, setSpellsSel, spellCount }) {
  const availC = CANTRIPS[form.cls] || [];
  const availS = SPELLS[form.cls] || [];
  const tog = (arr, set, v, max) => {
    if (arr.includes(v)) set(arr.filter(x => x !== v));
    else if (arr.length < max) set([...arr, v]);
  };
  return (
    <div className="step-pane">
      <div className="step-title">✧ 第五章 · 秘术与祷言 ✧</div>
      <div className="step-sub">从职业法术目录中挑选你已掌握的魔法。</div>

      {cantripCount > 0 && (
        <>
          <div className="spell-section-title">
            <span className="t">戏法（0 环）</span>
            <span className="sub">无限施放 · 无需消耗法术位</span>
            <span className="count" style={{ color: cantrips.length === cantripCount ? 'var(--emerald-light)' : 'var(--arcane-light)' }}>{cantrips.length} / {cantripCount}</span>
          </div>
          <div className="spell-grid">
            {availC.map(s => {
              const sel = cantrips.includes(s);
              const dis = !sel && cantrips.length >= cantripCount;
              return (
                <div key={s} className={`spell-card cantrip ${sel ? 'sel' : ''} ${dis ? 'dis' : ''}`}
                  onClick={() => !dis && tog(cantrips, setCantrips, s, cantripCount)}>
                  <div className="sp-icon">✦</div>
                  <div className="sp-name">{s}</div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {spellCount > 0 && (
        <>
          <div className="spell-section-title" style={{ marginTop: 20 }}>
            <span className="t">已知法术（1 环）</span>
            <span className="sub">长休后可重新准备</span>
            <span className="count" style={{ color: spellsSel.length === spellCount ? 'var(--emerald-light)' : 'var(--amethyst-light)' }}>{spellsSel.length} / {spellCount}</span>
          </div>
          <div className="spell-grid">
            {availS.map(s => {
              const sel = spellsSel.includes(s);
              const dis = !sel && spellsSel.length >= spellCount;
              return (
                <div key={s} className={`spell-card lv1 ${sel ? 'sel' : ''} ${dis ? 'dis' : ''}`}
                  onClick={() => !dis && tog(spellsSel, setSpellsSel, s, spellCount)}>
                  <div className="sp-icon">❖</div>
                  <div className="sp-name">{s}</div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Step 6: 专长 / ASI ───────────────────────
function Step6({ level }) {
  const asiLevels = [4, 8, 12, 16, 19].filter(l => level >= l);
  const [choices, setChoices] = React.useState(asiLevels.map(() => 'asi'));
  const feats = ['敏锐', '坚韧', '强击者', '战法者', '神射手', '守护者', '利用诸元素'];
  return (
    <div className="step-pane">
      <div className="step-title">✧ 第六章 · 淬炼与专长 ✧</div>
      <div className="step-sub">Lv{level} — {asiLevels.length} 次 属性提升 / 专长选择</div>

      {asiLevels.map((lv, i) => (
        <div key={i} className="asi-row">
          <div className="asi-badge">Lv {lv}</div>
          <div className="asi-tabs">
            <button className={`asi-tab ${choices[i] === 'asi' ? 'sel' : ''}`}
              onClick={() => { const n = [...choices]; n[i] = 'asi'; setChoices(n); }}>
              +2 属性提升
            </button>
            <button className={`asi-tab ${choices[i] === 'feat' ? 'sel' : ''}`}
              onClick={() => { const n = [...choices]; n[i] = 'feat'; setChoices(n); }}>
              选择专长
            </button>
          </div>
          {choices[i] === 'feat' && (
            <select className="input-fantasy" style={{ maxWidth: 200 }}>
              {feats.map(f => <option key={f}>{f}</option>)}
            </select>
          )}
          {choices[i] === 'asi' && (
            <div className="asi-hint">从六项能力中选两项 +1 ，或一项 +2（在下一页面编辑）</div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Step 7: 队伍确认 ─────────────────────────
function Step7({ form, cls, race, finalScores }) {
  const companions = [
    { name: '索恩·石拳', cls: 'fighter', race: '矮人', role: '前排坦克' },
    { name: '薇拉·月语', cls: 'wizard',  race: '精灵', role: '爆发控场' },
    { name: '凯瑞丝',     cls: 'rogue',   race: '半身人', role: '侦察刺客' },
  ];
  const prof = 2 + Math.floor((form.level - 1) / 4);
  const hp = (cls?.hd || 8) + modifier(finalScores.con) + Math.max(0, form.level - 1) * (Math.floor((cls?.hd || 8) / 2) + 1 + modifier(finalScores.con));

  return (
    <div className="step-pane">
      <div className="step-title">✧ 终章 · 同伴相逢 ✧</div>
      <div className="step-sub">你的冒险不会独自前行。AI 已为你组建了最合拍的队伍。</div>

      {/* 玩家确认卡 */}
      <div className="final-hero-card">
        <div className="fh-left">
          <Portrait cls={form.cls} size="xl" />
        </div>
        <div className="fh-right">
          <div className="fh-name">{form.name}</div>
          <div className="fh-sub">{race?.zh} · {cls?.zh}{form.subclass ? ` · ${form.subclass}` : ''} · Lv {form.level}</div>
          <div className="fh-align">{form.alignment} · 背景：{form.background}</div>

          <div className="fh-stats">
            {ABILITY_KEYS.map(k => (
              <div key={k} className="fh-stat">
                <div className="n">{ABILITY_ZH[k]}</div>
                <div className="v">{finalScores[k]}</div>
                <div className="m">{modStr(modifier(finalScores[k]))}</div>
              </div>
            ))}
          </div>

          <div className="fh-derived">
            <span>HP {Math.max(1, hp)}</span>
            <span>AC {10 + modifier(finalScores.dex)}</span>
            <span>熟练 +{prof}</span>
            <span>先攻 {modStr(modifier(finalScores.dex))}</span>
          </div>
        </div>
      </div>

      {/* 队友 */}
      <div className="companions-title">
        <span className="orn">❦</span>
        <span className="t">你的队友</span>
        <span className="orn">❦</span>
      </div>

      <div className="companions-grid">
        {companions.map(c => (
          <div key={c.name} className="companion-card">
            <Portrait cls={c.cls} size="md" />
            <div className="cc-info">
              <div className="cc-name">{c.name}</div>
              <div className="cc-sub">{c.race} · {CLASSES.find(k => k.key === c.cls)?.zh}</div>
              <div className="cc-role">{c.role}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

window.CreateScene = CreateScene;
