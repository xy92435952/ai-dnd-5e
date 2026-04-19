// ════════════════════════════════════════════════════════════
// Combat Scene — RPG 游戏化版本
// BG3 底部 HUD + XCOM 风先攻条 + 伪 iso 战场 + 伤害飘字
// ════════════════════════════════════════════════════════════

const CBT_UNITS = [
  { id: 'p1', name: '艾琳',   cls: 'paladin',  init: 22, hp: 38, max: 48, ac: 18, team: 'player', letter: '艾', conds: [{ i: '✦', t: '祝圣武器', b: true }] },
  { id: 'p2', name: '凯瑞丝', cls: 'rogue',    init: 19, hp: 32, max: 36, ac: 15, team: 'ally',   letter: '凯', conds: [{ i: '❋', t: '潜行', b: true }] },
  { id: 'e1', name: '黑暗教徒', cls: 'enemy',  init: 16, hp: 22, max: 30, ac: 14, team: 'enemy',  letter: '教' },
  { id: 'p3', name: '索恩',   cls: 'fighter',  init: 12, hp: 45, max: 52, ac: 19, team: 'ally',   letter: '索' },
  { id: 'e2', name: '骷髅法师', cls: 'enemy',  init: 10, hp: 24, max: 24, ac: 12, team: 'enemy',  letter: '骨', conds: [{ i: '⊕', t: '法伤易伤' }] },
  { id: 'p4', name: '薇拉',   cls: 'wizard',   init: 9,  hp: 14, max: 28, ac: 13, team: 'ally',   letter: '薇', conds: [{ i: '⚠', t: '虚弱' }] },
  { id: 'e3', name: '暗影狼', cls: 'enemy',    init: 7,  hp: 0,  max: 18, ac: 13, team: 'enemy',  letter: '狼', dead: true },
];

const CBT_GRID_W = 10;
const CBT_GRID_H = 7;

// 棋盘预设
const CBT_MAP = {
  '3_3': { uid: 'p1' },  // active
  '2_4': { uid: 'p2' },
  '4_2': { uid: 'p3' },
  '2_2': { uid: 'p4' },
  '7_3': { uid: 'e1', targeted: true },
  '8_4': { uid: 'e2' },
};
const CBT_WALLS = ['5_1', '5_0', '0_5', '1_5', '5_5'];
const CBT_HAZARDS = ['6_5'];
const CBT_REACH = ['2_3', '3_2', '4_3', '3_4', '2_5', '4_4'];
const CBT_PATH  = ['4_3', '5_3', '6_3'];

const SKILL_BAR = [
  { k: 'atk',   label: '长剑劈砍', glyph: '⚔', cost: '动作', key: '1', kind: 'attack', hit: 75, dmg: '1d8+3' },
  { k: 'smite', label: '神圣斩击', glyph: '✦', cost: '附赠·1环', key: '2', kind: 'spell',  hit: 75, dmg: '+2d8 光耀' },
  { k: 'shove', label: '猛力推撞', glyph: '↦', cost: '动作', key: '3', kind: 'attack' },
  { k: 'bless', label: '祝福',     glyph: '✧', cost: '动作·1环', key: '4', kind: 'spell', cd: 0 },
  { k: 'heal',  label: '治疗之光', glyph: '✚', cost: '附赠·1环', key: '5', kind: 'bonus' },
  { k: 'lay',   label: '治疗魔掌', glyph: '☩', cost: '动作', key: '6', kind: 'bonus' },
  { k: 'dash',  label: '冲刺',     glyph: '»', cost: '动作', key: '7', kind: 'move' },
  { k: 'disg',  label: '脱离',     glyph: '↶', cost: '动作', key: '8', kind: 'move' },
  { k: 'empty', label: '', glyph: '', cost: '', key: '9', kind: 'empty' },
  { k: 'pot',   label: '治疗药剂', glyph: '⚱', cost: '动作', key: '0', kind: 'attack' },
];

const CBT_LOG = [
  { kind: 'crit', roll: '1d20=20', txt: '艾琳对黑暗教徒发起神圣斩击 — 暴击！' },
  { kind: 'dmg',  roll: '16 伤害', txt: '秘银长剑破开护甲，金色光焰灼烧皮肉' },
  { kind: 'normal', roll: '1d20=14', txt: '凯瑞丝潜行突袭 — 命中' },
  { kind: 'dmg',  roll: '8 伤害', txt: '匕首沿脊骨划过，偷袭加成 +3d6' },
  { kind: 'miss', roll: '1d20=5',  txt: '薇拉的火球术 — DC失败，敌人半伤' },
  { kind: 'normal', roll: '回合',   txt: '—— 第 3 回合开始 ——' },
];

function CombatScene() {
  const active = CBT_UNITS.find(u => u.id === 'p1');
  const target = CBT_UNITS.find(u => u.id === 'e1');

  const [selSkill, setSelSkill] = React.useState('smite');
  const [floats, setFloats] = React.useState([
    { id: 1, kind: 'crit', val: '32!', x: 70, y: 30 },
    { id: 2, kind: 'dmg',  val: '16', x: 72, y: 42 },
    { id: 3, kind: 'miss', val: 'MISS',  x: 28, y: 60 },
  ]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'linear-gradient(180deg, #06040a 0%, #0a0604 100%)' }}>

      {/* ── 回合横幅 ── */}
      <div className="turn-banner">
        <span className="round-tag">R 3</span>
        <span style={{ color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '.2em', marginRight: 8 }}>轮到</span>
        <span className="active-name">艾琳·晨光</span>
        <span style={{ marginLeft: 14, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>· 银谷村·酒馆伏击 ·</span>
      </div>

      {/* ── 横向先攻条 ── */}
      <div className="init-ribbon">
        {CBT_UNITS.map((u, i) => {
          const pct = (u.hp / u.max) * 100;
          const low = pct < 34;
          return (
            <div key={u.id} className={`unit-chip ${u.team === 'enemy' ? 'enemy' : ''} ${u.id === 'p1' ? 'active' : ''} ${u.dead ? 'dead' : ''} ${low ? 'low' : ''}`}>
              <div className="init-no">{u.init}</div>
              <div className="avatar">{u.letter}{u.dead && '×'}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment)', letterSpacing: '.08em', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.name}</div>
              <div className="hp-tick"><div className="fill" style={{ width: `${pct}%` }} /></div>
              {u.conds && (
                <div style={{ display: 'flex', justifyContent: 'center', gap: 1, marginTop: 2 }}>
                  {u.conds.map((c, ci) => (
                    <span key={ci} style={{ fontSize: 8, color: c.b ? 'var(--arcane-light)' : '#f4a0a0' }}>{c.i}</span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        <div style={{ flex: 1 }} />
        <button className="btn-ghost" style={{ padding: '4px 12px', fontSize: 9 }}>☰ 日志</button>
      </div>

      {/* ── 战场（iso）── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'grid', placeItems: 'center', padding: '30px 20px 0' }}>
        {/* 氛围雾 */}
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(ellipse at 30% 40%, rgba(47,168,184,.08), transparent 60%), radial-gradient(ellipse at 80% 60%, rgba(196,40,40,.1), transparent 55%)' }} />

        <div className="iso-battlefield">
          <div className="iso-grid" style={{ gridTemplateColumns: `repeat(${CBT_GRID_W}, 54px)`, gridTemplateRows: `repeat(${CBT_GRID_H}, 54px)` }}>
            {Array.from({ length: CBT_GRID_H }).flatMap((_, y) =>
              Array.from({ length: CBT_GRID_W }).map((_, x) => {
                const key = `${x}_${y}`;
                const cell = CBT_MAP[key];
                const unit = cell && CBT_UNITS.find(u => u.id === cell.uid);
                const isWall = CBT_WALLS.includes(key);
                const isHazard = CBT_HAZARDS.includes(key);
                const isPath = CBT_PATH.includes(key);
                const isReach = CBT_REACH.includes(key);
                const isTarget = cell?.targeted;
                const klass = isWall ? 'wall'
                  : isTarget ? 'target'
                  : isHazard ? 'hazard'
                  : isPath ? 'path'
                  : isReach ? 'reach' : '';
                return (
                  <div key={key} className={`iso-cell ${klass}`}>
                    {unit && (
                      <div className={`iso-unit ${unit.team === 'enemy' ? 'enemy' : unit.team === 'player' ? 'player' : 'ally'} ${unit.id === 'p1' ? 'active' : ''} ${(unit.hp/unit.max) < .34 ? 'low' : ''}`}
                        style={{
                          '--c-light': unit.team === 'enemy' ? '#f04848' : unit.team === 'player' ? '#6ae884' : '#7fc8f8',
                          '--c-dark':  unit.team === 'enemy' ? '#3a0a0a' : unit.team === 'player' ? '#1a4a28' : '#143a5e',
                          '--c-glow':  unit.team === 'enemy' ? '#f04848' : unit.team === 'player' ? '#6ae884' : '#5fb8f8',
                        }}>
                        <div className="base" />
                        <div className="sprite-wrap">
                          <PixelSprite
                            kind={
                              unit.cls === 'paladin' ? 'paladin'
                              : unit.cls === 'rogue' ? 'rogue'
                              : unit.cls === 'fighter' ? 'fighter'
                              : unit.cls === 'wizard' ? 'wizard'
                              : unit.id === 'e1' ? 'cultist'
                              : unit.id === 'e2' ? 'skeleton_mage'
                              : unit.id === 'e3' ? 'shadow_wolf'
                              : 'paladin'
                            }
                            size={46}
                            dead={unit.dead}
                          />
                        </div>
                        <div className="micro-hp"><div className="fill" style={{ width: `${(unit.hp/unit.max)*100}%` }} /></div>
                        {isTarget && <div className="target-ring" />}
                      </div>
                    )}
                    {isPath && !unit && <span style={{ fontSize: 10, color: 'var(--arcane-light)', opacity: .7 }}>◆</span>}
                    {isReach && !unit && !isPath && <span style={{ fontSize: 9, color: 'var(--arcane-light)', opacity: .45 }}>·</span>}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* 伤害浮字 */}
        {floats.map(f => (
          <span key={f.id} className={`float-text ${f.kind}`} style={{ left: `${f.x}%`, top: `${f.y}%` }}>{f.val}</span>
        ))}

        {/* 目标卡浮于右上 */}
        <div style={{ position: 'absolute', top: 20, right: 20, width: 220 }}>
          <div className="target-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="name">◈ 黑暗教徒</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.15em' }}>TARGET</span>
            </div>
            <div style={{ height: 8, background: '#0a0604', border: '1px solid rgba(196,40,40,.5)', marginTop: 6 }}>
              <div style={{ height: '100%', width: `${(22/30)*100}%`, background: 'linear-gradient(90deg, #f04040, #8a1818)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.3)' }} />
            </div>
            <div className="hit-pred">
              <span>HP <b style={{ color: '#f4a0a0' }}>22/30</b> · AC <b style={{ color: 'var(--parchment)' }}>14</b></span>
            </div>
            <div style={{ borderTop: '1px solid rgba(138,90,24,.3)', marginTop: 8, paddingTop: 8 }}>
              <div className="hit-pred">
                <span>命中</span>
                <span className="pct">75%</span>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--parchment-dark)', letterSpacing: '.08em', marginTop: 3 }}>
                预期伤害 <span style={{ color: 'var(--amber)', fontWeight: 700 }}>1d8+3 +2d8光耀</span>
              </div>
            </div>
          </div>
        </div>

        {/* 图例浮于顶部中线 */}
        <div style={{ position: 'absolute', top: 6, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', gap: 14, fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--parchment-dark)', letterSpacing: '.1em',
          padding: '4px 14px', background: 'rgba(0,0,0,.6)', border: '1px solid rgba(138,90,24,.3)', zIndex: 5 }}>
          <span style={{ color: 'var(--arcane-light)' }}>◆ 路径</span>
          <span style={{ color: 'rgba(127,232,248,.7)' }}>· 可达</span>
          <span style={{ color: 'var(--flame)' }}>◎ 目标</span>
          <span style={{ color: '#f08040' }}>✺ 危险</span>
          <span style={{ color: 'var(--parchment-dark)' }}>■ 墙体</span>
        </div>
      </div>

      {/* ═══ 底部游戏化 HUD ═══ */}
      <div className="combat-hud">

        {/* 左 · 当前角色 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="action-pips">
            <div className="pip action"><span>⚔</span></div>
            <div className="pip bonus used"><span>✦</span></div>
            <div className="pip react"><span>⚡</span></div>
          </div>
          <div className="hud-portrait">
            <div className="big">艾</div>
            <div className="stats">
              <div className="name">艾琳·晨光</div>
              <div className="sub">圣武士 · 誓言守护 · Lv 5</div>
              <div className="hp-segmented mid">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className={`seg ${i >= Math.round((38/48)*12) ? 'empty' : ''}`} />
                ))}
              </div>
              <div className="hp-text">
                <span><span className="cur">38</span> / 48</span>
                <span>移动 <b style={{ color: 'var(--arcane-light)' }}>20/30</b></span>
              </div>
              <div className="stat-line">
                <span>AC <span className="v">18</span></span>
                <span>先攻 <span className="v">+2</span></span>
                <span>DC <span className="v">14</span></span>
              </div>
              <div className="conditions">
                <span className="cond-icon buff" title="祝圣武器">✦</span>
                <span className="cond-icon buff" title="神圣援助">✧</span>
              </div>
            </div>
          </div>
        </div>

        {/* 中 · 技能快捷栏 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div className="skill-bar">
            {SKILL_BAR.map(s => (
              <div key={s.k} className={`slot-key ${s.kind} ${selSkill === s.k ? 'active' : ''}`}
                onClick={() => s.kind !== 'empty' && setSelSkill(s.k)}
                style={selSkill === s.k && s.kind !== 'empty' ? {
                  borderColor: 'var(--flame)',
                  transform: 'translateY(-3px)',
                  boxShadow: 'inset 0 1px 0 rgba(240,208,96,.4), 0 0 0 1px var(--flame), 0 0 22px -2px var(--flame), 0 6px 12px -4px rgba(0,0,0,.8)',
                } : {}}>
                <span className="hot">{s.key}</span>
                <span className="glyph">{s.glyph}</span>
                {s.cost && <span className="cost">{s.cost.split('·')[0]}</span>}
              </div>
            ))}
          </div>
          <div className="slot-label-bar">
            {SKILL_BAR.map(s => <span key={s.k}>{s.label || '—'}</span>)}
          </div>

          {/* 战斗日志 */}
          <div className="combat-log" style={{ marginTop: 4 }}>
            {CBT_LOG.map((l, i) => (
              <div key={i} className={`log-entry ${l.kind}`}>
                <span className="roll">{l.roll}</span>
                <span>{l.txt}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 右 · 法术位 + 结束回合 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{
            padding: '8px 10px',
            background: 'linear-gradient(180deg, #1a1208, #0a0604)',
            border: '1px solid rgba(138,90,24,.5)',
            boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
          }}>
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 10, color: 'var(--amber)', letterSpacing: '.2em', textTransform: 'uppercase', marginBottom: 6 }}>
              ✦ 法术位
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {[
                { lv: '1环', cur: 3, max: 4 },
                { lv: '2环', cur: 1, max: 2 },
              ].map(sp => (
                <div key={sp.lv} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--arcane-light)', letterSpacing: '.08em', width: 24 }}>{sp.lv}</span>
                  <div className="spell-slots">
                    {Array.from({ length: sp.max }).map((_, i) => (
                      <div key={i} className={`slot-gem ${i >= sp.cur ? 'used' : ''}`} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(138,90,24,.3)', display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.1em' }}>
              <span>专注 <span style={{ color: 'var(--flame)' }}>祝福</span></span>
              <span>命运 <span style={{ color: 'var(--amber)', fontWeight: 700 }}>2/3</span></span>
            </div>
          </div>

          <button className="end-turn-mega">☰ 结束回合</button>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}>▶ 等待</button>
            <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}>⊙ 闪避</button>
            <button className="btn-ghost" style={{ fontSize: 10, padding: '5px 8px' }}>☉ 搜索</button>
            <button className="btn-danger" style={{ fontSize: 9, padding: '5px 8px' }}>终止</button>
          </div>
        </div>
      </div>
    </div>
  );
}

window.CombatScene = CombatScene;
