/**
 * Tutorial — 新手教程系统
 * =========================
 * 源自 design bundle（claude.ai/design "h1kg0Nx3..."），
 * UI 外壳整体保留、内容（TUTORIAL_CONTENT）已从 Claude Design 占位填充为
 * 真实的 DnD 跑团教学文案。
 *
 * 导出：
 *   <TutorialEntryCard />  — 可挂在主页/大厅的入口卡
 *   <TutorialHost />       — 顶层容器（welcome → runner → dojo 模式切换）
 *
 * 用法（Home.jsx）：
 *   const [tutOpen, setTutOpen] = useState(false)
 *   return (<>
 *     <TutorialEntryCard onOpen={() => setTutOpen(true)} />
 *     <TutorialHost open={tutOpen} onClose={() => setTutOpen(false)} />
 *   </>)
 *
 * 章节 2-4 会提到"点击「创建角色」"等跨页动作——如果玩家当前不在对应页，
 * 会走"纯文本讲解"模式（spotlight 居中展示 coach 气泡，不挖空）。
 * 未来可在 CharacterCreate / Adventure / Combat 添加 `data-tut="..."` 锚点
 * 启用完整的 spotlight 引导。
 */

import { useState, useEffect, useMemo } from 'react'

// ═══════════════════════════════════════════════════════════
// TUTORIAL_CONTENT — 真实教学内容
// ═══════════════════════════════════════════════════════════

const TUTORIAL_CONTENT = {
  chapters: [
    {
      id: 'intro',
      idx: 1,
      glyph: '✦',
      title: '欢迎来到战役',
      desc: '认识你的 AI 地下城主 · 了解核心玩法',
      duration: '约 3 分钟',
      steps: [
        {
          id: 'welcome',
          coach: '欢迎，年轻的冒险者。我是<span class="coach-highlight">艾尔德林</span>——本局战役的地下城主。你即将踏入的，是 50 年桌上角色扮演（TRPG）的经典传统——<span class="coach-highlight">龙与地下城 5e</span>。在这里，你扮演一位英雄，而我负责讲述世界、扮演 NPC、判定命运。',
          require: 'auto',
        },
        {
          id: 'roles',
          coach: '跑团有三个核心要素：<br/>① <span class="coach-highlight">DM</span>（地下城主，我）——描述场景、裁决规则。<br/>② <span class="coach-highlight">玩家</span>（你）——用角色的眼睛看世界、宣告你的行动。<br/>③ <span class="coach-highlight">骰子</span>——当成败存疑时，让命运来决定。',
          require: 'auto',
        },
        {
          id: 'dice',
          coach: '最常用的是 <span class="coach-key">d20</span>，一个 20 面骰。几乎所有关键判定都从它开始：<br/>◆ 攻击能否命中？掷 d20。<br/>◆ 能否说服守卫？掷 d20。<br/>◆ 能否翻过高墙？掷 d20。<br/><br/>骰出数字 + 你的<span class="coach-highlight">修正值</span> ≥ <span class="coach-highlight">难度（DC）</span> = 成功。',
          tip: '自然 20（原始点数=20）= 大成功；自然 1 = 大失手。这是跑团最戏剧化的两个瞬间。',
          require: 'auto',
        },
        {
          id: 'flow',
          coach: '本教程会带你走三步：<br/>① <span class="coach-highlight">铸造英雄</span>——种族、职业、能力、装备。<br/>② <span class="coach-highlight">第一次跑团</span>——一场小酒馆的对话。<br/>③ <span class="coach-highlight">第一场战斗</span>——先攻、移动、攻击、法术。<br/><br/>每章几分钟。做完你就能独立开团了。',
          unlock: { name: '踏入门槛', desc: '你已了解跑团的基本规则' },
          require: 'auto',
        },
      ],
    },
    {
      id: 'create',
      idx: 2,
      glyph: '☙',
      title: '铸造你的英雄',
      desc: '种族、职业、能力、背景、技能、纹章 —— 六步成型',
      duration: '约 6 分钟',
      steps: [
        {
          id: 'c-intro',
          coach: '一位英雄由六个维度定义：<span class="coach-highlight">种族</span>、<span class="coach-highlight">职业</span>、<span class="coach-highlight">能力值</span>、<span class="coach-highlight">背景</span>、<span class="coach-highlight">技能</span>、<span class="coach-highlight">装备</span>。接下来我逐一介绍。',
          require: 'auto',
        },
        {
          id: 'c-race',
          coach: '<span class="coach-highlight">种族</span>影响外貌与天赋：精灵灵巧、矮人坚韧、半精灵圆融。5e 的 9 个主要种族各有属性加值与特殊能力，没有绝对"最优"——选你喜欢的即可。',
          glossary: {
            term: '种族',
            pron: 'ZHONG ZU',
            def: '决定你的血统背景。带来属性加值、额外语言、视觉能力（如矮人的黑暗视觉）、以及独特的种族特性。',
            example: '半兽人 +2 力量 +1 体质 · 暗视 60尺 · 精英不屈（HP 归零时 1/长休机会留 1HP 不倒）。',
          },
          require: 'auto',
        },
        {
          id: 'c-class',
          coach: '<span class="coach-highlight">职业</span>决定你的战斗方式与成长曲线。<br/>◆ 战士 / 野蛮人——前排硬汉，上去扛线砍人。<br/>◆ 法师 / 术士——后排爆发，火球/闪电伺候。<br/>◆ 盗贼 / 游侠——灵巧偷袭，潜行/射箭。<br/>◆ 牧师 / 德鲁伊——治疗辅助，神圣烈焰。<br/>◆ 圣武士 / 邪术师——混合型，战法平衡。<br/><br/>新手推荐 <span class="coach-highlight">战士</span>——规则简单、容错率高、上手即战力。',
          require: 'auto',
        },
        {
          id: 'c-ability',
          coach: '6 项<span class="coach-highlight">能力值</span>是一切判定的根基：<br/>◆ <span class="coach-key">STR</span> 力量——近战攻击、负重、推撞。<br/>◆ <span class="coach-key">DEX</span> 敏捷——远程攻击、护甲加值、先攻。<br/>◆ <span class="coach-key">CON</span> 体质——HP、专注检定。<br/>◆ <span class="coach-key">INT</span> 智力——法师施法、奥秘/调查。<br/>◆ <span class="coach-key">WIS</span> 感知——牧师施法、察觉/洞察。<br/>◆ <span class="coach-key">CHA</span> 魅力——游说、欺瞒、吟游/邪术施法。',
          tip: '游戏里用的不是能力值本身，而是它的"修正值"——如 14 对应 +2；16 对应 +3；8 对应 -1。',
          require: 'auto',
        },
        {
          id: 'c-bg',
          coach: '<span class="coach-highlight">背景</span>描述你当冒险者前是什么身份：士兵、学者、罪犯、流浪者……每个背景赠送 2 项技能熟练 + 若干工具/语言 + 独特特性，还会影响 NPC 对你的初印象。',
          require: 'auto',
        },
        {
          id: 'c-skill',
          coach: '<span class="coach-highlight">技能熟练</span>让你在对应领域更可靠——骰点时加 <span class="coach-highlight">熟练加值</span>（1 级时 +2，随等级成长）。一个擅长"隐匿"的盗贼，在潜行时几乎不会失败。',
          glossary: {
            term: '熟练加值',
            pron: 'PROFICIENCY',
            def: '随等级成长的加值（Lv1-4: +2; Lv5-8: +3; Lv9-12: +4; ...）。加在熟练技能、熟练武器、职业法术的判定上。',
            example: '战士的"运动"熟练：d20 + STR 修正 + 熟练加值。高墙再高也能翻过去。',
          },
          require: 'auto',
        },
        {
          id: 'c-finale',
          coach: '最后一步，确认你的英雄档案。点"开始冒险"时会有一段<span class="coach-highlight">铸造仪式</span>——这是你和角色建立情感的瞬间。此后，她的每一次命中、每一次失误，都将是你的故事。',
          unlock: { name: '初登冒险者名册', desc: '你的英雄已被记入编年史' },
          require: 'auto',
        },
      ],
    },
    {
      id: 'adventure',
      id_alt: 'adventure',
      idx: 3,
      glyph: '❧',
      title: '第一次跑团',
      desc: '对话、选择、投骰 —— 解决小酒馆的一场纠纷',
      duration: '约 5 分钟',
      steps: [
        {
          id: 'a-intro',
          coach: '冒险的 70% 时间不是砍杀，而是<span class="coach-highlight">对话与探索</span>。来，我给你一个场景：<br/><br/><i>黄昏，银谷村"蜡烛之烬"酒馆，壁炉噼啪作响。吧台老板揉着被打伤的手腕，朝你望来。"冒险者，对吧？来得正好——有三个混蛋刚洗劫了我的库房，就躲在码头仓库。500 金币，你愿意出手吗？"</i>',
          require: 'auto',
        },
        {
          id: 'a-choice',
          coach: '屏幕中会给你 3-6 个<span class="coach-highlight">对话选项</span>。有的标注 <span class="coach-key">[洞察·DC14]</span>——这是一次技能检定。数字是<span class="coach-highlight">难度等级</span>（DC）：越高越难。',
          glossary: {
            term: 'DC',
            pron: 'DIFFICULTY CLASS',
            def: '技能检定的目标数字。简单 10、中等 15、困难 20、极难 25。你的 d20 + 修正 ≥ DC 即成功。',
            example: '[洞察·DC14] = 你需要掷出 d20 + 感知修正 + 熟练（若熟练）≥ 14，才能看穿对方是否说谎。',
          },
          require: 'auto',
        },
        {
          id: 'a-preview',
          coach: '把鼠标悬停在选项上，会弹出<span class="coach-highlight">结果预告</span>——显示你的成功率、修正、以及可能的后果。这是帮你做决策的神器，而不是剧透。',
          tip: '成功率是基于你当前角色的属性实时计算的——同一个选项，战士和法师的数值可能天差地别。',
          require: 'auto',
        },
        {
          id: 'a-roll',
          coach: '选定后，如果有检定，屏幕中央会弹出 <span class="coach-highlight">d20 骰子</span>。它会真实翻滚几圈——这不是装饰，骰面的数字就是你的 d20 点数。',
          require: 'auto',
        },
        {
          id: 'a-result',
          coach: '结果显示如 <span class="coach-key">d20=14 +3 [熟练] = 17 vs DC14</span>——成功！我会根据成败续写故事：老板会给你更多情报，或者警告你"别打探"。<br/><br/><i>你的决定塑造世界。</i>',
          unlock: { name: '初入角色扮演', desc: '你已学会"扮演"而不只是"玩"' },
          require: 'auto',
        },
      ],
    },
    {
      id: 'combat',
      idx: 4,
      glyph: '⚔',
      title: '战斗的艺术',
      desc: '先攻、行动、移动、法术位 —— 打赢你的第一场仗',
      duration: '约 6 分钟',
      steps: [
        {
          id: 'b-intro',
          coach: '<i>你推开码头仓库的门——三个黑袍身影猛地回头。一个拔刀冲来，另一个举起法杖，第三个缩进阴影。</i><br/><br/>战斗！屏幕会切到战斗模式：<span class="coach-highlight">网格地图</span> + <span class="coach-highlight">先攻条</span> + <span class="coach-highlight">技能栏</span>。',
          require: 'auto',
        },
        {
          id: 'b-init',
          coach: '所有参战者掷 <span class="coach-highlight">先攻</span>（d20 + DEX 修正），从高到低排序。顶部的<span class="coach-highlight">先攻条</span>就是回合顺序——金色/绿色是盟友，红色是敌人，当前发光的那个是正在行动的。',
          glossary: {
            term: '先攻',
            pron: 'INITIATIVE',
            def: '决定回合顺序的 d20 检定。每场战斗开始时掷一次，排序生效到战斗结束。',
            example: '敏捷 16 的盗贼（+3）容易拿到前排先攻；笨重的重甲战士（+0 DEX）往往要后行动。',
          },
          require: 'auto',
        },
        {
          id: 'b-grid',
          coach: '每格代表<span class="coach-highlight">5 尺</span>（约 1.5 米）。你每回合的基础移动力是 <span class="coach-highlight">6 格 = 30 尺</span>。点击空格移动、点击敌人攻击。墙体 <span class="coach-key">█</span> 阻挡视线和通行。',
          require: 'auto',
        },
        {
          id: 'b-action',
          coach: '每回合你有 3 类"资源"：<br/>◆ <span class="coach-highlight">动作</span>（1 次）：攻击、施法、冲刺、闪避……<br/>◆ <span class="coach-highlight">附赠行动</span>（1 次）：战吼、副手攻击、治疗药剂……<br/>◆ <span class="coach-highlight">反应</span>（1 次）：借机攻击、护盾术……（可在他人回合触发）<br/><br/>外加<span class="coach-highlight">移动</span>不消耗动作。',
          tip: '右上角的三个圆点就是这三类资源。用掉一个就会变灰。',
          require: 'auto',
        },
        {
          id: 'b-threat',
          coach: '打开"<span class="coach-highlight">⚔ 威胁区</span>"开关——红色斜纹格是敌人的近战威胁范围。你若从威胁区走出（且未"脱离接战"），会触发<span class="coach-highlight">借机攻击</span>——对方免费砍你一刀。',
          glossary: {
            term: '借机攻击',
            pron: 'OPPORTUNITY ATTACK',
            def: '5e 核心规则之一：当你在敌人的近战范围内移动、且不是"脱离接战"时，该敌人可用反应对你攻击一次。',
            example: '盗贼从敌人身边直接撤退 → 被借机攻击；先"脱离接战"再移动 → 安全。',
          },
          require: 'auto',
        },
        {
          id: 'b-attack',
          coach: '攻击分两步：<br/>① <span class="coach-highlight">命中骰</span>——d20 + 攻击加值 vs 目标 AC。≥ AC 就命中。<br/>② <span class="coach-highlight">伤害骰</span>——武器对应骰子 + 能力修正（如长剑 1d8+STR）。<br/><br/>自然 20 = 暴击，伤害骰数量翻倍。',
          glossary: {
            term: 'AC',
            pron: 'ARMOR CLASS',
            def: '护甲等级。攻击者需掷出 d20 + 攻击加值 ≥ 你的 AC 才能命中。裸身 10 + DEX；链甲 16；板甲 18。',
            example: '目标 AC 15。你的攻击加值 +5。d20 需要掷出至少 10，才能命中（10+5=15）。',
          },
          require: 'auto',
        },
        {
          id: 'b-spell',
          coach: '法师/术士/邪术师用 <span class="coach-highlight">法术位</span> 施放法术——1 环法术位就像"子弹"，用完这回合这环没了。环数越高，法术越强（1 环魔法飞弹 → 3 环火球 → 5 环死云）。屏幕右侧会显示剩余法术位。',
          tip: 'AoE 法术（范围伤害）如火球——鼠标悬停法术名时，地图会显示<span class="coach-highlight">橙色半径圈</span>预览。',
          require: 'auto',
        },
        {
          id: 'b-end',
          coach: '打完或都用完资源，点<span class="coach-highlight">☰ 结束回合</span>把回合交给下一位。战斗直到一方全灭——或谈判/投降/逃走。<br/><br/><i>记住：最有趣的战斗不是 100% 赢，而是 60% 能输的紧张局面。</i>',
          unlock: { name: '首战告捷', desc: '你已掌握战斗的核心节奏' },
          require: 'auto',
        },
      ],
    },
  ],
}

// ═══════════════════════════════════════════════════════════
// ① 主页入口卡
// ═══════════════════════════════════════════════════════════
export function TutorialEntryCard({ progress = 0, total = 4, onOpen }) {
  return (
    <div className="tut-entry-card" onClick={onOpen}>
      <div className="tec-corner-br" />
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div className="tec-icon">✦</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="tec-kicker">◆ 新手指引 ◆</div>
          <div className="tec-title">圣物殿 · 启蒙</div>
          <div className="tec-sub">
            地下城主艾尔德林将从零开始，带你<br />
            铸造英雄、踏入第一场冒险与战斗。
          </div>
        </div>
      </div>
      <div className="tec-progress" aria-label="tutorial progress">
        {Array.from({ length: total }).map((_, i) => (
          <div key={i} className={`dot ${i < progress ? 'done' : i === progress ? 'current' : ''}`} />
        ))}
      </div>
      <div className="tec-cta">
        <span className="tec-meta">{progress}/{total} 章节 · 约 20 分钟</span>
        <button
          className="tec-btn"
          onClick={(e) => { e.stopPropagation(); onOpen?.() }}
        >
          {progress === 0 ? '开启教程 ►' : progress >= total ? '重温 ◌' : '继续 ►'}
        </button>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// ② 章节索引（全屏欢迎屏）
// ═══════════════════════════════════════════════════════════
function TutorialWelcome({ onPickChapter, onClose, progress = {} }) {
  const chs = TUTORIAL_CONTENT.chapters
  return (
    <div className="tut-overlay" role="dialog" aria-modal="true">
      <div className="tut-welcome">
        <div className="tw-ornament">✦ ❧ ✦</div>
        <div className="tw-kicker">◆ TUTORIAL · 启蒙圣所 ◆</div>
        <h2 className="tw-title">新冒险者指南</h2>
        <p className="tw-lead">
          欢迎，年轻的灵魂。<br />
          在踏入广阔的费伦之前，让我——地下城主艾尔德林——<br />
          引你走过骰子与命运交织的第一程。
        </p>

        <div className="tut-modules">
          {chs.map((c, i) => {
            const state = progress[c.id] || 'available'
            const locked = i > 0 && !progress[chs[i - 1].id]
            return (
              <div
                key={c.id}
                className={`tut-module ${locked ? 'locked' : ''} ${state === 'done' ? 'done' : ''}`}
                onClick={() => !locked && onPickChapter?.(c.id)}
              >
                <div className="tm-idx">{String(c.idx).padStart(2, '0')}</div>
                <div className="tm-glyph">{c.glyph}</div>
                <div className="tm-title">{c.title}</div>
                <div className="tm-desc">{c.desc}</div>
                <div className="tm-dur">⧗ {c.duration}</div>
              </div>
            )
          })}
        </div>

        <div className="tw-footer">
          <button className="btn-coach" onClick={onClose}>稍后再说</button>
          <button
            className="btn-coach primary"
            onClick={() => onPickChapter?.(chs[0].id)}
          >
            {Object.keys(progress).length ? '继续教程 ►' : '从第一章开始 ►'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// ③ Spotlight（带圆环 + 暗化遮罩）
// ═══════════════════════════════════════════════════════════
function TutorialSpotlight({ rect }) {
  const pad = 8
  if (!rect) {
    return (
      <div className="tut-spotlight">
        <div className="sp-mask" style={{ clipPath: 'none' }} />
      </div>
    )
  }
  const x = rect.x - pad, y = rect.y - pad, w = rect.w + pad * 2, h = rect.h + pad * 2
  const clipPath = `polygon(
    0 0, 100% 0, 100% 100%, 0 100%, 0 0,
    ${x}px ${y}px,
    ${x}px ${y + h}px,
    ${x + w}px ${y + h}px,
    ${x + w}px ${y}px,
    ${x}px ${y}px
  )`
  return (
    <div className="tut-spotlight">
      <div className="sp-mask" style={{ clipPath }} />
      <div className="sp-ring" style={{ left: x, top: y, width: w, height: h }} />
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// ④ Coach 对话气泡
// ═══════════════════════════════════════════════════════════
function TutorialCoach({ step, stepIdx, total, rect, onPrev, onNext, onSkip }) {
  const pos = useMemo(() => {
    if (!rect) {
      return { left: window.innerWidth / 2 - 170, top: window.innerHeight - 320, dir: null }
    }
    const W = 340, H = 220, gap = 24
    const dir = step.dir && step.dir !== 'auto'
      ? step.dir
      : (rect.x + rect.w + W + gap < window.innerWidth ? 'left'
        : rect.x - W - gap > 0 ? 'right'
        : rect.y + rect.h + H + gap < window.innerHeight ? 'top' : 'bottom')
    let left, top
    if (dir === 'left')   { left = rect.x + rect.w + gap; top = rect.y + rect.h / 2 - H / 2 }
    if (dir === 'right')  { left = rect.x - W - gap;      top = rect.y + rect.h / 2 - H / 2 }
    if (dir === 'top')    { left = rect.x + rect.w / 2 - W / 2; top = rect.y + rect.h + gap }
    if (dir === 'bottom') { left = rect.x + rect.w / 2 - W / 2; top = rect.y - H - gap }
    left = Math.max(16, Math.min(window.innerWidth - W - 16, left))
    top  = Math.max(80, Math.min(window.innerHeight - H - 16, top))
    return { left, top, dir }
  }, [rect, step.dir])

  const isHTML = typeof step.coach === 'string' && step.coach.includes('<')

  return (
    <div className="tut-coach" data-dir={pos.dir} style={{ left: pos.left, top: pos.top }}>
      <div className="coach-head">
        <div className="coach-avatar">艾</div>
        <div>
          <div className="coach-name">艾尔德林</div>
          <div className="coach-role">地下城主 · 引导者</div>
        </div>
        <div className="coach-step">{stepIdx + 1} / {total}</div>
      </div>
      <div className="coach-body">
        {isHTML
          ? <span dangerouslySetInnerHTML={{ __html: step.coach }} />
          : step.coach}
      </div>
      {step.action && (
        <div style={{
          marginTop: 10, padding: '6px 10px',
          background: 'rgba(240,208,96,.1)',
          borderLeft: '2px solid var(--amber)',
          fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--amber)',
        }}>
          ➤ {step.action}
        </div>
      )}
      {step.tip && <div className="coach-tip-hint" dangerouslySetInnerHTML={{ __html: step.tip }} />}
      <div className="coach-nav">
        <div className="coach-progress">
          {Array.from({ length: total }).map((_, i) => (
            <div key={i} className={`p-dot ${i < stepIdx ? 'done' : i === stepIdx ? 'current' : ''}`} />
          ))}
        </div>
        <div className="coach-actions">
          {stepIdx > 0 && <button className="btn-coach" onClick={onPrev}>◄ 上一步</button>}
          {step.require !== 'click' && step.require !== 'custom' && (
            <button className="btn-coach primary" onClick={onNext}>
              {stepIdx + 1 >= total ? '完成 ✓' : '下一步 ►'}
            </button>
          )}
          {(step.require === 'click' || step.require === 'custom') && (
            <button className="btn-coach" onClick={onSkip} title="跳过此步">跳过 ↷</button>
          )}
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// ⑤ Spotlight + Coach 组合（runner）
// ═══════════════════════════════════════════════════════════
function TutorialRunner({ chapterId, onExit, onChapterDone }) {
  const chapter = TUTORIAL_CONTENT.chapters.find(c => c.id === chapterId)
  const [stepIdx, setStepIdx] = useState(0)
  const [rect, setRect] = useState(null)
  const [unlockMsg, setUnlockMsg] = useState(null)
  const step = chapter?.steps[stepIdx]

  // 重置章节切换时的 stepIdx
  useEffect(() => { setStepIdx(0) }, [chapterId])

  // 定位 target 元素
  useEffect(() => {
    if (!step?.target) { setRect(null); return }
    const locate = () => {
      const el = document.querySelector(step.target)
      if (!el) { setRect(null); return }
      const r = el.getBoundingClientRect()
      setRect({ x: r.left, y: r.top, w: r.width, h: r.height })
    }
    locate()
    const el = document.querySelector(step.target)
    const obs = el ? new ResizeObserver(locate) : null
    if (el && obs) obs.observe(el)
    window.addEventListener('resize', locate)
    window.addEventListener('scroll', locate, true)
    const tid = setInterval(locate, 300) // 兜底
    return () => {
      if (obs) obs.disconnect()
      window.removeEventListener('resize', locate)
      window.removeEventListener('scroll', locate, true)
      clearInterval(tid)
    }
  }, [step?.target])

  // 进入 / 离开 callbacks + 成就解锁
  useEffect(() => {
    step?.onEnter?.()
    if (step?.unlock) {
      setUnlockMsg(step.unlock)
      const t = setTimeout(() => setUnlockMsg(null), 3200)
      return () => { clearTimeout(t); step?.onLeave?.() }
    }
    return () => step?.onLeave?.()
  }, [chapterId, stepIdx])

  // 暴露给场景代码的 window.tutorial.next()
  useEffect(() => {
    window.tutorial = window.tutorial || {}
    window.tutorial.next = () => {
      setStepIdx(i => {
        if (i + 1 >= (chapter?.steps.length || 0)) { onChapterDone?.(chapter?.id); return i }
        return i + 1
      })
    }
    window.tutorial.prev = () => setStepIdx(i => Math.max(0, i - 1))
    window.tutorial.exit = () => onExit?.()
    return () => {
      if (window.tutorial) {
        delete window.tutorial.next
        delete window.tutorial.prev
        delete window.tutorial.exit
      }
    }
  }, [chapter, onChapterDone, onExit])

  // click-require：监听 target 点击自动推进
  useEffect(() => {
    if (step?.require !== 'click' || !step.target) return
    const el = document.querySelector(step.target)
    if (!el) return
    const handler = () => window.tutorial?.next?.()
    el.addEventListener('click', handler, { once: true })
    return () => el.removeEventListener('click', handler)
  }, [stepIdx, step?.require, step?.target])

  if (!chapter || !step) return null

  const total = chapter.steps.length

  return (
    <>
      {/* 顶部 HUD */}
      <div className="tut-hud">
        <span className="h-label">◆ 教程</span>
        <span className="h-title">{chapter.glyph} {chapter.title}</span>
        <div className="h-steps">
          {chapter.steps.map((s, i) => (
            <div key={s.id} className={`st ${i < stepIdx ? 'done' : i === stepIdx ? 'current' : ''}`} />
          ))}
        </div>
        <button className="h-exit" onClick={onExit}>✕ 退出</button>
      </div>

      {/* 当前目标横幅 */}
      {step.goal && (
        <div className="tut-goal-banner" key={step.id + '-g'}>
          <span className="gb-icon">✦</span>
          <span className="gb-label">当前目标</span>
          <span className="gb-text">{step.goal}</span>
        </div>
      )}

      {/* Spotlight */}
      <TutorialSpotlight rect={rect} />

      {/* 术语浮窗 */}
      {step.glossary && rect && (
        <div
          className="tut-glossary"
          style={{
            left: Math.min(window.innerWidth - 280, rect.x + rect.w + 16),
            top: Math.max(20, rect.y),
          }}
        >
          <div className="g-term">{step.glossary.term}</div>
          {step.glossary.pron && <div className="g-pron">{step.glossary.pron}</div>}
          <div className="g-def">{step.glossary.def}</div>
          {step.glossary.example && <div className="g-example">{step.glossary.example}</div>}
        </div>
      )}

      {/* 无 target 但有 glossary：居中右下角展示 */}
      {step.glossary && !rect && (
        <div
          className="tut-glossary"
          style={{ right: 32, top: 120, left: 'auto' }}
        >
          <div className="g-term">{step.glossary.term}</div>
          {step.glossary.pron && <div className="g-pron">{step.glossary.pron}</div>}
          <div className="g-def">{step.glossary.def}</div>
          {step.glossary.example && <div className="g-example">{step.glossary.example}</div>}
        </div>
      )}

      {/* Coach 气泡 */}
      <TutorialCoach
        step={step}
        stepIdx={stepIdx}
        total={total}
        rect={rect}
        onPrev={() => setStepIdx(i => Math.max(0, i - 1))}
        onNext={() => {
          if (stepIdx + 1 >= total) onChapterDone?.(chapter.id)
          else setStepIdx(i => i + 1)
        }}
        onSkip={onExit}
      />

      {/* 小成就 */}
      {unlockMsg && (
        <div className="tut-unlock" key={unlockMsg.name}>
          <div className="u-icon">✦</div>
          <div>
            <div className="u-kicker">成就解锁</div>
            <div className="u-name">{unlockMsg.name}</div>
            <div className="u-desc">{unlockMsg.desc}</div>
          </div>
        </div>
      )}
    </>
  )
}

// ═══════════════════════════════════════════════════════════
// ⑥ 顶层：TutorialHost — 管理 welcome / runner 切换
// ═══════════════════════════════════════════════════════════
export function TutorialHost({ open, onClose, initialChapter }) {
  const [mode, setMode] = useState('welcome') // 'welcome' | 'runner'
  const [activeChapter, setActiveChapter] = useState(initialChapter || null)
  const [progress, setProgress] = useState(() => {
    try { return JSON.parse(localStorage.getItem('tutorial_progress') || '{}') }
    catch { return {} }
  })

  useEffect(() => {
    if (!open) return
    if (initialChapter) { setActiveChapter(initialChapter); setMode('runner') }
    else setMode('welcome')
  }, [open, initialChapter])

  const saveProgress = (next) => {
    setProgress(next)
    try { localStorage.setItem('tutorial_progress', JSON.stringify(next)) } catch (e) {}
  }

  if (!open) return null

  if (mode === 'welcome') {
    return (
      <TutorialWelcome
        progress={progress}
        onClose={onClose}
        onPickChapter={(id) => { setActiveChapter(id); setMode('runner') }}
      />
    )
  }
  if (mode === 'runner' && activeChapter) {
    return (
      <TutorialRunner
        chapterId={activeChapter}
        onExit={() => setMode('welcome')}
        onChapterDone={(id) => {
          const next = { ...progress, [id]: 'done' }
          saveProgress(next)
          setMode('welcome')
        }}
      />
    )
  }
  return null
}

// 导出辅助：查询进度总数
export function getTutorialProgress() {
  try {
    const raw = JSON.parse(localStorage.getItem('tutorial_progress') || '{}')
    return Object.keys(raw).length
  } catch { return 0 }
}
