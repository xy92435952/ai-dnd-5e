/**
 * PixelSprite — 内联 SVG 像素精灵（16x24 网格，HD-2D 风）
 * 来源：design v0.10 prototype pixel-sprites.jsx
 * 用途：战场 token 兜底；未来可通过 <Sprite /> 组件切换到 PNG 资源
 *
 * 支持 kind：
 *   职业：paladin / rogue / fighter / wizard
 *   敌人：cultist / skeleton_mage / shadow_wolf
 *   其他 kind 自动 fallback 到 paladin
 */
import { useMemo } from 'react'

const SKIN = '#e8b890';      // 肤色
const SKIN_SH = '#a06848';   // 肤色阴影
const HAIR_BRN = '#3a2010';  // 棕发
const HAIR_BLD = '#e8c850';  // 金发
const HAIR_BLK = '#1a0a08';  // 黑发
const HAIR_RED = '#a02820';  // 红发
const EYE = '#1a0a08';
const OUTLINE = '#000000';

// 装备调色板
const GOLD = '#e8c040';       const GOLD_DK = '#8a6818';
const STEEL = '#c8d0d8';      const STEEL_DK = '#6a7080';
const LEATHER = '#6a4020';    const LEATHER_DK = '#3a2010';
const CLOTH_BLUE = '#3878c8'; const CLOTH_BLUE_DK = '#1a3a6a';
const CLOTH_PURP = '#6840a0'; const CLOTH_PURP_DK = '#3a1a5a';
const CLOTH_GREEN='#3a8848';  const CLOTH_GREEN_DK='#1a4a20';
const CLOTH_RED = '#a82830';  const CLOTH_RED_DK  = '#5a1018';
const CLOTH_DRK = '#1a1418';  const CLOTH_DRK_DK  = '#000000';
const BONE = '#e8dcb8';       const BONE_DK = '#8a7c5a';

// px helper: 每个像素 2px 大小
const P = 2;
const px = (x, y, c) =>
  <rect key={`${x},${y},${c}`} x={x*P} y={y*P} width={P} height={P} fill={c} shapeRendering="crispEdges" />;

// 画一个像素串："5,3,#ff0000 6,3,#ff0000 ..." 用数组更省事
// 我们用紧凑的格式：每个角色定义一个 pixel map [x, y, color]

// ══════════════════════════════════════════════════════════════
// 角色定义（16x24 画布）
// 约定：头 4-11 行、身体 12-19、腿 20-23
// ══════════════════════════════════════════════════════════════

// —— 圣武士（艾琳）金盔 + 蓝袍 + 盾 ——
function spritePaladin() {
  const pixels = [];
  // 头盔（金）
  for (let x = 5; x <= 10; x++) pixels.push([x, 4, GOLD]);
  for (let x = 4; x <= 11; x++) pixels.push([x, 5, GOLD]);
  for (let x = 4; x <= 11; x++) pixels.push([x, 6, GOLD_DK]);
  // 面罩 T 形缝
  pixels.push([7,6,OUTLINE],[8,6,OUTLINE]);
  for (let x = 4; x <= 11; x++) pixels.push([x, 7, GOLD]);
  pixels.push([6,7,OUTLINE],[9,7,OUTLINE]);
  // 脸（下半露出）
  for (let x = 5; x <= 10; x++) pixels.push([x, 8, SKIN]);
  pixels.push([5,8,SKIN_SH],[10,8,SKIN_SH]);
  // 头盔顶冠（金羽饰）
  pixels.push([7,3,GOLD],[8,3,GOLD]);
  pixels.push([7,2,GOLD_DK]);
  // 下巴 / 脖子
  for (let x = 6; x <= 9; x++) pixels.push([x, 9, SKIN]);
  // 肩甲（钢）
  for (let x = 3; x <= 12; x++) pixels.push([x, 10, STEEL]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 11, STEEL_DK]);
  // 胸甲金边
  pixels.push([5,11,GOLD],[10,11,GOLD]);
  // 身（蓝袍）
  for (let x = 5; x <= 10; x++) for (let y = 12; y <= 17; y++) pixels.push([x, y, CLOTH_BLUE]);
  // 胸甲金十字
  pixels.push([7,13,GOLD],[8,13,GOLD]);
  pixels.push([7,14,GOLD],[8,14,GOLD]);
  pixels.push([6,14,GOLD],[9,14,GOLD]);
  // 腰带
  for (let x = 5; x <= 10; x++) pixels.push([x, 17, LEATHER_DK]);
  pixels.push([7,17,GOLD],[8,17,GOLD]);
  // 左臂 · 举盾
  for (let y = 10; y <= 14; y++) pixels.push([2, y, STEEL], [3, y, STEEL_DK]);
  // 盾（圆盾，金边 + 蓝底 + 十字）
  pixels.push([1,11,GOLD],[2,11,GOLD]);
  for (let y = 12; y <= 15; y++) { pixels.push([0,y,GOLD_DK],[1,y,CLOTH_BLUE],[2,y,CLOTH_BLUE]); }
  pixels.push([1,16,GOLD],[2,16,GOLD]);
  pixels.push([1,13,GOLD]); // 十字竖
  pixels.push([0,13,GOLD_DK]);
  // 右臂 · 持剑
  for (let y = 10; y <= 15; y++) pixels.push([12, y, STEEL_DK], [13, y, STEEL]);
  // 剑柄 + 剑
  pixels.push([13,9,LEATHER]);
  pixels.push([13,8,GOLD]); pixels.push([12,8,GOLD],[14,8,GOLD]); // 护手
  for (let y = 2; y <= 7; y++) pixels.push([13, y, STEEL]);
  pixels.push([13,1,STEEL]);
  // 披风（背后一点红色露边）
  pixels.push([3,12,CLOTH_RED_DK],[12,12,CLOTH_RED_DK]);
  pixels.push([3,13,CLOTH_RED],[12,13,CLOTH_RED]);
  // 腿（钢靴 + 蓝裤）
  for (let y = 18; y <= 20; y++) { pixels.push([6,y,CLOTH_BLUE_DK],[7,y,CLOTH_BLUE_DK],[8,y,CLOTH_BLUE_DK],[9,y,CLOTH_BLUE_DK]); }
  pixels.push([6,21,STEEL_DK],[7,21,STEEL],[8,21,STEEL],[9,21,STEEL_DK]);
  pixels.push([5,22,STEEL_DK],[6,22,STEEL],[7,22,STEEL],[8,22,STEEL],[9,22,STEEL],[10,22,STEEL_DK]);
  return pixels;
}

// —— 盗贼（凯瑞丝）兜帽 + 匕首 ——
function spriteRogue() {
  const pixels = [];
  // 兜帽（深紫）外廓
  for (let x = 4; x <= 11; x++) pixels.push([x, 4, CLOTH_DRK]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 5, CLOTH_DRK]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 6, CLOTH_DRK_DK]);
  pixels.push([2,6,CLOTH_DRK_DK],[13,6,CLOTH_DRK_DK]);
  // 脸部阴影（兜帽下半露出）
  for (let x = 5; x <= 10; x++) pixels.push([x, 7, CLOTH_DRK_DK]);
  pixels.push([6,7,SKIN_SH],[7,7,SKIN],[8,7,SKIN],[9,7,SKIN_SH]);
  pixels.push([7,7,EYE],[8,7,EYE]); // 眼
  // 下颌
  for (let x = 6; x <= 9; x++) pixels.push([x, 8, SKIN]);
  pixels.push([5,8,CLOTH_DRK_DK],[10,8,CLOTH_DRK_DK]);
  // 一缕红发
  pixels.push([4,6,HAIR_RED],[4,7,HAIR_RED],[11,6,HAIR_RED]);
  // 脖领
  for (let x = 5; x <= 10; x++) pixels.push([x, 9, LEATHER_DK]);
  // 披风兜帽背
  for (let y = 10; y <= 12; y++) { pixels.push([3,y,CLOTH_DRK],[12,y,CLOTH_DRK]); }
  // 身体（皮甲）
  for (let x = 4; x <= 11; x++) pixels.push([x, 10, LEATHER]);
  for (let x = 4; x <= 11; x++) pixels.push([x, 11, LEATHER_DK]);
  for (let x = 5; x <= 10; x++) for (let y = 12; y <= 16; y++) pixels.push([x, y, LEATHER]);
  // 皮甲交叉绑带
  pixels.push([6,12,GOLD_DK],[9,13,GOLD_DK]);
  pixels.push([7,13,GOLD_DK],[8,14,GOLD_DK]);
  // 腰带 + 金扣
  for (let x = 5; x <= 10; x++) pixels.push([x, 16, CLOTH_DRK_DK]);
  pixels.push([7,16,GOLD],[8,16,GOLD]);
  // 双臂
  for (let y = 11; y <= 14; y++) pixels.push([4,y,LEATHER_DK],[11,y,LEATHER_DK]);
  // 左手匕首（向前伸）
  pixels.push([3,13,LEATHER],[2,14,STEEL],[2,13,STEEL_DK]);
  pixels.push([1,14,STEEL],[1,13,STEEL_DK]);
  // 右手匕首（反手）
  pixels.push([12,14,LEATHER],[13,14,STEEL_DK],[13,15,STEEL]);
  pixels.push([14,15,STEEL_DK]);
  // 腿（紧身黑裤）
  for (let y = 17; y <= 20; y++) { pixels.push([6,y,CLOTH_DRK],[7,y,CLOTH_DRK],[8,y,CLOTH_DRK],[9,y,CLOTH_DRK]); }
  // 靴
  pixels.push([6,21,LEATHER_DK],[7,21,LEATHER],[8,21,LEATHER],[9,21,LEATHER_DK]);
  pixels.push([5,22,LEATHER_DK],[6,22,LEATHER],[7,22,LEATHER],[8,22,LEATHER],[9,22,LEATHER],[10,22,LEATHER_DK]);
  return pixels;
}

// —— 战士（索恩）大斧 + 重甲 ——
function spriteFighter() {
  const pixels = [];
  // 头发（棕色乱发）
  for (let x = 4; x <= 11; x++) pixels.push([x, 3, HAIR_BRN]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 4, HAIR_BRN]);
  pixels.push([3,5,HAIR_BRN],[12,5,HAIR_BRN]);
  // 脸
  for (let x = 5; x <= 10; x++) pixels.push([x, 5, SKIN]);
  pixels.push([5,5,SKIN_SH],[10,5,SKIN_SH]);
  pixels.push([6,6,EYE],[9,6,EYE]);
  for (let x = 5; x <= 10; x++) pixels.push([x, 6, SKIN]);
  pixels.push([6,6,EYE],[9,6,EYE]);
  pixels.push([5,6,SKIN_SH],[10,6,SKIN_SH]);
  // 胡渣
  for (let x = 6; x <= 9; x++) pixels.push([x, 7, SKIN]);
  pixels.push([7,7,HAIR_BRN],[8,7,HAIR_BRN]);
  // 脖子
  for (let x = 6; x <= 9; x++) pixels.push([x, 8, SKIN]);
  // 肩甲（钢 · 巨大）
  for (let x = 2; x <= 13; x++) pixels.push([x, 9, STEEL]);
  for (let x = 2; x <= 13; x++) pixels.push([x, 10, STEEL_DK]);
  pixels.push([2,9,OUTLINE],[13,9,OUTLINE]);
  // 胸甲
  for (let x = 4; x <= 11; x++) for (let y = 11; y <= 15; y++) pixels.push([x, y, STEEL]);
  // 铆钉
  pixels.push([5,12,GOLD],[10,12,GOLD]);
  pixels.push([5,14,GOLD],[10,14,GOLD]);
  pixels.push([7,13,GOLD_DK],[8,13,GOLD_DK]);
  // 腰带
  for (let x = 4; x <= 11; x++) pixels.push([x, 15, LEATHER_DK]);
  pixels.push([7,15,GOLD],[8,15,GOLD]);
  // 左臂（持斧）
  for (let y = 10; y <= 15; y++) pixels.push([3,y,STEEL_DK]);
  pixels.push([2,11,STEEL],[2,12,STEEL]);
  // 斧柄 + 斧头
  for (let y = 4; y <= 13; y++) pixels.push([1,y,LEATHER_DK]);
  // 斧头（双刃）
  pixels.push([0,5,STEEL],[0,6,STEEL],[0,7,STEEL]);
  pixels.push([2,5,STEEL],[2,6,STEEL],[2,7,STEEL]);
  pixels.push([0,4,STEEL_DK],[2,4,STEEL_DK],[0,8,STEEL_DK],[2,8,STEEL_DK]);
  pixels.push([1,3,STEEL_DK]);
  // 右臂
  for (let y = 10; y <= 14; y++) pixels.push([12,y,STEEL_DK]);
  pixels.push([13,12,STEEL],[13,13,STEEL]);
  // 腿（钢护胫 + 红裙甲）
  for (let y = 16; y <= 18; y++) for (let x = 5; x <= 10; x++) pixels.push([x, y, CLOTH_RED]);
  pixels.push([5,16,CLOTH_RED_DK],[10,16,CLOTH_RED_DK]);
  for (let y = 19; y <= 20; y++) { pixels.push([6,y,STEEL],[7,y,STEEL],[8,y,STEEL],[9,y,STEEL]); }
  pixels.push([6,21,STEEL_DK],[7,21,STEEL],[8,21,STEEL],[9,21,STEEL_DK]);
  pixels.push([5,22,STEEL_DK],[6,22,STEEL],[7,22,STEEL],[8,22,STEEL],[9,22,STEEL],[10,22,STEEL_DK]);
  return pixels;
}

// —— 法师（薇拉）紫袍 + 法杖 + 尖帽 ——
function spriteWizard() {
  const pixels = [];
  // 尖帽（紫色，顶端向上延伸）
  pixels.push([8,0,CLOTH_PURP_DK]);
  pixels.push([7,1,CLOTH_PURP],[8,1,CLOTH_PURP_DK]);
  pixels.push([6,2,CLOTH_PURP],[7,2,CLOTH_PURP],[8,2,CLOTH_PURP_DK]);
  pixels.push([5,3,CLOTH_PURP],[6,3,CLOTH_PURP],[7,3,CLOTH_PURP],[8,3,CLOTH_PURP_DK],[9,3,CLOTH_PURP_DK]);
  for (let x = 4; x <= 10; x++) pixels.push([x, 4, CLOTH_PURP]);
  pixels.push([4,4,CLOTH_PURP_DK],[10,4,CLOTH_PURP_DK]);
  for (let x = 3; x <= 11; x++) pixels.push([x, 5, CLOTH_PURP_DK]);
  // 帽子金星
  pixels.push([7,4,GOLD],[8,4,GOLD]);
  // 脸
  for (let x = 5; x <= 10; x++) pixels.push([x, 6, SKIN]);
  for (let x = 5; x <= 10; x++) pixels.push([x, 7, SKIN]);
  pixels.push([5,6,SKIN_SH],[10,6,SKIN_SH]);
  pixels.push([5,7,SKIN_SH],[10,7,SKIN_SH]);
  pixels.push([6,7,EYE],[9,7,EYE]);
  // 长金发（帽侧漏出）
  pixels.push([3,6,HAIR_BLD],[4,6,HAIR_BLD],[11,6,HAIR_BLD],[12,6,HAIR_BLD]);
  pixels.push([3,7,HAIR_BLD],[4,7,HAIR_BLD],[11,7,HAIR_BLD],[12,7,HAIR_BLD]);
  pixels.push([3,8,HAIR_BLD],[11,8,HAIR_BLD]);
  // 下巴
  for (let x = 6; x <= 9; x++) pixels.push([x, 8, SKIN]);
  // 袍领（白）
  pixels.push([5,9,BONE],[6,9,BONE],[9,9,BONE],[10,9,BONE]);
  pixels.push([7,9,CLOTH_PURP_DK],[8,9,CLOTH_PURP_DK]);
  // 身（紫袍）
  for (let x = 4; x <= 11; x++) for (let y = 10; y <= 17; y++) pixels.push([x, y, CLOTH_PURP]);
  // 袍装饰金条
  for (let y = 10; y <= 17; y++) pixels.push([7, y, GOLD_DK], [8, y, GOLD_DK]);
  pixels.push([7,11,GOLD],[8,11,GOLD]);
  pixels.push([7,14,GOLD],[8,14,GOLD]);
  // 腰带（金）
  for (let x = 4; x <= 11; x++) pixels.push([x, 13, GOLD_DK]);
  pixels.push([7,13,GOLD],[8,13,GOLD]);
  // 左手（持法杖）
  for (let y = 11; y <= 14; y++) pixels.push([3,y,CLOTH_PURP_DK]);
  pixels.push([2,12,SKIN_SH],[2,13,SKIN_SH]);
  // 法杖（木 + 顶端水晶）
  for (let y = 3; y <= 15; y++) pixels.push([1, y, LEATHER]);
  pixels.push([0,3,LEATHER_DK]);
  // 水晶（蓝 + 发光）
  pixels.push([0,1,CLOTH_BLUE],[1,1,CLOTH_BLUE],[2,1,CLOTH_BLUE]);
  pixels.push([0,2,CLOTH_BLUE_DK],[1,2,CLOTH_BLUE],[2,2,CLOTH_BLUE_DK]);
  pixels.push([1,0,STEEL]);
  // 右袖
  for (let y = 11; y <= 14; y++) pixels.push([12,y,CLOTH_PURP_DK]);
  pixels.push([13,12,SKIN_SH],[13,13,SKIN_SH]);
  // 袍下摆
  for (let x = 3; x <= 12; x++) pixels.push([x, 18, CLOTH_PURP]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 19, CLOTH_PURP_DK]);
  for (let x = 2; x <= 13; x++) pixels.push([x, 20, CLOTH_PURP_DK]);
  pixels.push([2,21,CLOTH_PURP_DK],[13,21,CLOTH_PURP_DK]);
  // 鞋尖
  pixels.push([6,22,LEATHER_DK],[9,22,LEATHER_DK]);
  return pixels;
}

// —— 黑暗教徒（敌·祭司） 暗红袍 + 兜帽 ——
function spriteCultist() {
  const pixels = [];
  // 兜帽（暗红）
  for (let x = 4; x <= 11; x++) pixels.push([x, 3, CLOTH_RED_DK]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 4, CLOTH_RED]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 5, CLOTH_RED_DK]);
  pixels.push([2,5,CLOTH_RED_DK],[13,5,CLOTH_RED_DK]);
  // 兜帽阴影内的脸（几乎纯黑 + 红眼）
  for (let x = 5; x <= 10; x++) pixels.push([x, 6, OUTLINE]);
  for (let x = 5; x <= 10; x++) pixels.push([x, 7, OUTLINE]);
  pixels.push([6,7,'#ff3030'],[9,7,'#ff3030']); // 红眼
  // 下颌黑阴
  for (let x = 6; x <= 9; x++) pixels.push([x, 8, CLOTH_DRK_DK]);
  // 兜帽角（尖）
  pixels.push([3,3,CLOTH_RED_DK],[12,3,CLOTH_RED_DK]);
  // 披风（暗红往下）
  for (let x = 3; x <= 12; x++) pixels.push([x, 9, CLOTH_RED]);
  for (let x = 2; x <= 13; x++) pixels.push([x, 10, CLOTH_RED_DK]);
  // 身（黑袍内衬）
  for (let x = 4; x <= 11; x++) for (let y = 11; y <= 17; y++) pixels.push([x, y, CLOTH_DRK]);
  // 胸前邪徽（倒五角）
  pixels.push([7,12,CLOTH_RED],[8,12,CLOTH_RED]);
  pixels.push([6,13,CLOTH_RED],[9,13,CLOTH_RED]);
  pixels.push([7,14,CLOTH_RED],[8,14,CLOTH_RED]);
  pixels.push([7,13,'#ff3030'],[8,13,'#ff3030']);
  // 袖
  for (let y = 10; y <= 14; y++) pixels.push([3,y,CLOTH_RED_DK],[12,y,CLOTH_RED_DK]);
  // 手（骨手）举起
  pixels.push([2,11,BONE_DK],[2,12,BONE]);
  pixels.push([13,11,BONE_DK],[13,12,BONE]);
  // 短匕
  pixels.push([14,11,STEEL],[14,10,STEEL_DK]);
  // 袍下摆
  for (let x = 3; x <= 12; x++) pixels.push([x, 18, CLOTH_RED_DK]);
  for (let x = 2; x <= 13; x++) pixels.push([x, 19, CLOTH_DRK]);
  for (let x = 2; x <= 13; x++) pixels.push([x, 20, CLOTH_DRK_DK]);
  // 锯齿下摆
  pixels.push([3,21,CLOTH_DRK],[5,21,CLOTH_DRK],[7,21,CLOTH_DRK],[9,21,CLOTH_DRK],[11,21,CLOTH_DRK]);
  return pixels;
}

// —— 骷髅法师（敌） 白骨 + 破烂黑袍 ——
function spriteSkeletonMage() {
  const pixels = [];
  // 骷髅头
  for (let x = 5; x <= 10; x++) pixels.push([x, 4, BONE]);
  for (let x = 4; x <= 11; x++) pixels.push([x, 5, BONE]);
  for (let x = 4; x <= 11; x++) pixels.push([x, 6, BONE]);
  for (let x = 4; x <= 11; x++) pixels.push([x, 7, BONE]);
  pixels.push([4,5,BONE_DK],[11,5,BONE_DK]);
  pixels.push([4,7,BONE_DK],[11,7,BONE_DK]);
  // 眼窝（黑 + 内部火光）
  pixels.push([5,6,OUTLINE],[6,6,OUTLINE]);
  pixels.push([9,6,OUTLINE],[10,6,OUTLINE]);
  pixels.push([5,6,'#ff8030'],[10,6,'#ff8030']); // 内发光
  // 鼻孔
  pixels.push([7,7,OUTLINE],[8,7,OUTLINE]);
  // 牙
  for (let x = 5; x <= 10; x++) pixels.push([x, 8, BONE_DK]);
  pixels.push([5,8,OUTLINE],[7,8,OUTLINE],[9,8,OUTLINE]);
  // 脖骨
  pixels.push([7,9,BONE],[8,9,BONE]);
  // 肩（黑袍 + 碎骨刺）
  for (let x = 3; x <= 12; x++) pixels.push([x, 10, CLOTH_DRK]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 11, CLOTH_DRK_DK]);
  pixels.push([3,9,BONE],[12,9,BONE]);
  // 身（黑袍）
  for (let x = 4; x <= 11; x++) for (let y = 12; y <= 17; y++) pixels.push([x, y, CLOTH_DRK]);
  // 胸口符文（紫光）
  pixels.push([7,13,CLOTH_PURP],[8,13,CLOTH_PURP]);
  pixels.push([7,14,CLOTH_PURP_DK],[8,14,CLOTH_PURP_DK]);
  // 肋骨凸起
  for (let x = 5; x <= 10; x++) pixels.push([x, 15, BONE_DK]);
  // 骨臂 · 举法杖
  pixels.push([3,11,BONE],[3,12,BONE_DK],[3,13,BONE],[3,14,BONE]);
  pixels.push([2,10,BONE_DK],[2,11,BONE],[2,12,BONE]);
  // 法杖（扭曲黑木 + 绿焰头骨）
  for (let y = 2; y <= 10; y++) pixels.push([1, y, LEATHER_DK]);
  pixels.push([0,4,LEATHER_DK]);
  pixels.push([0,1,BONE],[1,1,BONE],[2,1,BONE]);
  pixels.push([0,0,'#40e060'],[1,0,'#80ffa0'],[2,0,'#40e060']); // 绿焰
  pixels.push([0,2,BONE_DK],[2,2,BONE_DK]);
  // 右臂
  pixels.push([12,11,BONE],[12,12,BONE],[12,13,BONE]);
  pixels.push([13,11,BONE_DK],[13,12,BONE]);
  // 袍下摆（破烂）
  for (let x = 3; x <= 12; x++) pixels.push([x, 18, CLOTH_DRK]);
  for (let x = 3; x <= 12; x++) pixels.push([x, 19, CLOTH_DRK_DK]);
  pixels.push([4,20,CLOTH_DRK],[6,20,CLOTH_DRK],[9,20,CLOTH_DRK],[11,20,CLOTH_DRK]);
  pixels.push([5,21,CLOTH_DRK_DK],[10,21,CLOTH_DRK_DK]);
  return pixels;
}

// —— 暗影狼（敌 · 死亡态） 四足黑毛 ——
function spriteShadowWolf() {
  const pixels = [];
  // 简化：四足兽形剪影（侧面）
  // 头（右侧）
  for (let x = 10; x <= 14; x++) pixels.push([x, 10, CLOTH_DRK_DK]);
  for (let x = 10; x <= 14; x++) pixels.push([x, 11, CLOTH_DRK]);
  pixels.push([14,10,OUTLINE]);
  // 耳
  pixels.push([11,9,CLOTH_DRK_DK],[13,9,CLOTH_DRK_DK]);
  // 眼（红）
  pixels.push([13,11,'#ff3030']);
  // 口
  pixels.push([14,12,CLOTH_DRK_DK],[13,12,BONE_DK]);
  // 身体
  for (let x = 3; x <= 11; x++) for (let y = 12; y <= 15; y++) pixels.push([x, y, CLOTH_DRK]);
  for (let x = 3; x <= 11; x++) pixels.push([x, 12, CLOTH_DRK_DK]);
  // 尾
  pixels.push([2,12,CLOTH_DRK],[1,11,CLOTH_DRK],[0,10,CLOTH_DRK_DK]);
  // 腿
  pixels.push([4,16,CLOTH_DRK],[5,16,CLOTH_DRK],[4,17,CLOTH_DRK_DK],[5,17,CLOTH_DRK_DK]);
  pixels.push([9,16,CLOTH_DRK],[10,16,CLOTH_DRK],[9,17,CLOTH_DRK_DK],[10,17,CLOTH_DRK_DK]);
  return pixels;
}

// ══════════════════════════════════════════════════════════════
// SPRITES 映射
// ══════════════════════════════════════════════════════════════
const SPRITES = {
  paladin: spritePaladin,
  rogue:   spriteRogue,
  fighter: spriteFighter,
  wizard:  spriteWizard,
  cultist: spriteCultist,
  skeleton_mage: spriteSkeletonMage,
  shadow_wolf:   spriteShadowWolf,
};

// ══════════════════════════════════════════════════════════════
// <PixelSprite kind="paladin" size={44} dead /> 组件
// ══════════════════════════════════════════════════════════════
function PixelSprite({ kind, size = 44, dead = false, dim = false }) {
  const gen = SPRITES[kind] || SPRITES.paladin;
  const pixels = useMemo(() => gen(), [kind]);
  const W = 16 * P;   // 32
  const H = 24 * P;   // 48
  return (
    <svg
      width={size}
      height={size * (H / W)}
      viewBox={`0 0 ${W} ${H}`}
      style={{
        imageRendering: 'pixelated',
        filter: dead ? 'grayscale(1) brightness(.4)' : dim ? 'saturate(.6) brightness(.8)' : 'drop-shadow(0 2px 0 rgba(0,0,0,.8))',
        pointerEvents: 'none',
      }}
    >
      {pixels.map(([x, y, c], i) => (
        <rect key={i} x={x*P} y={y*P} width={P} height={P} fill={c} shapeRendering="crispEdges" />
      ))}
    </svg>
  );
}

export default PixelSprite
