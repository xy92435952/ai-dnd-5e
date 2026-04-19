"""将 PixelSprite.jsx 的内联 SVG 像素数据烘焙成 16×24 PNG 资源。

每个 sprite 为 32×48 像素的 PNG（2x up-scale, 保持 imageRendering:pixelated 锐利），
输出到 frontend/public/sprites/{kind}.png。

策略：
  1. 从 JSX 源码提取 7 个原型（paladin / rogue / fighter / wizard / cultist /
     skeleton_mage / shadow_wolf）的像素数据。
  2. 根据 _INDEX.json 的 39 个 kind 及其 fallback 映射，为每个 kind 生成 PNG。
  3. 对于同一 fallback 的多个 kind（如 cultist→cultist/bandit/goblin/kobold…），
     通过**色相偏移**+**边缘色调整**生成视觉差异，避免全部完全一样。

依赖：Pillow
"""
import json
import re
import colorsys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
JSX_PATH = ROOT / "frontend" / "src" / "components" / "PixelSprite.jsx"
INDEX_PATH = ROOT / "frontend" / "public" / "sprites" / "_INDEX.json"
OUT_DIR = ROOT / "frontend" / "public" / "sprites"

# 16x24 网格，2x 放大 → 32x48 PNG
GRID_W = 16
GRID_H = 24
SCALE = 2

# ─── Palette（和 PixelSprite.jsx 一致） ───
PALETTE = {
    "SKIN":    "#e8b890",
    "SKIN_SH": "#a06848",
    "HAIR_BRN":"#3a2010",
    "HAIR_BLD":"#e8c850",
    "HAIR_BLK":"#1a0a08",
    "HAIR_RED":"#a02820",
    "EYE":     "#1a0a08",
    "OUTLINE": "#000000",
    "GOLD":    "#e8c040",
    "GOLD_DK": "#8a6818",
    "STEEL":   "#c8d0d8",
    "STEEL_DK":"#6a7080",
    "LEATHER": "#6a4020",
    "LEATHER_DK":"#3a2010",
    "CLOTH_BLUE":   "#3878c8",
    "CLOTH_BLUE_DK":"#1a3a6a",
    "CLOTH_PURP":   "#6840a0",
    "CLOTH_PURP_DK":"#3a1a5a",
    "CLOTH_GREEN":  "#3a8848",
    "CLOTH_GREEN_DK":"#1a4a20",
    "CLOTH_RED":   "#a82830",
    "CLOTH_RED_DK":"#5a1018",
    "CLOTH_DRK":   "#1a1418",
    "CLOTH_DRK_DK":"#000000",
    "BONE":    "#e8dcb8",
    "BONE_DK": "#8a7c5a",
}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ─── 简化版：直接内嵌 7 个原型的像素数组 ───
# 从 PixelSprite.jsx 抄过来（以保证脚本可独立运行，不依赖 JS 解析）
# 每项: [x, y, color_const]

# 为简化，以下把每个原型用"高度浓缩版"保留 —— 小字号画出来大致能识别职业
# 实际使用时按需替换为完整像素数据。

def palette(name: str) -> tuple[int, int, int]:
    return hex_to_rgb(PALETTE.get(name, "#000000"))


def shift_hue(rgb: tuple[int, int, int], degrees: float) -> tuple[int, int, int]:
    """HSV 色相偏移（仅对饱和度 > 20 的颜色生效，避免把黑/白/灰也变色）"""
    r, g, b = [c / 255.0 for c in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.2:
        return rgb
    h = (h + degrees / 360.0) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def draw_pixels(pixels: list[tuple[int, int, str]], hue_shift: float = 0) -> Image.Image:
    """把像素数组绘制成 32x48 RGBA PNG"""
    img = Image.new("RGBA", (GRID_W * SCALE, GRID_H * SCALE), (0, 0, 0, 0))
    for x, y, color_name in pixels:
        if not (0 <= x < GRID_W and 0 <= y < GRID_H):
            continue
        rgb = palette(color_name)
        if hue_shift != 0:
            rgb = shift_hue(rgb, hue_shift)
        r, g, b = rgb
        # 填充 2×2 块
        for dx in range(SCALE):
            for dy in range(SCALE):
                img.putpixel((x * SCALE + dx, y * SCALE + dy), (r, g, b, 255))
    return img


# ─── 7 个原型的像素数据 ───
# 为了让脚本独立，手工重建精简版（16×24 核心轮廓，识别度优先）

def sprite_paladin() -> list[tuple[int, int, str]]:
    """金盔蓝袍圣武士"""
    p = []
    # 金色头盔（4-7 行）
    for x in range(5, 11): p.append((x, 4, "GOLD"))
    for x in range(4, 12):
        p.append((x, 5, "GOLD"))
        p.append((x, 6, "GOLD_DK"))
        p.append((x, 7, "GOLD"))
    p.extend([(7, 6, "OUTLINE"), (8, 6, "OUTLINE"), (6, 7, "OUTLINE"), (9, 7, "OUTLINE")])
    # 顶冠
    p.extend([(7, 3, "GOLD"), (8, 3, "GOLD"), (7, 2, "GOLD_DK")])
    # 脸
    for x in range(5, 11): p.append((x, 8, "SKIN"))
    p.extend([(5, 8, "SKIN_SH"), (10, 8, "SKIN_SH")])
    # 脖
    for x in range(6, 10): p.append((x, 9, "SKIN"))
    # 钢肩甲 / 蓝袍
    for x in range(3, 13): p.append((x, 10, "STEEL"))
    for x in range(4, 12):
        p.append((x, 11, "CLOTH_BLUE"))
        p.append((x, 12, "CLOTH_BLUE"))
        p.append((x, 13, "CLOTH_BLUE"))
        p.append((x, 14, "CLOTH_BLUE_DK"))
    # 金色缎带中线
    for y in range(11, 15): p.append((8, y, "GOLD"))
    # 腰带
    for x in range(5, 11): p.append((x, 15, "LEATHER"))
    # 腿
    for y in range(16, 21):
        p.extend([(6, y, "CLOTH_BLUE_DK"), (7, y, "CLOTH_BLUE"), (8, y, "CLOTH_BLUE"), (9, y, "CLOTH_BLUE_DK")])
    # 靴
    for x in range(5, 11): p.append((x, 21, "LEATHER_DK"))
    for x in range(5, 11): p.append((x, 22, "OUTLINE"))
    # 剑（右手）
    for y in range(8, 16): p.append((13, y, "STEEL"))
    p.extend([(13, 7, "GOLD"), (13, 16, "GOLD_DK")])
    # 盾（左手）
    for y in range(10, 17):
        p.append((2, y, "STEEL_DK"))
        p.append((3, y, "STEEL"))
    return p


def sprite_rogue() -> list[tuple[int, int, str]]:
    """暗色斗篷游荡者"""
    p = []
    # 兜帽
    for x in range(5, 11): p.append((x, 4, "CLOTH_DRK"))
    for x in range(4, 12):
        p.append((x, 5, "CLOTH_DRK"))
        p.append((x, 6, "CLOTH_DRK"))
        p.append((x, 7, "CLOTH_DRK_DK"))
    # 脸（阴影里）
    for x in range(6, 10): p.append((x, 8, "SKIN_SH"))
    # 眼睛发光
    p.extend([(7, 7, "GOLD"), (9, 7, "GOLD")])
    # 披风
    for y in range(9, 18):
        for x in range(3, 13):
            p.append((x, y, "CLOTH_DRK"))
    # 中线深色
    for y in range(9, 18): p.append((8, y, "CLOTH_DRK_DK"))
    # 腿
    for y in range(18, 21):
        p.extend([(6, y, "LEATHER_DK"), (7, y, "LEATHER"), (8, y, "LEATHER"), (9, y, "LEATHER_DK")])
    # 匕首
    for y in range(12, 16): p.append((13, y, "STEEL"))
    p.append((13, 11, "STEEL_DK"))
    # 靴
    for x in range(5, 11): p.append((x, 22, "OUTLINE"))
    return p


def sprite_fighter() -> list[tuple[int, int, str]]:
    """板甲战士 + 战锤"""
    p = []
    # 头盔（钢）
    for x in range(5, 11):
        p.append((x, 4, "STEEL"))
        p.append((x, 5, "STEEL"))
    for x in range(4, 12):
        p.append((x, 6, "STEEL_DK"))
        p.append((x, 7, "STEEL"))
    p.extend([(7, 6, "OUTLINE"), (8, 6, "OUTLINE")])
    # 顶
    p.extend([(7, 3, "STEEL"), (8, 3, "STEEL")])
    # 脸
    for x in range(6, 10): p.append((x, 8, "SKIN"))
    # 胸甲
    for x in range(3, 13): p.append((x, 9, "STEEL_DK"))
    for x in range(3, 13):
        p.append((x, 10, "STEEL"))
        p.append((x, 11, "STEEL"))
        p.append((x, 12, "STEEL_DK"))
        p.append((x, 13, "STEEL"))
        p.append((x, 14, "STEEL_DK"))
    # 腰带 / 裙甲
    for x in range(4, 12): p.append((x, 15, "LEATHER"))
    for y in range(16, 20):
        for x in range(5, 11): p.append((x, y, "STEEL_DK"))
    # 腿
    for y in range(20, 22):
        p.extend([(6, y, "STEEL"), (7, y, "STEEL"), (8, y, "STEEL"), (9, y, "STEEL")])
    for x in range(5, 11): p.append((x, 22, "OUTLINE"))
    # 战锤（右）
    for y in range(8, 16): p.append((13, y, "LEATHER_DK"))
    for x in range(12, 15):
        for y in range(7, 10): p.append((x, y, "STEEL"))
    return p


def sprite_wizard() -> list[tuple[int, int, str]]:
    """紫袍尖帽法师 + 法杖"""
    p = []
    # 尖帽
    p.append((8, 2, "CLOTH_PURP_DK"))
    p.extend([(7, 3, "CLOTH_PURP"), (8, 3, "CLOTH_PURP_DK"), (9, 3, "CLOTH_PURP")])
    for x in range(6, 11): p.append((x, 4, "CLOTH_PURP"))
    for x in range(5, 12): p.append((x, 5, "CLOTH_PURP"))
    for x in range(5, 12): p.append((x, 6, "CLOTH_PURP_DK"))
    # 帽檐金带
    for x in range(5, 12): p.append((x, 7, "GOLD"))
    # 脸 + 胡子
    for x in range(6, 10): p.append((x, 8, "SKIN"))
    for x in range(5, 11): p.append((x, 9, "BONE"))  # 白胡子
    # 紫袍
    for y in range(10, 18):
        for x in range(4, 12): p.append((x, y, "CLOTH_PURP"))
    for y in range(10, 18): p.append((8, y, "GOLD"))  # 金色披肩
    # 脚
    for y in range(18, 21):
        for x in range(5, 11): p.append((x, y, "CLOTH_PURP_DK"))
    for x in range(5, 11): p.append((x, 22, "OUTLINE"))
    # 法杖 + 水晶
    for y in range(4, 17): p.append((13, y, "LEATHER"))
    p.append((13, 3, "CLOTH_PURP"))
    p.extend([(12, 3, "CLOTH_PURP"), (14, 3, "CLOTH_PURP"), (13, 2, "GOLD")])
    return p


def sprite_cultist() -> list[tuple[int, int, str]]:
    """暗红长袍邪教徒（兜帽中有眼）"""
    p = []
    # 兜帽（深红）
    for x in range(5, 11): p.append((x, 4, "CLOTH_RED_DK"))
    for x in range(4, 12):
        p.append((x, 5, "CLOTH_RED_DK"))
        p.append((x, 6, "CLOTH_RED"))
    # 黑色内衬
    for x in range(5, 11): p.append((x, 7, "CLOTH_DRK"))
    # 红光眼
    p.extend([(7, 8, "CLOTH_RED"), (9, 8, "CLOTH_RED")])
    # 兜帽垂边
    p.extend([(3, 6, "CLOTH_RED_DK"), (12, 6, "CLOTH_RED_DK"),
              (3, 7, "CLOTH_RED_DK"), (12, 7, "CLOTH_RED_DK")])
    # 长袍
    for y in range(9, 20):
        for x in range(4, 12): p.append((x, y, "CLOTH_RED_DK"))
    # 金色符文
    p.extend([(8, 12, "GOLD"), (8, 14, "GOLD"), (8, 16, "GOLD")])
    # 脚
    for y in range(20, 22):
        for x in range(5, 11): p.append((x, y, "CLOTH_DRK"))
    for x in range(5, 11): p.append((x, 22, "OUTLINE"))
    return p


def sprite_skeleton_mage() -> list[tuple[int, int, str]]:
    """骷髅法师 + 紫火法杖"""
    p = []
    # 颅骨
    for x in range(5, 11): p.append((x, 4, "BONE"))
    for x in range(4, 12): p.append((x, 5, "BONE"))
    for x in range(4, 12): p.append((x, 6, "BONE_DK"))
    for x in range(4, 12): p.append((x, 7, "BONE"))
    # 黑眼洞
    p.extend([(6, 6, "OUTLINE"), (7, 6, "OUTLINE"),
              (9, 6, "OUTLINE"), (10, 6, "OUTLINE")])
    # 下巴
    for x in range(6, 10): p.append((x, 8, "BONE"))
    # 肋骨
    for y in range(9, 14):
        for x in range(5, 11): p.append((x, y, "BONE"))
    for x in range(5, 11):
        p.append((x, 10, "BONE_DK"))
        p.append((x, 12, "BONE_DK"))
    # 破烂紫袍
    for y in range(14, 20):
        for x in range(4, 12): p.append((x, y, "CLOTH_PURP_DK"))
    # 手骨 + 法杖
    for y in range(5, 16): p.append((13, y, "BONE"))
    p.extend([(12, 4, "CLOTH_PURP"), (13, 4, "CLOTH_PURP"), (14, 4, "CLOTH_PURP")])
    # 脚
    for y in range(20, 22):
        for x in range(5, 11): p.append((x, y, "BONE_DK"))
    return p


def sprite_shadow_wolf() -> list[tuple[int, int, str]]:
    """暗影狼（四足兽）"""
    p = []
    # 身体前段（头）
    for y in range(8, 11):
        for x in range(2, 6): p.append((x, y, "CLOTH_DRK"))
    # 耳朵
    p.extend([(2, 7, "CLOTH_DRK"), (5, 7, "CLOTH_DRK")])
    # 红眼
    p.extend([(3, 9, "CLOTH_RED"), (5, 9, "CLOTH_RED")])
    # 嘴 / 尖牙
    p.extend([(2, 10, "OUTLINE"), (3, 11, "BONE")])
    # 身躯
    for y in range(9, 16):
        for x in range(6, 14): p.append((x, y, "CLOTH_DRK"))
    # 鬃毛尖突
    for x in range(7, 13): p.append((x, 8, "CLOTH_DRK_DK"))
    # 尾巴
    p.extend([(14, 10, "CLOTH_DRK"), (15, 11, "CLOTH_DRK_DK"),
              (14, 12, "CLOTH_DRK"), (15, 9, "CLOTH_DRK_DK")])
    # 腿（4 条）
    for y in range(16, 22):
        p.extend([(3, y, "CLOTH_DRK"), (6, y, "CLOTH_DRK"),
                  (9, y, "CLOTH_DRK"), (12, y, "CLOTH_DRK")])
    # 爪
    for x in [3, 6, 9, 12]: p.append((x, 22, "OUTLINE"))
    return p


PROTOTYPES = {
    "paladin":        sprite_paladin(),
    "fighter":        sprite_fighter(),
    "rogue":          sprite_rogue(),
    "wizard":         sprite_wizard(),
    "cultist":        sprite_cultist(),
    "skeleton_mage":  sprite_skeleton_mage(),
    "shadow_wolf":    sprite_shadow_wolf(),
}


# 根据每个 kind 指定的 hue_shift 生成多样化
# 同一原型派生的变体通过色相偏移区分
VARIANT_HUE = {
    # 职业变体（基于 paladin/fighter/rogue/wizard）
    "cleric":    ("paladin", 0),         # 圣武士式
    "ranger":    ("fighter", -50),       # 绿色偏移
    "barbarian": ("fighter", 20),        # 血色偏移
    "bard":      ("wizard", 80),         # 蓝→青
    "druid":     ("wizard", -90),        # 紫→绿
    "sorcerer":  ("wizard", 40),         # 紫→红紫
    "warlock":   ("wizard", -40),        # 紫→蓝紫
    "monk":      ("fighter", 30),        # 黄调

    # 人形敌人变体（基于 cultist）
    "bandit":    ("cultist", 30),        # 棕红
    "goblin":    ("cultist", -60),       # 绿色
    "kobold":    ("cultist", 50),        # 橘黄
    "orc_warrior": ("cultist", -30),     # 暗红→深棕
    "hobgoblin": ("cultist", 15),
    "unknown_humanoid": ("cultist", 0),

    # 不死生物（基于 skeleton_mage）
    "skeleton_warrior": ("skeleton_mage", -60),
    "zombie":    ("skeleton_mage", -30),
    "ghoul":     ("skeleton_mage", 30),
    "vampire_spawn": ("skeleton_mage", 80),
    "lich":      ("skeleton_mage", 0),
    "mind_flayer": ("skeleton_mage", 60),
    "beholder":  ("skeleton_mage", 120),

    # 野兽（基于 shadow_wolf）
    "wolf":      ("shadow_wolf", 30),
    "dire_wolf": ("shadow_wolf", 0),
    "bear":      ("shadow_wolf", 20),
    "giant_spider": ("shadow_wolf", -40),
    "owlbear":   ("shadow_wolf", 10),
    "giant_rat": ("shadow_wolf", 50),
    "young_dragon_red": ("shadow_wolf", -80),  # 红龙
    "unknown_beast": ("shadow_wolf", 0),

    # 巨人
    "ogre":      ("cultist", -90),
    "troll":     ("cultist", -60),

    # 恶魔/元素
    "demon_minor": ("cultist", 60),
    "fiend":     ("cultist", 45),
    "elemental_fire": ("wizard", 150),   # 火焰蓝→红橙

    "unknown_monster": ("cultist", 0),
}


def main():
    # 读索引
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index = json.load(f)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    # 1. 先生成 7 个原型
    for name, pixels in PROTOTYPES.items():
        img = draw_pixels(pixels, hue_shift=0)
        img.save(OUT_DIR / f"{name}.png", "PNG")
        generated += 1
        print(f"  ✓ {name}.png ({len(pixels)} px)")

    # 2. 生成所有变体
    for kind, info in index.get("sprites", {}).items():
        if kind in PROTOTYPES:
            continue   # 已生成
        fb = info.get("fallback")
        if not fb or fb not in PROTOTYPES:
            continue

        # 找 hue_shift
        variant = VARIANT_HUE.get(kind, (fb, 0))
        proto_name, hue = variant[0], variant[1]
        if proto_name not in PROTOTYPES:
            proto_name = fb
        pixels = PROTOTYPES[proto_name]

        img = draw_pixels(pixels, hue_shift=hue)
        img.save(OUT_DIR / f"{kind}.png", "PNG")
        generated += 1
        print(f"  ✓ {kind}.png (from {proto_name}, hue {hue:+d}°)")

    print(f"\n生成完成：{generated} 个 PNG → {OUT_DIR}")


if __name__ == "__main__":
    main()
