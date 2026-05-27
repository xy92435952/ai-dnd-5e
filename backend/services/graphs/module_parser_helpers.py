"""Pure helper functions for module parsing, JSON repair, and chunk batching."""

import json
import re

# 长模组切分参数
_MAX_CHARS_PER_SEGMENT = 15000          # 每段最大字符数（DeepSeek V4-Flash 稳妥）
_MAX_ITEMS_PER_CHUNK_BATCH = 15         # chunk 生成单批最多 items（scenes+npcs+items 总数）


def _mod(score: int) -> int:
    return (score - 10) // 2


def _fill_monster_defaults(m: dict) -> dict:
    scores = m.get('ability_scores', {})
    if not scores:
        cr = m.get('cr', 1)
        base = min(10 + int(cr * 1.5), 20)
        scores = {'str': base, 'dex': 10, 'con': base - 2,
                  'int': 8, 'wis': 10, 'cha': 8}
        m['ability_scores'] = scores

    if not m.get('actions'):
        cr = m.get('cr', 1)
        prof = 2 + (int(cr) // 4)
        atk_bonus = prof + _mod(scores.get('str', 10))
        m['actions'] = [{
            'name': '近战攻击',
            'type': 'melee_attack',
            'attack_bonus': atk_bonus,
            'reach_or_range': '触及5尺',
            'damage_dice': f'1d{6 + int(cr) * 2}+{_mod(scores.get("str", 10))}',
            'damage_type': '钝击',
            'extra_effects': ''
        }]

    if not m.get('saving_throws'):
        m['saving_throws'] = {}

    defaults = {
        'type': '怪物', 'xp': max(10, int(m.get('cr', 1) * 100)),
        'hp_dice': f"{max(1, m.get('hp', 10) // 5)}d8",
        'ac_source': '天然护甲', 'speed': 30, 'skills': {},
        'resistances': [], 'immunities': [], 'vulnerabilities': [],
        'condition_immunities': [], 'senses': '普通视觉',
        'languages': [], 'special_abilities': [], 'legendary_actions': [],
        'known_spells': [], 'prepared_spells': [], 'cantrips': [], 'spell_slots': {},
        'spell_ability': None, 'spell_save_dc': None,
        'multiattack': 1, 'pack_tactics': False,
        'typical_count': 1, 'tactics': '直接攻击最近的目标'
    }
    for k, v in defaults.items():
        if k not in m or m[k] is None:
            m[k] = v
    return m


def _strip_code_block(text: str) -> str:
    """去除 LLM 输出中的 Markdown 代码块包裹（```json ... ```）"""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n?\s*```\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


def _try_parse_json(text: str) -> dict:
    """尝试解析 JSON，失败时尝试修复常见问题后重试。"""
    text = _strip_code_block(text)

    # 第一次尝试：直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 修复：LLM 在 JSON 字符串值内使用了未转义的 ASCII 双引号
    # 策略：逐字符扫描，在 JSON 字符串内部将未转义的 " 替换为中文引号「」
    fixed = _fix_unescaped_quotes(text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 兜底：截取到最后一个 }
    try:
        start = text.index('{')
        end = text.rindex('}')
        chunk = text[start:end + 1]
        fixed2 = _fix_unescaped_quotes(chunk)
        return json.loads(fixed2)
    except (json.JSONDecodeError, ValueError):
        pass

    raise json.JSONDecodeError("All JSON repair attempts failed", text, 0)


def _fix_unescaped_quotes(text: str) -> str:
    """
    修复 JSON 字符串值中未转义的双引号。
    逐字符状态机：追踪是否在字符串内部，将字符串内部的未转义 " 替换为「」
    """
    result = []
    in_string = False
    escape_next = False
    i = 0

    while i < len(text):
        ch = text[i]

        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue

        if ch == '\\' and in_string:
            escape_next = True
            result.append(ch)
            i += 1
            continue

        if ch == '"':
            if not in_string:
                # 开始一个字符串
                in_string = True
                result.append(ch)
            else:
                # 可能是字符串结束，也可能是未转义的内部引号
                # 向前看：字符串结束后应紧跟 , : ] } 或空白
                j = i + 1
                while j < len(text) and text[j] in ' \t\n\r':
                    j += 1
                if j >= len(text) or text[j] in ',:]}\n':
                    # 这是字符串结尾
                    in_string = False
                    result.append(ch)
                else:
                    # 这是字符串内部的未转义引号，替换为中文引号
                    result.append('\u201c')
            i += 1
            continue

        result.append(ch)
        i += 1

    return ''.join(result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 长模组切分 & partial 合并（v0.11）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MD_HEADING_RE = re.compile(r'^\s{0,3}##\s+', re.MULTILINE)
_CHAP_KEYWORDS_RE = re.compile(
    r'^\s*('
    r'第\s*[一二三四五六七八九十百千0-9]+\s*[幕章节部分回]'
    r'|Chapter\s+\d+|Scene\s+\d+|Act\s+\d+|Part\s+\d+'
    r'|序章|终章|楔子|尾声|引子|后记'
    r')\b',
    re.MULTILINE | re.IGNORECASE,
)


def _split_by_markdown_heading(text: str) -> list[str]:
    """按 ## 二级标题切。每段以 ## 开头。"""
    matches = list(_MD_HEADING_RE.finditer(text))
    if len(matches) < 2:
        return []
    segments = []
    # 首个 ## 前可能有前言
    if matches[0].start() > 0:
        head = text[:matches[0].start()].strip()
        if head:
            segments.append(head)
    for i, m in enumerate(matches):
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[m.start():next_start].strip()
        if seg:
            segments.append(seg)
    return segments


def _split_by_chapter_keywords(text: str) -> list[str]:
    """按中文章节关键词或英文 Chapter/Scene/Act 切。"""
    matches = list(_CHAP_KEYWORDS_RE.finditer(text))
    if len(matches) < 2:
        return []
    segments = []
    if matches[0].start() > 0:
        head = text[:matches[0].start()].strip()
        if head:
            segments.append(head)
    for i, m in enumerate(matches):
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[m.start():next_start].strip()
        if seg:
            segments.append(seg)
    return segments


def _split_by_char_count(text: str, max_chars: int) -> list[str]:
    """按字数硬切，优先保留句末/空行边界。"""
    segments: list[str] = []
    rest = text
    while rest:
        if len(rest) <= max_chars:
            segments.append(rest.strip())
            break
        candidate = rest[:max_chars]
        # 在 70%-100% 范围内找句末边界
        min_boundary = int(max_chars * 0.7)
        boundary = max(
            candidate.rfind('。'),
            candidate.rfind('！'),
            candidate.rfind('？'),
            candidate.rfind('\n\n'),
            candidate.rfind('. '),
        )
        if boundary < min_boundary:
            boundary = max_chars - 1  # 找不到好位置就硬切
        segments.append(rest[:boundary + 1].strip())
        rest = rest[boundary + 1:]
    return [s for s in segments if s]


def _split_module_text(text: str, max_chars: int = _MAX_CHARS_PER_SEGMENT) -> list[str]:
    """三级 fallback：Markdown 标题 → 章节关键词 → 字数硬切。
    text <= max_chars 直接返回 [text]。"""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    # 宽容度：分段后允许某段略超（1.5×），避免一个大段被强切坏
    tolerance = max_chars * 1.5

    md_segs = _split_by_markdown_heading(text)
    if md_segs and all(len(s) <= tolerance for s in md_segs):
        return md_segs

    chap_segs = _split_by_chapter_keywords(text)
    if chap_segs and all(len(s) <= tolerance for s in chap_segs):
        return chap_segs

    return _split_by_char_count(text, max_chars)


def _merge_module_partials(partials: list[dict]) -> dict:
    """合并多段 partial module_data 为完整 data。
    - 顶层字段（name/setting/plot_summary/tone/level/size）：取第一段的
    - scenes：顺序 append，order 重编号
    - npcs/monsters/magic_items：按 name+(role/cr) 联合 key 去重
    - key_rewards：字符串并集去重
    """
    if not partials:
        return {}
    if len(partials) == 1:
        return partials[0]

    merged = {
        "name":                  partials[0].get("name", ""),
        "setting":               partials[0].get("setting", ""),
        "plot_summary":          partials[0].get("plot_summary", ""),
        "tone":                  partials[0].get("tone", "标准冒险"),
        "level_min":             partials[0].get("level_min", 1),
        "level_max":             partials[0].get("level_max", 5),
        "recommended_party_size": partials[0].get("recommended_party_size", 4),
        "class_restrictions":    partials[0].get("class_restrictions", []),
        "scenes":                [],
        "npcs":                  [],
        "monsters":              [],
        "magic_items":           [],
        "key_rewards":           [],
    }

    npc_seen: dict = {}        # (name, role_hint) → npc
    monster_seen: dict = {}    # (name, cr_hint) → monster
    item_seen: dict = {}       # (name, type_hint) → item
    reward_seen: set = set()

    for p in partials:
        if not isinstance(p, dict):
            continue

        for scene in p.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            scene = {**scene, "order": len(merged["scenes"])}
            merged["scenes"].append(scene)

        for npc in p.get("npcs") or []:
            if not isinstance(npc, dict) or not npc.get("name"):
                continue
            key = (str(npc.get("name", "")).strip(), str(npc.get("role", "")).strip()[:20])
            if key not in npc_seen:
                npc_seen[key] = npc
                merged["npcs"].append(npc)
            else:
                # 合并同 key 的字段（取长版本）
                existing = npc_seen[key]
                for field in ("role", "personality", "alignment", "attitude"):
                    if len(str(npc.get(field, "") or "")) > len(str(existing.get(field, "") or "")):
                        existing[field] = npc[field]

        for m in p.get("monsters") or []:
            if not isinstance(m, dict) or not m.get("name"):
                continue
            key = (str(m.get("name", "")).strip(), str(m.get("cr", "")))
            if key not in monster_seen:
                monster_seen[key] = m
                merged["monsters"].append(m)

        for item in p.get("magic_items") or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            key = (str(item.get("name", "")).strip(), str(item.get("type", "")).strip()[:20])
            if key not in item_seen:
                item_seen[key] = item
                merged["magic_items"].append(item)

        for reward in p.get("key_rewards") or []:
            if isinstance(reward, str):
                r = reward.strip()
                if r and r not in reward_seen:
                    reward_seen.add(r)
                    merged["key_rewards"].append(reward)

    # 扩展 level 范围到所有段
    for p in partials[1:]:
        lmin = p.get("level_min")
        lmax = p.get("level_max")
        if isinstance(lmin, (int, float)) and lmin < merged["level_min"]:
            merged["level_min"] = int(lmin)
        if isinstance(lmax, (int, float)) and lmax > merged["level_max"]:
            merged["level_max"] = int(lmax)

    return merged


def _split_module_data_for_chunks(
    module_data: dict,
    items_per_batch: int = _MAX_ITEMS_PER_CHUNK_BATCH,
) -> list[dict]:
    """把 module_data 按 items（scenes+npcs+magic_items 总数）切成多批。
    每批都带完整 meta（name/setting/plot/tone/level），
    monsters 只在第一批出现（一次 overview 足够）。"""
    scenes = module_data.get("scenes") or []
    npcs = module_data.get("npcs") or []
    magic_items = module_data.get("magic_items") or []
    monsters = module_data.get("monsters") or []

    total = len(scenes) + len(npcs) + len(magic_items)
    if total <= items_per_batch:
        return [module_data]

    meta = {
        "name":         module_data.get("name", ""),
        "setting":      module_data.get("setting", ""),
        "plot_summary": module_data.get("plot_summary", ""),
        "tone":         module_data.get("tone", "标准冒险"),
        "level_min":    module_data.get("level_min", 1),
        "level_max":    module_data.get("level_max", 5),
    }

    # 按类型 + 顺序排列所有 items，然后按 batch_size 切
    all_items = (
        [("scene", x) for x in scenes] +
        [("npc", x) for x in npcs] +
        [("magic_item", x) for x in magic_items]
    )

    batches = []
    for idx, start in enumerate(range(0, len(all_items), items_per_batch)):
        slice_items = all_items[start:start + items_per_batch]
        batch = {
            **meta,
            "scenes":      [x[1] for x in slice_items if x[0] == "scene"],
            "npcs":        [x[1] for x in slice_items if x[0] == "npc"],
            "magic_items": [x[1] for x in slice_items if x[0] == "magic_item"],
            "monsters":    monsters if idx == 0 else [],  # 只在第一批出现
        }
        batches.append(batch)
    return batches
