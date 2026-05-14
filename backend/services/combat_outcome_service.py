from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Character, CombatState


async def check_and_cleanup_combat_outcome(
    db: AsyncSession,
    *,
    session,
    session_id: str,
    enemies: list[dict[str, Any]],
    check_combat_over: Callable[[list[dict[str, Any]], int], tuple[bool, str | None]],
) -> tuple[bool, str | None]:
    player = await db.get(Character, session.player_character_id)
    player_hp = player.hp_current if player else 0
    combat_over, outcome = check_combat_over(enemies, player_hp)

    if combat_over:
        session.combat_active = False
        try:
            result = await db.execute(select(CombatState).where(CombatState.session_id == session_id))
            old_state = result.scalars().first()
            if old_state:
                await db.delete(old_state)
        except Exception:
            pass

    return combat_over, outcome
