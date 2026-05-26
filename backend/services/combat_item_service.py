from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, CombatState, Session
from services.dnd_rules import get_incapacitating_reasons


@dataclass
class CombatItemActionError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass
class CombatItemAction:
    combat: CombatState
    turn_state: dict


async def prepare_combat_item_action(
    *,
    db: AsyncSession,
    character_id: str,
    session_id: str | None,
    get_turn_state: Callable[[CombatState, str], dict],
) -> CombatItemAction:
    if not session_id:
        raise CombatItemActionError(400, "战斗中使用物品需要提供 session_id")

    session = await db.get(Session, session_id)
    if not session:
        raise CombatItemActionError(404, "会话不存在")

    character = await db.get(Character, character_id)
    if character:
        reasons = get_incapacitating_reasons(character)
        if reasons:
            raise CombatItemActionError(400, f"Character cannot act while {', '.join(reasons)}")

    combat_result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
    combat = combat_result.scalars().first()
    if not combat:
        raise CombatItemActionError(404, "战斗状态不存在")

    turn_state = validate_combat_item_action(
        session=session,
        combat=combat,
        character_id=character_id,
        get_turn_state=get_turn_state,
    )
    return CombatItemAction(combat=combat, turn_state=turn_state)


def validate_combat_item_action(
    *,
    session: Any,
    combat: Any,
    character_id: str,
    get_turn_state: Callable[[Any, str], dict],
) -> dict:
    if not session.combat_active:
        raise CombatItemActionError(400, "当前不在战斗中")

    turn_order = combat.turn_order or []
    if not turn_order:
        raise CombatItemActionError(400, "战斗回合顺序不存在")

    current = turn_order[combat.current_turn_index % len(turn_order)]
    current_id = current.get("character_id") if isinstance(current, dict) else None
    if str(current_id) != str(character_id):
        raise CombatItemActionError(400, "现在不是该角色的回合")

    turn_state = get_turn_state(combat, character_id)
    if turn_state.get("action_used"):
        raise CombatItemActionError(400, "本回合行动已用尽，请使用「结束回合」")

    return turn_state


def consume_combat_item_action(
    action: CombatItemAction,
    *,
    character_id: str,
    save_turn_state: Callable[[CombatState, str, dict], None],
) -> dict:
    action.turn_state["action_used"] = True
    save_turn_state(action.combat, character_id, action.turn_state)
    return action.turn_state
