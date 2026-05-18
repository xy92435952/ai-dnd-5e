import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage

from services.action_parser_local import dist
from services.action_parser_prompts import PARSE_PROMPT
from services.llm import get_llm


async def parse_with_llm(
    player_input: str,
    game_state: dict,
    player_id: str,
    player_data: dict,
    positions: dict,
    move_remaining: int,
) -> dict:
    player_pos = positions.get(str(player_id), {})

    battlefield = []
    for eid, pos in positions.items():
        entity_info = None
        for char in game_state.get("characters", []):
            if str(char.get("id")) == str(eid):
                entity_info = f"{char.get('name','?')} (队友, HP:{char.get('hp_current',0)}/{char.get('hp_max',0)})"
                break
        if not entity_info:
            for enemy in game_state.get("enemies", []):
                if str(enemy.get("id")) == str(eid):
                    entity_info = f"{enemy.get('name','?')} (敌人, HP:{enemy.get('hp_current',0)}/{enemy.get('hp_max',0)})"
                    break
        if not entity_info:
            entity_info = eid[:8]

        distance = dist(pos, player_pos) if player_pos else 999
        battlefield.append(
            f"  ID:{eid[:16]} | {entity_info} | "
            f"位置:({pos.get('x','?')},{pos.get('y','?')}) | 距离:{distance}格({distance*5}ft)"
        )

    game_state_str = "\n".join(battlefield) if battlefield else "无实体信息"

    prompt = PARSE_PROMPT.format(
        game_state=game_state_str,
        player_id=player_id,
        player_name=player_data.get("name", "玩家"),
        player_x=player_pos.get("x", "?"),
        player_y=player_pos.get("y", "?"),
        player_hp=player_data.get("hp_current", 0),
        player_hp_max=player_data.get("hp_max", 0),
        player_ac=player_data.get("ac", 10),
        move_remaining=move_remaining,
        move_remaining_ft=move_remaining * 5,
        player_input=player_input,
    )

    llm = get_llm(temperature=0.3, max_tokens=500, task="fast")
    resp = await asyncio.wait_for(
        llm.ainvoke([
            SystemMessage(content="你是 DnD 5e 战斗行动解析器。只返回 JSON。"),
            HumanMessage(content=prompt),
        ]),
        timeout=10.0,
    )

    raw = resp.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    result = json.loads(raw)
    result.setdefault("actions", [])
    result.setdefault("narrative_hint", "")
    result["_fallback"] = False
    return result
