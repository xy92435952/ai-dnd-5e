from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.combat_concentration_effect_service import clear_concentration_effects_for_caster
from services.combat_ready_spell_concentration_service import (
    clear_ready_spell_for_lost_concentration,
    is_ready_spell_concentration,
)


@dataclass
class EndConcentrationResult:
    character_id: str
    character_name: str
    spell_name: str | None
    actor_state: dict[str, Any]
    concentration_effect_updates: list[dict[str, Any]] = field(default_factory=list)
    ready_action_failed: dict[str, Any] | None = None

    @property
    def ended(self) -> bool:
        return bool(self.spell_name)

    @property
    def narration(self) -> str:
        if not self.spell_name:
            return f"{self.character_name}当前没有需要维持的专注。"
        return f"{self.character_name}结束了对【{self.spell_name}】的专注。"

    def to_response(self) -> dict[str, Any]:
        return {
            "narration": self.narration,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "actor_state": self.actor_state,
            "caster_state": self.actor_state,
            "concentration_ended": self.ended,
            "concentration_spell_name": self.spell_name,
            "concentration_effect_updates": self.concentration_effect_updates,
            "ready_action_failed": self.ready_action_failed,
        }


async def end_concentration_for_character(db, session, character) -> EndConcentrationResult:
    """Voluntarily end a character's concentration and clear tracked effects."""
    character_id = str(character.id)
    character_name = character.name or character_id
    spell_name = character.concentration
    character.concentration = None

    concentration_effect_updates: list[dict[str, Any]] = []
    if spell_name:
        concentration_effect_updates = await clear_concentration_effects_for_caster(
            db,
            session,
            character_id,
            spell_name=spell_name,
        )

    actor_state = {
        "target_id": character_id,
        "entity_id": character_id,
        "target_name": character_name,
        "concentration": None,
    }
    if concentration_effect_updates:
        actor_state["concentration_effect_updates"] = concentration_effect_updates

    ready_action_failed = None
    if is_ready_spell_concentration(spell_name):
        cleared_ready_spell = await clear_ready_spell_for_lost_concentration(
            db,
            session,
            character,
            concentration_spell_name=spell_name,
            reason="concentration_ended",
            add_log=False,
        )
        if cleared_ready_spell:
            ready_action_failed = cleared_ready_spell.ready_action_failed
            actor_state["ready_action_failed"] = ready_action_failed

    return EndConcentrationResult(
        character_id=character_id,
        character_name=character_name,
        spell_name=spell_name,
        actor_state=actor_state,
        concentration_effect_updates=concentration_effect_updates,
        ready_action_failed=ready_action_failed,
    )
