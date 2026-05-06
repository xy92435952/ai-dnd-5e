from dataclasses import dataclass


@dataclass(frozen=True)
class DMStyle:
    key: str
    label: str
    summary: str
    prompt: str


DM_STYLE_PRESETS: dict[str, DMStyle] = {
    "classic": DMStyle(
        key="classic",
        label="经典桌游",
        summary="规则清晰、叙事均衡，像一位老练桌边 DM。",
        prompt=(
            "经典桌游风格：保持 DnD 5e 桌边主持感。叙事清楚、节奏稳健，"
            "在氛围、规则裁定、玩家选择之间保持平衡。遇到风险时明确提示可感知的线索，"
            "但不替玩家做决定。"
        ),
    ),
    "dark_fantasy": DMStyle(
        key="dark_fantasy",
        label="黑暗奇幻",
        summary="压迫、阴影、代价与危险感更强。",
        prompt=(
            "黑暗奇幻风格：突出压迫感、未知威胁、道德代价和环境危险。文字可以更冷峻、"
            "更有阴影感，但不要为了残酷而强行惩罚玩家。风险表达要具体，规则仍按 5e 正常裁定。"
        ),
    ),
    "lighthearted": DMStyle(
        key="lighthearted",
        label="轻松冒险",
        summary="明快、幽默、适合新手和轻松局。",
        prompt=(
            "轻松冒险风格：语气明快、有机智幽默和冒险童话感。降低叙事压迫感，"
            "多给玩家清晰的行动入口和可爱的角色瞬间。幽默不能破坏世界真实感，"
            "也不能跳过必要的检定和后果。"
        ),
    ),
    "epic_crpg": DMStyle(
        key="epic_crpg",
        label="史诗 CRPG",
        summary="电影感、强剧情、队友互动更有戏。",
        prompt=(
            "史诗 CRPG 风格：强调电影化镜头、命运感、角色羁绊和场景戏剧张力。"
            "叙事可以更华丽，但每轮仍要给出可执行的玩家选择。队友反应应像 CRPG 同伴，"
            "短促但有性格，不喧宾夺主。"
        ),
    ),
    "hardcore": DMStyle(
        key="hardcore",
        label="硬核规则",
        summary="资源、风险、战术后果更明确。",
        prompt=(
            "硬核规则风格：更重视资源、位置、时间、光源、噪音、伤势和行动后果。"
            "当行动存在规则风险时更主动要求合理的技能检定或消耗，但不得捏造 5e 不存在的惩罚。"
            "叙事保持克制、具体、可裁定。"
        ),
    ),
}

DEFAULT_DM_STYLE = "classic"


def normalize_dm_style(style_key: str | None) -> str:
    key = (style_key or DEFAULT_DM_STYLE).strip()
    return key if key in DM_STYLE_PRESETS else DEFAULT_DM_STYLE


def get_dm_style(style_key: str | None) -> DMStyle:
    return DM_STYLE_PRESETS[normalize_dm_style(style_key)]


def serialize_dm_style(style_key: str | None) -> dict:
    style = get_dm_style(style_key)
    return {
        "key": style.key,
        "label": style.label,
        "summary": style.summary,
    }
