// ════════════════════════════════════════════════════════════
// Combat Scene — 战斗页面重构
// ════════════════════════════════════════════════════════════
const COMBATANTS = [
  { id: 'p1', name: '艾琳', cls: 'paladin', init: 18, hp_cur: 42, hp_max: 48, ac: 18, team: 'player', active: true },
  { id: 'p2', name: '凯瑞丝', cls: 'rogue', init: 16, hp_cur: 32, hp_max: 36, ac: 15, team: 'ally' },
  { id: 'e1', name: '黑暗教徒', cls: 'enemy', init: 14, hp_cur: 22, hp_max: 30, ac: 14, team: 'enemy' },
  { id: 'p3', name: '索恩', cls: 'fighter', init: 12, hp_cur: 38, hp_max: 52, ac: 19, team: 'ally' },
  { id: 'e2', name: '暗影狼', cls: 'enemy', init: 10, hp_cur: 0, hp_max: 18, ac: 13, team: 'enemy', dead: true },
  { id: 'p4', name: '薇拉', cls: 'wizard', init: 9, hp_cur: 14, hp_max: 28, ac: 13, team: 'ally' },
  { id: 'e3', name: '骷髅法师', cls: 'enemy', init: 8, hp_cur: 24, hp_max: 24, ac: 12, team: 'enemy' },
];

// 8x10 grid layout
const GRID = { w: 10, h: 8 };
const UNITS = {
  '3_2': { id: 'p1', team: 'player', cls: 'paladin', letter: '艾' },
  '4_2': { id: 'p3', team: 'ally', cls: 'fighter', letter: '索' },
  '2_3': { id: 'p2', team: 'ally', cls: 'rogue', letter: '凯' },
  '2_1': { id: 'p4', team: 'ally', cls: 'wizard', letter: '薇' },
  '7_3': { id: 'e1', team: 'enemy', cls: 'enemy', letter: '教' },
  '8_5': { id: 'e3', team: 'enemy', cls: 'enemy', letter: '骨' },
};
const WALLS = ['5_0', '5_1', '0_5', '1_5'];
const REACH = ['3_3', '4_3', '3_1', '4_1', '2_2']; // 可移动格
const TARGETS = ['7_3']; // 攻击目标

function CombatScene() {
  const active = COMBATANTS.find(c => c.active);
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* 顶栏 — 轮次横幅 */}
      <div style={{
        padding: '10px 24px',
        background: 'linear-gradient(180deg, rgba(138,26,26,.35), rgba(74,10,10,.15))',
        borderBottom: '1px solid var(--blood-light)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span className="eyebrow" style={{ color: 'var(--blood-light)', letterSpacing: '.3em' }}>⚔ 战斗进行中 ⚔</span>
          <span style={{ fontFamily: 'var(--font-heading)', fontSize: 13, color: 'var(--parchment-dark)' }}>第 3 回合</span>
        </div>
        <div className="display-title" style={{ fontSize: 16 }}>⚜ 银谷村·酒馆伏击 ⚜</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-ghost" style={{ padding: '5px 12px', fontSize: 10 }}>☰ 日志</button>
          <button className="btn-danger" style={{ padding: '5px 12px' }}>终止战斗</button>
        </div>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '220px 1fr 280px', gap: 0, overflow: 'hidden' }}>

        {/* 左 — 先攻顺序 */}
        <aside style={{ padding: '14px 10px', borderRight: '1px solid var(--bark-light)', overflowY: 'auto', background: 'linear-gradient(180deg, rgba(10,6,2,.5), rgba(10,6,2,.2))' }}>
          <div className="eyebrow" style={{ textAlign: 'center', marginBottom: 10 }}>✦ 先攻顺序 ✦</div>
          {COMBATANTS.map((c, i) => (
            <div key={c.id} className={`init-row ${c.active ? 'active' : ''} ${c.dead ? 'dead' : ''}`}>
              <div className="init-num">{i + 1}</div>
              <Portrait cls={c.cls} size="sm" wounded={c.hp_cur / c.hp_max < 0.35} style={{ width: 32, height: 32 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: 'var(--font-heading)', fontSize: 12, color: 'var(--parchment)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.name} {c.dead && '💀'}
                </div>
                <div style={{ height: 3, background: 'var(--bark)', borderRadius: 2, marginTop: 3, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%',
                    width: `${Math.max(0, (c.hp_cur / c.hp_max) * 100)}%`,
                    background: c.team === 'enemy' ? 'linear-gradient(90deg, #c83838, #e06040)' : 'linear-gradient(90deg, #3a7a48, #6aaa6a)',
                  }} />
                </div>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--amber)' }}>{c.init}</div>
            </div>
          ))}
        </aside>

        {/* 中 — 战斗地图 */}
        <div style={{ padding: 18, overflow: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 14, color: 'var(--amber)', letterSpacing: '.1em' }}>
              ☪ 轮到 <span style={{ fontFamily: 'var(--font-display)', fontSize: 18 }}>艾琳</span> 行动
            </div>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--parchment-dark)', marginTop: 3 }}>
              行动 · 附赠 · 反应 · 移动 30 / 30 ft
            </div>
          </div>

          <div
            className="battle-grid"
            style={{ gridTemplateColumns: `repeat(${GRID.w}, 48px)`, gridTemplateRows: `repeat(${GRID.h}, 48px)` }}
          >
            {Array.from({ length: GRID.h }).flatMap((_, y) =>
              Array.from({ length: GRID.w }).map((_, x) => {
                const key = `${x}_${y}`;
                const unit = UNITS[key];
                const isWall = WALLS.includes(key);
                const isReach = REACH.includes(key);
                const isTarget = TARGETS.includes(key);
                const cls = unit
                  ? unit.team
                  : isWall ? 'wall'
                  : isTarget ? 'target'
                  : isReach ? 'reach' : '';
                return (
                  <div key={key} className={`battle-cell ${cls}`}>
                    {unit && (
                      <div className="unit-token" style={{
                        background: unit.team === 'player' ? 'radial-gradient(circle at 35% 30%, #4e86b8, #1e3658)'
                                 : unit.team === 'ally' ? 'radial-gradient(circle at 35% 30%, #6aaa6a, #1e3a24)'
                                 : 'radial-gradient(circle at 35% 30%, #c83838, #3a0a0a)',
                        boxShadow: unit.team === 'player' ? '0 0 14px rgba(78,134,184,.6), 0 2px 6px rgba(0,0,0,.6)' : '0 2px 6px rgba(0,0,0,.6)',
                        border: unit.team === 'player' ? '2px solid var(--amber)' : '1px solid rgba(0,0,0,.4)',
                      }}>
                        {unit.letter}
                      </div>
                    )}
                    {isReach && !unit && <span style={{ fontSize: 8, color: 'var(--amber)', opacity: .5, fontFamily: 'var(--font-mono)' }}>•</span>}
                  </div>
                );
              })
            )}
          </div>

          {/* 图例 */}
          <div style={{ display: 'flex', gap: 14, fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--parchment-dark)', flexWrap: 'wrap', justifyContent: 'center' }}>
            <LegendDot color="rgba(78,134,184,.6)" label="玩家" />
            <LegendDot color="rgba(95,168,120,.6)" label="队友" />
            <LegendDot color="rgba(200,56,56,.6)" label="敌人" />
            <LegendDot color="rgba(212,168,71,.4)" label="可达" dashed />
            <LegendDot color="var(--amber)" label="目标" pulse />
          </div>
        </div>

        {/* 右 — 行动面板 */}
        <aside style={{ padding: '14px 14px', borderLeft: '1px solid var(--bark-light)', overflowY: 'auto', background: 'linear-gradient(180deg, rgba(10,6,2,.5), rgba(10,6,2,.2))', display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* 当前角色状态 */}
          <div className="panel-ornate" style={{ padding: 12 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 }}>
              <Portrait cls="paladin" size="md" />
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 15, color: 'var(--parchment)' }}>艾琳·晨光</div>
                <div className="eyebrow" style={{ fontSize: 9 }}>圣武士 · 誓言守护</div>
              </div>
            </div>
            <HpBar cur={42} max={48} />
            <div style={{ display: 'flex', gap: 8, marginTop: 8, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              <span style={{ color: 'var(--parchment-dark)' }}>AC</span>
              <span style={{ color: 'var(--amber)', fontWeight: 700 }}>18</span>
              <span style={{ color: 'var(--bark-light)' }}>|</span>
              <span style={{ color: 'var(--parchment-dark)' }}>先攻</span>
              <span style={{ color: 'var(--amber)', fontWeight: 700 }}>+2</span>
            </div>
          </div>

          {/* 行动配额 */}
          <div className="panel-ornate" style={{ padding: 12 }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>⚜ 本回合行动 ⚜</div>
            <QuotaRow label="行动" dots={1} used={0} glyph="⚔" />
            <QuotaRow label="附赠行动" dots={1} used={0} glyph="✦" />
            <QuotaRow label="反应" dots={1} used={0} glyph="⚡" />
            <div style={{ marginTop: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--parchment-dark)', marginBottom: 4 }}>
                <span>移动</span>
                <span style={{ color: 'var(--amber)' }}>20/30 ft</span>
              </div>
              <div style={{ height: 6, background: 'var(--bark)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: '67%', background: 'linear-gradient(90deg, var(--sapphire), var(--sapphire-light))' }} />
              </div>
            </div>
          </div>

          {/* 行动按钮 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button className="action-btn attack"><span style={{ width: 18, textAlign: 'center' }}>⚔</span>近战攻击</button>
            <button className="action-btn spell"><span style={{ width: 18, textAlign: 'center' }}>✦</span>施放法术</button>
            <button className="action-btn move"><span style={{ width: 18, textAlign: 'center' }}>➤</span>移动</button>
            <button className="action-btn bonus"><span style={{ width: 18, textAlign: 'center' }}>✧</span>圣击 (附赠)</button>
            <button className="action-btn"><span style={{ width: 18, textAlign: 'center' }}>⊙</span>闪避</button>
            <button className="action-btn"><span style={{ width: 18, textAlign: 'center' }}>»</span>冲刺</button>
            <button className="action-btn"><span style={{ width: 18, textAlign: 'center' }}>↶</span>脱离</button>
            <button className="action-btn end" style={{ marginTop: 8 }}>☰ 结束回合</button>
          </div>

          {/* 战斗事件 */}
          <div className="panel-ornate" style={{ padding: 10, maxHeight: 160, overflow: 'auto' }}>
            <div className="eyebrow" style={{ marginBottom: 6 }}>✥ 战斗事件 ✥</div>
            <LogLine color="var(--blood-light)">教徒的匕首刺向你 · d20=14+5=19 vs AC18 · 命中 6 伤害</LogLine>
            <LogLine color="var(--emerald-light)">凯瑞丝悄然潜行，获得偷袭加成</LogLine>
            <LogLine color="var(--amber)">薇拉消耗 2环法术位 施放"灼热射线"</LogLine>
            <LogLine color="var(--parchment-dark)">暗影狼倒下 💀</LogLine>
          </div>
        </aside>
      </div>
    </div>
  );
}

function LegendDot({ color, label, dashed, pulse }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      <span style={{
        width: 10, height: 10, borderRadius: 3,
        background: color,
        border: dashed ? '1px dashed var(--amber)' : 'none',
        animation: pulse ? 'breathe 1.4s ease-in-out infinite' : 'none',
      }} />
      {label}
    </span>
  );
}

function QuotaRow({ label, dots, used, glyph }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
      <span style={{ fontSize: 12, color: 'var(--amber)' }}>{glyph}</span>
      <span style={{ flex: 1, fontSize: 11, color: 'var(--parchment-dark)', fontFamily: 'var(--font-heading)' }}>{label}</span>
      <span className="quota-dots">
        {Array.from({ length: dots }).map((_, i) => (
          <span key={i} className={`d ${i < used ? 'used' : ''}`} />
        ))}
      </span>
    </div>
  );
}

function LogLine({ color, children }) {
  return (
    <div style={{
      fontSize: 11, lineHeight: 1.6, padding: '3px 0',
      borderBottom: '1px solid rgba(90,58,34,.2)',
      color: 'var(--parchment)',
      fontFamily: 'var(--font-body)',
    }}>
      <span style={{ color, marginRight: 6 }}>●</span>{children}
    </div>
  );
}

window.CombatScene = CombatScene;
