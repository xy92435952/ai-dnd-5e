// DnD 5e SRD 数据库 — 种族 / 职业 / 子职 / 技能 / 背景
// 用于角色创建页面的信息弹窗和选择逻辑

// ══════════════════════════════════════════════════════════
// 种族
// ══════════════════════════════════════════════════════════
export const RACE_INFO = {
  'Human': {
    zh: '人类',
    description: '人类是人间界最多见也最充满野心的种族。他们适应力极强，能在各种环境中生存，并在冒险生涯中展现惊人的多样性。',
    speed: 30, size: '中型',
    traits: [
      { name: '全能', desc: '所有能力值 +1，没有特别突出但无明显短板' },
      { name: '技能特长', desc: '额外习得一项技能熟练，职业选择更灵活' },
      { name: '额外语言', desc: '除通用语外，可再学习一门语言' },
    ],
    playstyle: '全能型选手，适合想要极大发挥职业特性的玩家，对初学者友好。',
  },
  'Elf': {
    zh: '精灵',
    description: '精灵是神秘而充满魔力的种族，寿命极长，天生亲近自然与魔法。他们动作轻盈，感知敏锐，拥有令其他种族羡慕的优雅。',
    speed: 30, size: '中型',
    traits: [
      { name: '黑暗视觉', desc: '60尺范围内可在黑暗中视物，视黑暗为弱光' },
      { name: '精灵感知', desc: '搜寻技能 +2，专注检定有优势（高精灵/月精灵）' },
      { name: '精灵血脉', desc: '免疫魅惑，魔法无法使你入睡' },
      { name: '恍然出神', desc: '无需睡眠，4小时冥想即可获得长休效果' },
      { name: '武器训练', desc: '精通长剑、短剑、短弓、长弓' },
    ],
    playstyle: '法师/游侠的绝佳选择。灵敏高感知，适合远程或施法型角色。',
  },
  'Dwarf': {
    zh: '矮人',
    description: '矮人是以坚韧和耐力闻名的古老种族。他们深居山岳，精通锻造，拥有对毒素的天然抗性和在石地行进的本能。',
    speed: 25, size: '中型',
    traits: [
      { name: '黑暗视觉', desc: '60尺暗视' },
      { name: '矮人坚韧', desc: '对毒素伤害有抗性，对毒素效果的豁免有优势' },
      { name: '矮人战斗训练', desc: '精通战斧、手斧、轻锤、重锤' },
      { name: '石头鉴别', desc: '鉴定石工作品时能力检定有优势' },
      { name: '速度不受减缓', desc: '即使穿重甲，速度也不受减缓' },
    ],
    playstyle: '适合圣武士、战士、牧师。体质加成让你成为超级坦克，永远不担心毒素。',
  },
  'Halfling': {
    zh: '半身人',
    description: '半身人是快乐而脚踏实地的小个子种族，喜欢舒适的家园和美食。但别低估他们——遇到危险时，半身人展现出令人惊叹的韧性和好运气。',
    speed: 25, size: '小型',
    traits: [
      { name: '幸运', desc: '攻击、能力检定或豁免掷出1时，重掷并使用新结果' },
      { name: '勇敢', desc: '对恐惧效果的豁免有优势' },
      { name: '半身人灵活', desc: '可穿越任何比你大的生物的空间' },
    ],
    playstyle: '游荡者最佳搭档。"幸运"特性是游戏中最强的被动之一，有效避免灾难性失败。',
  },
  'Half-Elf': {
    zh: '半精灵',
    description: '半精灵融合了人类的野心与精灵的感知，他们在人类社会和精灵部落之间游走，两边都能融入，却又永远是局外人。',
    speed: 30, size: '中型',
    traits: [
      { name: '黑暗视觉', desc: '60尺暗视' },
      { name: '精灵血脉', desc: '免疫魅惑，魔法无法使你入睡' },
      { name: '技能多才', desc: '额外习得两项技能熟练，可自由选择' },
      { name: '综合能力加成', desc: '魅力 +2 外，另有两项能力值各 +1（可自选）' },
    ],
    playstyle: '吟游诗人和术士的顶级选择。高魅力 + 额外技能让你在社交和战斗都能出彩。',
  },
  'Half-Orc': {
    zh: '半兽人',
    description: '半兽人继承了兽人的强大体魄与人类的适应力。他们往往被偏见所困扰，但在战场上，他们的力量和凶猛让敌人胆寒。',
    speed: 30, size: '中型',
    traits: [
      { name: '黑暗视觉', desc: '60尺暗视' },
      { name: '凶悍', desc: '造成伤害时可以多掷一个骰子并取最高结果' },
      { name: '兽人耐力', desc: '每场战斗一次：HP降至0时可维持1HP继续战斗' },
      { name: '恐吓熟练', desc: '自动获得恐吓技能熟练' },
    ],
    playstyle: '野蛮人和战士的天然搭档。兽人耐力是最好的救命技能，让你在关键时刻多一次机会。',
  },
  'Dragonborn': {
    zh: '龙裔',
    description: '龙裔是远古龙之后裔，以鳞甲之身承载着龙族血脉的荣耀与力量。他们与龙同类，却走在自己的道路上。',
    speed: 30, size: '中型',
    traits: [
      { name: '龙族血脉', desc: '根据血统选择一种伤害类型（火焰/闪电/寒冰等）' },
      { name: '吐息武器', desc: '动作：喷吐伤害（锥形或直线），豁免失败则受全伤' },
      { name: '伤害抗性', desc: '对血统对应的伤害类型有抗性' },
    ],
    playstyle: '术士/圣武士搭配效果极佳。吐息武器提供额外的范围伤害选项，独特而有存在感。',
  },
  'Tiefling': {
    zh: '魔裔',
    description: '魔裔是与恶魔血脉相连的种族，额上长角，尾巴摇曳，天生携带阴暗烙印。但这份黑暗血脉也赋予他们强大的魔法能力。',
    speed: 30, size: '中型',
    traits: [
      { name: '黑暗视觉', desc: '60尺暗视' },
      { name: '地狱血脉', desc: '对火焰伤害有抗性' },
      { name: '地狱遗产', desc: '获得若干天生法术：魔法技巧(戏法)、地狱烈焰(3级)、黑暗命令(5级)' },
    ],
    playstyle: '邪术师/法师的主题选择。地狱遗产提供额外法术而无需消耗法术位，魅力加成辅助施法。',
  },
}

// ══════════════════════════════════════════════════════════
// 职业
// ══════════════════════════════════════════════════════════
export const CLASS_INFO = {
  'Barbarian': {
    zh: '野蛮人', hit_die: 'd12',
    primary_ability: '力量',
    armor: '轻甲、中甲、盾牌',
    weapons: '所有简单武器和军事武器',
    description: '野蛮人是原始的战斗机器，通过进入狂暴状态爆发惊人的战斗力。他们不依赖盔甲，而是凭借本能与体质保护自己。',
    subclass_unlock: 3, subclass_label: '原始路径',
    features: [
      { level: 1, name: '狂暴', desc: '附赠动作：进入狂暴，近战伤害+2，对力量/体质检定有优势，对物理伤害有抗性，持续1分钟' },
      { level: 1, name: '无甲防御', desc: '不穿甲时，AC = 10 + 敏捷调整 + 体质调整' },
      { level: 2, name: '鲁莽攻击', desc: '放弃优势换取敌人对你的攻击优势，获得本次攻击优势' },
      { level: 5, name: '额外攻击', desc: '每回合可攻击两次' },
      { level: 7, name: '本能闪避', desc: '可用反应将受到的某些伤害减半' },
    ],
    subclasses: [
      { name: 'Berserker', zh: '狂战士', description: '纯粹的战斗狂热，狂暴时可用附赠动作额外攻击，免疫魅惑和恐惧，极致的暴力机器。' },
      { name: 'Totem Warrior', zh: '图腾战士', description: '从精神动物（熊/鹰/狼）获得力量，兼具小队辅助和强力单体战斗能力。' },
      { name: 'Storm Herald', zh: '风暴先驱', description: '化身自然力量，可在周围释放风暴、沙漠高温或冻原严寒，持续环境伤害。' },
      { name: 'Zealot', zh: '狂热者', description: '神灵赐予的战斗意志，死亡后可被免费复活，攻击可附加神圣/放射伤害。' },
    ],
  },
  'Bard': {
    zh: '吟游诗人', hit_die: 'd8',
    primary_ability: '魅力',
    armor: '轻甲',
    weapons: '简单武器、手弩、长剑、细剑、短剑',
    description: '吟游诗人以音乐和故事为武器，既能鼓舞同伴也能瓦解敌人意志。他们是知识渊博的万能选手，支援能力极强。',
    subclass_unlock: 3, subclass_label: '诗人学院',
    features: [
      { level: 1, name: '施法', desc: '魅力为施法属性，已知法术数量随等级增长，全施法者法术位' },
      { level: 1, name: '吟游鼓励', desc: '用附赠动作给盟友一枚灵感骰（d6起），可加到检定或豁免' },
      { level: 2, name: '万能技艺', desc: '将半数熟练加值应用于所有未熟练的技能' },
      { level: 5, name: '字里乾坤', desc: '扩展可知晓法术列表，偷学其他职业法术' },
    ],
    subclasses: [
      { name: 'Lore', zh: '知识学院', description: '专注于操控和控制法术，获取其他职业的秘密，通过切割话语削弱敌方攻击。极强的控场和信息收集能力。' },
      { name: 'Valor', zh: '英勇学院', description: '武装起来的吟游诗人，可穿中甲，获得军事武器熟练，后期可在攻击时施放法术。' },
      { name: 'Glamour', zh: '魅惑学院', description: '专注于魅惑和幻觉，给队友提供临时HP和移动力，拥有强大的群体控制。' },
      { name: 'Swords', zh: '剑术学院', description: '战斗型诗人，通过花式剑术(Blade Flourish)造成额外伤害，可同时进行近战攻击和施法。' },
    ],
  },
  'Cleric': {
    zh: '牧师', hit_die: 'd8',
    primary_ability: '感知',
    armor: '轻甲、中甲、盾牌（部分领域重甲）',
    weapons: '所有简单武器',
    description: '牧师是神明的代理人，通过祈祷获得神圣法术。他们能治疗盟友、伤害亡灵，并根据所侍奉的神灵展现截然不同的战斗风格。',
    subclass_unlock: 1, subclass_label: '神圣领域',
    features: [
      { level: 1, name: '施法', desc: '感知为施法属性，全施法者，每次长休后从所有已准备法术中选择施法' },
      { level: 1, name: '神圣领域特性', desc: '根据选择的领域获得独特能力和奖励法术' },
      { level: 2, name: '引导神力', desc: '每次短休后可用一次，触发所选领域的神圣效果' },
      { level: 5, name: '消灭亡灵', desc: '引导神力可直接消灭低CR的亡灵生物' },
    ],
    subclasses: [
      { name: 'Life', zh: '生命领域', description: '治疗专精。治疗法术效果增强，获得重甲熟练，是游戏中最强的治疗者。' },
      { name: 'Light', zh: '光明领域', description: '攻击型牧师，专注于光明和火焰系法术，拥有强大的输出能力。' },
      { name: 'War', zh: '战争领域', description: '近战型牧师，获得重甲和军事武器熟练，可额外攻击，冲锋陷阵的神圣战士。' },
      { name: 'Knowledge', zh: '知识领域', description: '信息与控制，可获取其他技能熟练，读心，控制目标思想。' },
      { name: 'Trickery', zh: '诡计领域', description: '幻觉与隐身，召唤分身，给盟友提供隐形，适合潜行和偷袭风格。' },
      { name: 'Nature', zh: '自然领域', description: '自然系法术专精，可驾驭野兽，对自然系伤害有抗性。' },
      { name: 'Tempest', zh: '暴风领域', description: '雷霆与闪电。最大化雷电伤害，将敌人击退，是攻击性最强的牧师领域之一。' },
    ],
  },
  'Druid': {
    zh: '德鲁伊', hit_die: 'd8',
    primary_ability: '感知',
    armor: '轻甲、中甲、盾牌（无金属）',
    weapons: '棍棒、匕首、投矛、标枪、权杖、镰刀、短剑、木棍',
    description: '德鲁伊是自然力量的守护者，能够变身为野兽并施放强大的自然法术。他们是多才多艺的法术使用者，在荒野中如鱼得水。',
    subclass_unlock: 2, subclass_label: '德鲁伊圈',
    features: [
      { level: 1, name: '施法', desc: '感知为施法属性，全施法者，每次长休后重新准备法术' },
      { level: 1, name: '德鲁伊语', desc: '秘密语言，可在普通言语中传递隐藏信息' },
      { level: 2, name: '野性形态', desc: '每次短休后可变身为特定野兽，等级越高可变身更强大的生物' },
    ],
    subclasses: [
      { name: 'Land', zh: '大地圈', description: '增强施法能力，根据地形（海岸/沙漠/森林/草原等）获取额外法术，拥有自然恢复补充法术位。' },
      { name: 'Moon', zh: '月亮圈', description: '专精变身，可变成更强大的野兽（包括元素体），战斗中可用附赠动作变身，极强的肉盾能力。' },
      { name: 'Spores', zh: '孢子圈', description: '通过孢子影响周围生物，可使死去的生物爬起来继续战斗，毒素和腐烂系主题。' },
    ],
  },
  'Fighter': {
    zh: '战士', hit_die: 'd10',
    primary_ability: '力量 或 敏捷',
    armor: '所有盔甲和盾牌',
    weapons: '所有简单武器和军事武器',
    description: '战士是各类武器和战斗风格的大师。他们不依赖魔法，以纯粹的技艺和坚韧征服战场，拥有游戏中最高的攻击频率。',
    subclass_unlock: 3, subclass_label: '武学传承',
    features: [
      { level: 1, name: '战斗风格', desc: '选择专精：防御(+1AC)/决斗(+2近战伤害)/双武器/箭矢大师/守护式/神射手' },
      { level: 1, name: '第二口气', desc: '附赠动作：恢复 1d10+战士等级 点HP，每次短休后重置' },
      { level: 2, name: '行动涌现', desc: '可额外使用一次攻击动作，冲刺/撤退/扑倒/缴械或协助' },
      { level: 5, name: '额外攻击', desc: '每个攻击动作攻击2次（11级3次，20级4次）' },
      { level: 9, name: '坚韧', desc: '可以重掷一次失败的能力检定' },
      { level: 11, name: '优越攻击', desc: '用一个攻击动作进行3次攻击' },
    ],
    subclasses: [
      { name: 'Champion', zh: '斗士', description: '简单有效的近战强化：暴击范围扩展至19-20，超凡体格获得额外技能，是最纯粹的战斗机器。' },
      { name: 'Battle Master', zh: '战争大师', description: '通过优越骰执行特殊动作（缴械/推倒/虚晃等），战术灵活性极强，复杂但有深度。' },
      { name: 'Eldritch Knight', zh: '魔战士', description: '融合战斗与法术：专精防御和变化系魔法，可将武器召回，后期可在攻击中施法，法战合一。' },
      { name: 'Samurai', zh: '武士', description: '意志力驱动：每天有限次获得攻击优势，对魅力/感知豁免有熟练加成，坚韧和荣誉的象征。' },
    ],
  },
  'Monk': {
    zh: '武僧', hit_die: 'd8',
    primary_ability: '敏捷 和 感知',
    armor: '无（无甲防御：10+敏捷+感知）',
    weapons: '简单武器、短剑',
    description: '武僧通过内功修炼"气"的力量，徒手战斗也能造成惊人伤害，还能以超自然的速度移动，施展令人叹服的武术。',
    subclass_unlock: 3, subclass_label: '武道传统',
    features: [
      { level: 1, name: '武功', desc: '徒手或简单武器伤害提升（d4起），可用敏捷代替力量进行攻击' },
      { level: 1, name: '无甲防御', desc: 'AC = 10 + 敏捷调整 + 感知调整' },
      { level: 2, name: '气', desc: '每次短休后恢复气值，可花气使用附赠攻击/耐力/闪步/震慑打击' },
      { level: 5, name: '额外攻击', desc: '每回合攻击两次' },
      { level: 5, name: '震慑打击', desc: '花1气点：攻击命中后目标失去剩余动作并倒地' },
    ],
    subclasses: [
      { name: 'Open Hand', zh: '虚空之手', description: '纯粹的肉搏，以气为武器击飞/推倒/定住敌人，后期可恢复自身HP，终极形态触摸消灭魔法效果。' },
      { name: 'Shadow', zh: '暗影之道', description: '潜行型武僧，可花气隐身/传送/制造黑暗，适合暗杀风格，配合游荡者绝妙。' },
      { name: 'Four Elements', zh: '四象之道', description: '元素法术型武僧，花气施放火球/水流/土墙等，元素法术使用者的武术版本。' },
      { name: 'Drunken Master', zh: '醉拳大师', description: '混乱的战斗风格，敌人难以预测你的动作，每次击杀后可移动，用气恢复行动力。' },
    ],
  },
  'Paladin': {
    zh: '圣武士', hit_die: 'd10',
    primary_ability: '力量 和 魅力',
    armor: '所有盔甲和盾牌',
    weapons: '所有简单武器和军事武器',
    description: '圣武士是神圣誓约的守护者，融合了战士的战斗力和牧师的神圣力量。他们在近战中无比强大，并能以圣洁之光治愈同伴。',
    subclass_unlock: 3, subclass_label: '神圣誓约',
    features: [
      { level: 1, name: '神圣感知', desc: '动作：感知60尺内的邪恶/善良/中立，以及神圣区域，持续10分钟' },
      { level: 1, name: '圣手', desc: '每次长休后充能，用手触碰治愈生命值（圣武士等级×5点，可分配）' },
      { level: 2, name: '战斗风格', desc: '专精防御或决斗风格' },
      { level: 2, name: '施法', desc: '魅力为施法属性，半施法者，誓约决定额外法术' },
      { level: 2, name: '神圣打击', desc: '消耗法术位：命中时附加 Xd8 放射伤害，是游戏中最强的爆发伤害之一' },
      { level: 5, name: '额外攻击', desc: '每回合攻击两次' },
    ],
    subclasses: [
      { name: 'Devotion', zh: '虔誠誓约', description: '经典圣骑士，神圣武器附魔、神圣光环驱散黑暗，防御和治疗能力出色的全能型。' },
      { name: 'Ancients', zh: '远古誓约', description: '守护自然与生命的绿骑士。对法术有抗性，治愈能力强，拥有自然系主题法术。' },
      { name: 'Vengeance', zh: '复仇誓约', description: '追猎恶人的圣武士。获得追踪目标能力，攻击有优势，可以传送到标记目标旁，高输出型。' },
      { name: 'Glory', zh: '荣耀誓约', description: '激励同伴的光辉战士，给盟友提供临时HP，提升小队机动性，领袖风格。' },
    ],
  },
  'Ranger': {
    zh: '游侠', hit_die: 'd10',
    primary_ability: '敏捷 和 感知',
    armor: '轻甲、中甲、盾牌',
    weapons: '所有简单武器和军事武器',
    description: '游侠是荒野中的猎人和探路者，擅长远程攻击和追踪。他们有限度的法术能力提供了额外的工具，特别是针对特定类型的敌人。',
    subclass_unlock: 3, subclass_label: '游侠传承',
    features: [
      { level: 1, name: '最爱敌人', desc: '选择一种敌人类型（巨兽/魔鬼/亡灵等），对其追踪、知识检定有优势' },
      { level: 1, name: '自然探索者', desc: '在特定地形中有多种便利（双倍移速不迷路、获取双倍食物等）' },
      { level: 2, name: '战斗风格', desc: '专精箭矢大师/远程攻击额外加值/双武器' },
      { level: 2, name: '施法', desc: '感知为施法属性，半施法者' },
      { level: 5, name: '额外攻击', desc: '每回合攻击两次' },
    ],
    subclasses: [
      { name: 'Hunter', zh: '猎手', description: '通用型猎手。选择特化方向：对抗巨型目标/群体伤害/防御反击，高度可定制的输出型游侠。' },
      { name: 'Beast Master', zh: '驯兽师', description: '与动物伙伴共同战斗。动物伙伴可执行攻击，随等级成长，适合喜欢"人兽搭档"风格的玩家。' },
      { name: 'Gloom Stalker', zh: '暗域潜行者', description: '黑暗中的杀手，在黑暗中不可见，先攻额外高，第一回合可以多攻击一次，极强的开场爆发。' },
      { name: 'Swarmkeeper', zh: '虫群之主', description: '被一群微小生物环绕，可用虫群推动/拉扯敌人，独特的战场控制风格。' },
    ],
  },
  'Rogue': {
    zh: '游荡者', hit_die: 'd8',
    primary_ability: '敏捷',
    armor: '轻甲',
    weapons: '简单武器、手弩、长剑、细剑、短剑',
    description: '游荡者是机敏的专家，精通偷袭和利用敌人弱点。他们的偷袭技能使一次攻击造成的伤害足以决定战斗，同时他们在各类技能上都很出色。',
    subclass_unlock: 3, subclass_label: '奸猾原型',
    features: [
      { level: 1, name: '专技', desc: '选择两项技能或盗贼工具，熟练加值翻倍（6级再选两项）' },
      { level: 1, name: '偷袭', desc: '在有优势或盟友相邻时，攻击附加额外骰子伤害（1d6/2级提升一档）' },
      { level: 1, name: '盗贼行语', desc: '秘密行话，传递隐藏信息' },
      { level: 2, name: '狡猾动作', desc: '附赠动作：冲刺/撤退/躲藏' },
      { level: 5, name: '闪避', desc: '敏捷豁免成功则受0伤害（失败仍减半）' },
    ],
    subclasses: [
      { name: 'Thief', zh: '窃贼', description: '纯粹的窃贼技艺：快手（附赠动作使用物品）、超级闪避（临时飞行）、运用魔法物品。' },
      { name: 'Assassin', zh: '刺客', description: '先手爆发型。潜行状态对意外攻击的目标造成暴击，可伪装身份，毒药使用专家。' },
      { name: 'Arcane Trickster', zh: '奥法骗徒', description: '融合魔法的游荡者，施法为智力，专精幻术和附魔，用魔法辅助偷袭和逃脱。' },
      { name: 'Swashbuckler', zh: '剑客', description: '魅力型近战，单挑能力极强，不需要优势即可偷袭（只需旁边没有其他敌人），风流倜傥的决斗者。' },
    ],
  },
  'Sorcerer': {
    zh: '术士', hit_die: 'd6',
    primary_ability: '魅力',
    armor: '无',
    weapons: '短弩、匕首、标枪、轻锤、木棍',
    description: '术士的魔力天生流淌在血液中，源自龙族、野蛮魔法或远古血统。他们已知法术数量有限，但"术法调整"机制让他们能灵活变通每一个法术。',
    subclass_unlock: 1, subclass_label: '术法之源',
    features: [
      { level: 1, name: '施法', desc: '魅力为施法属性，全施法者，术法之源赋予额外能力' },
      { level: 2, name: '术法源点', desc: '可将法术位转换为源点或将源点转换为法术位' },
      { level: 2, name: '术法调整', desc: '用源点改变法术效果：双倍法术(隐法)/无声施法/远距施法(增能)/强化效果等' },
      { level: 20, name: '法力喷涌', desc: '每轮可凭空生成4级或更低的法术位' },
    ],
    subclasses: [
      { name: 'Draconic', zh: '龙族血脉', description: '龙族血脉赋予天然护甲（无甲AC=13+敏捷），强化选定属性的法术伤害，后期可展翅飞翔。' },
      { name: 'Wild Magic', zh: '野蛮魔法', description: '不稳定的魔法爆发，法术施放后可能触发随机效果，但也能获得强力的"潮汐混沌"额外施法。' },
      { name: 'Storm', zh: '风暴血脉', description: '电和雷系伤害强化，获得移动力，后期可以飞行，风暴元素主题。' },
      { name: 'Divine Soul', zh: '神圣灵魂', description: '获取牧师完整法术列表，融合神圣与奥术，是游戏中法术储备最丰富的施法职业之一。' },
    ],
  },
  'Warlock': {
    zh: '邪术师', hit_die: 'd8',
    primary_ability: '魅力',
    armor: '轻甲',
    weapons: '所有简单武器',
    description: '邪术师通过与强大存在（恶魔/精灵/旧神等）签订契约获得力量。独特的"契约魔法"法术位每次短休即可恢复，戏法以魅力为攻击属性。',
    subclass_unlock: 1, subclass_label: '彼方恩主',
    features: [
      { level: 1, name: '契约魔法', desc: '法术位数量少（1-4个）但每次短休恢复，法术等级随等级提升（永远使用最高环）' },
      { level: 1, name: '彼方恩主特性', desc: '根据恩主获得不同的专属能力和额外法术' },
      { level: 2, name: '邪术', desc: '选择强化戏法或法术的永久被动效果（武器爆发/驱邪/心灵感应等数十种）' },
      { level: 3, name: '契约秘法', desc: '选择契约馈赠：秘术书/契约武器/熟悉者，深度定制施法风格' },
    ],
    subclasses: [
      { name: 'Fiend', zh: '恶魔', description: '最强的邪术师恩主。杀死敌人后获得临时HP，超强法术列表（火球/范围AOE），后期可抵御各种伤害。' },
      { name: 'Archfey', zh: '大精灵', description: '魅惑与恐惧大师，可使目标魅惑或恐惧，逃脱危机时可在视野内传送。迷幻且难以预测。' },
      { name: 'Great Old One', zh: '旧日支配者', description: '心灵感应与触手系：读心/传递心灵信息，触手法术，后期可进入旁观者思维，克苏鲁主题。' },
      { name: 'Hexblade', zh: '魔剑', description: '魅力替代力量进行武器攻击，近战型邪术师，能穿重甲，是最强的多职业搭档之一。' },
    ],
  },
  'Wizard': {
    zh: '法师', hit_die: 'd6',
    primary_ability: '智力',
    armor: '无',
    weapons: '短弩、匕首、标枪、轻锤、木棍',
    description: '法师是法术学习的巅峰，依靠智慧和研究掌握世界上最广泛的法术。他们的法术书可以不断扩充，在高等级时拥有无与伦比的魔法广度。',
    subclass_unlock: 2, subclass_label: '奥法传承',
    features: [
      { level: 1, name: '施法', desc: '智力为施法属性，全施法者，法术书记录法术，每次长休后准备法术' },
      { level: 1, name: '奥术恢复', desc: '每次短休后可恢复若干法术位（等级/2取整，且不超过5级法术位）' },
      { level: 2, name: '奥法传承特性', desc: '根据选择的传承学派获取专属能力，研究更深入' },
      { level: 18, name: '法术精通', desc: '可以不消耗法术位施放特定法术' },
    ],
    subclasses: [
      { name: 'Evocation', zh: '塑能学派', description: '爆炸伤害专精，可以让法术绕过盟友，强化爆发伤害骰，是最纯粹的攻击法师。' },
      { name: 'Abjuration', zh: '防护学派', description: '护盾与反制法术专精，可为自己添加生命之盾，反制法术能力卓越，极强的防御型法师。' },
      { name: 'Illusion', zh: '幻术学派', description: '创造幻觉迷惑敌人，幻象可在一定程度上造成真实伤害，是最考验创意的法师学派。' },
      { name: 'Necromancy', zh: '死灵学派', description: '操控不死生物，可用死灵魔法复活敌人尸体为仆从（最多可统治大量亡灵），吸取目标生命。' },
      { name: 'Conjuration', zh: '咒法学派', description: '召唤与传送专精，可召唤盟友或生物，传送自身（后期无限次），最强的位移型法师。' },
      { name: 'Divination', zh: '预言学派', description: '最强的工具型法师：拥有"预言骰"可以提前掷骰并替换任意检定结果，近乎作弊的能力。' },
      { name: 'Enchantment', zh: '附魔学派', description: '精神控制专精，可在不伤害敌人情况下控制其行动，催眠，迫使重新攻击盟友，极致的控制型。' },
      { name: 'Transmutation', zh: '变化学派', description: '改造物质和身体，可暂时强化属性，转化材料，传递强化buff给队友。' },
    ],
  },
}

// ══════════════════════════════════════════════════════════
// 技能
// ══════════════════════════════════════════════════════════
export const SKILL_INFO = {
  '运动':     { ability: 'str', en: 'Athletics',      desc: '攀爬、游泳、跳跃、摔角，以及需要爆发力的体力活动' },
  '特技':     { ability: 'dex', en: 'Acrobatics',     desc: '保持平衡、空翻、翻滚，以及复杂的身体协调动作' },
  '巧手':     { ability: 'dex', en: 'Sleight of Hand', desc: '扒窃、藏匿物品、变戏法，需要灵巧手指的精细动作' },
  '隐匿':     { ability: 'dex', en: 'Stealth',        desc: '悄无声息地移动和隐藏自身，避免被察觉' },
  '奥秘':     { ability: 'int', en: 'Arcana',         desc: '了解法术、魔法物品、奥秘传说，以及神秘力量' },
  '历史':     { ability: 'int', en: 'History',        desc: '了解历史事件、传奇人物、古代王国、过去的战争' },
  '调查':     { ability: 'int', en: 'Investigation',  desc: '搜寻线索、分析证据、推断信息，福尔摩斯式的分析' },
  '自然':     { ability: 'int', en: 'Nature',         desc: '了解地形、植物动物、天气变化、自然循环' },
  '宗教':     { ability: 'int', en: 'Religion',       desc: '了解神明、宗教仪式、神圣符文，以及不死生物' },
  '驯兽':     { ability: 'wis', en: 'Animal Handling', desc: '安抚、驯服动物，以及感知动物的意图和情绪' },
  '洞察':     { ability: 'wis', en: 'Insight',        desc: '判断生物的真实意图，察觉谎言或隐藏的情绪' },
  '医疗':     { ability: 'wis', en: 'Medicine',       desc: '稳定濒死同伴、诊断疾病，以及照料伤员' },
  '察觉':     { ability: 'wis', en: 'Perception',     desc: '利用感官察觉隐藏的事物，注意异常和危险信号' },
  '求生':     { ability: 'wis', en: 'Survival',       desc: '追踪踪迹、狩猎、导航，以及在野外生存' },
  '欺瞒':     { ability: 'cha', en: 'Deception',      desc: '说谎、伪装、用虚假信息误导他人' },
  '恐吓':     { ability: 'cha', en: 'Intimidation',   desc: '通过威胁、敌意或暴力手段影响他人' },
  '表演':     { ability: 'cha', en: 'Performance',    desc: '表演音乐、舞蹈、戏剧，以及其他娱乐艺术' },
  '说服':     { ability: 'cha', en: 'Persuasion',     desc: '通过理性、魅力或良好态度影响他人的想法' },
}

// ══════════════════════════════════════════════════════════
// 背景
// ══════════════════════════════════════════════════════════
export const BACKGROUND_INFO = {
  'Acolyte':      { zh: '侍僧',   desc: '在寺庙或神殿中服侍神明，熟悉宗教仪式和圣典。技能：洞察、宗教' },
  'Criminal':     { zh: '罪犯',   desc: '曾经游走于法律灰色地带，拥有广泛的地下人脉。技能：欺瞒、隐匿' },
  'Folk Hero':    { zh: '民间英雄', desc: '来自普通百姓，曾经完成改变家乡命运的壮举。技能：驯兽、求生' },
  'Noble':        { zh: '贵族',   desc: '出身高贵，接受过良好教育，熟悉权力运作规则。技能：历史、说服' },
  'Sage':         { zh: '学者',   desc: '毕生钻研知识，在图书馆和学术机构中度过大量时光。技能：奥秘、历史' },
  'Soldier':      { zh: '士兵',   desc: '曾在军队中服役，磨练了战斗技艺和团队协作能力。技能：运动、恐吓' },
  'Charlatan':    { zh: '骗子',   desc: '专业骗术师，能以假乱真，在社会各阶层中游刃有余。技能：欺瞒、巧手' },
  'Entertainer':  { zh: '艺人',   desc: '在舞台上博取喝彩，了解如何打动观众的情感。技能：特技、表演' },
  'Guild Artisan':{ zh: '工会工匠', desc: '属于手艺人行会，掌握一门精湛的工艺技术。技能：洞察、说服' },
  'Hermit':       { zh: '隐士',   desc: '独居于世外，通过冥想和自我反省获得独特见解。技能：医疗、宗教' },
  'Outlander':    { zh: '异乡人', desc: '在文明边缘的荒野中成长，了解生存之道。技能：运动、求生' },
  'Sailor':       { zh: '水手',   desc: '在海上漂泊多年，懂得驾船和阅读天象。技能：运动、察觉' },
}

// ══════════════════════════════════════════════════════════
// 双职业入门要求
// ══════════════════════════════════════════════════════════
export const MULTICLASS_REQUIREMENTS = {
  'Barbarian': { str: 13 },
  'Bard':      { cha: 13 },
  'Cleric':    { wis: 13 },
  'Druid':     { wis: 13 },
  'Fighter':   { str: 13, dex: 13 },   // 任意一项满足即可
  'Monk':      { dex: 13, wis: 13 },
  'Paladin':   { str: 13, cha: 13 },
  'Ranger':    { dex: 13, wis: 13 },
  'Rogue':     { dex: 13 },
  'Sorcerer':  { cha: 13 },
  'Warlock':   { cha: 13 },
  'Wizard':    { int: 13 },
}

// 职业 ZH→EN 映射
export const CLASS_ZH_TO_EN = {
  '野蛮人':'Barbarian','吟游诗人':'Bard','牧师':'Cleric','德鲁伊':'Druid',
  '战士':'Fighter','武僧':'Monk','圣武士':'Paladin','游侠':'Ranger',
  '游荡者':'Rogue','术士':'Sorcerer','邪术师':'Warlock','法师':'Wizard',
}

export const ABILITY_ZH = { str:'力量', dex:'敏捷', con:'体质', int:'智力', wis:'感知', cha:'魅力' }
