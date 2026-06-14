"""Role-aware AI movement helpers."""

from __future__ import annotations

from typing import Any

from services.combat_grid_service import chebyshev_distance
from services.encounter_template_service import normalize_tactical_role


GRID_WIDTH = 20
GRID_HEIGHT = 12
SKIRMISHER_REPOSITION_MAX_STEPS = 3
NO_OPPORTUNITY_ESCAPE_HINTS = (
    "flyby",
    "doesn't provoke opportunity",
    "does not provoke opportunity",
    "不触发借机",
    "不会触发借机",
    "飞掠",
)


def choose_skirmisher_reposition(
    *,
    actor: dict[str, Any] | None,
    party: list[dict[str, Any]],
    positions: dict[str, Any],
    turn_state: dict[str, Any],
    target_id: str | None = None,
    grid_width: int = GRID_WIDTH,
    grid_height: int = GRID_HEIGHT,
) -> dict[str, Any] | None:
    """Choose a rules-aware post-attack reposition for skirmisher enemies."""
    if not actor or normalize_tactical_role(actor.get("tactical_role"), "") != "skirmisher":
        return None

    actor_id = str(actor.get("id") or "")
    actor_pos = _position(positions, actor_id)
    if not actor_id or not actor_pos:
        return None

    alive_party = [
        character
        for character in party
        if character.get("hp_current", 0) > 0 and _position(positions, str(character.get("id") or ""))
    ]
    if not alive_party:
        return None

    move_remaining = _movement_remaining(turn_state)
    if move_remaining <= 0:
        return None

    can_leave_reach = bool(turn_state.get("disengaged")) or actor_ignores_opportunity_attacks(actor)
    current_distance = _nearest_party_distance(actor_pos, alive_party, positions)
    if current_distance <= 1 and not can_leave_reach:
        return None

    target_pos = _position(positions, str(target_id or ""))
    occupied = _occupied_positions(positions, actor_id)
    current = dict(actor_pos)
    start = dict(actor_pos)
    steps_taken = 0
    max_steps = min(move_remaining, SKIRMISHER_REPOSITION_MAX_STEPS)

    for _ in range(max_steps):
        candidate = _best_reposition_step(
            current=current,
            start=start,
            alive_party=alive_party,
            positions=positions,
            occupied=occupied,
            target_pos=target_pos,
            current_distance=current_distance,
            can_leave_reach=can_leave_reach,
            grid_width=grid_width,
            grid_height=grid_height,
        )
        if not candidate:
            break
        current = {"x": candidate["x"], "y": candidate["y"]}
        current_distance = candidate["nearest_party_distance"]
        steps_taken += 1

    if steps_taken <= 0:
        return None

    return {
        "x": current["x"],
        "y": current["y"],
        "steps": steps_taken,
        "from": start,
        "nearest_party_distance": current_distance,
        "reason": "skirmisher_reposition",
    }


def _best_reposition_step(
    *,
    current: dict[str, int],
    start: dict[str, int],
    alive_party: list[dict[str, Any]],
    positions: dict[str, Any],
    occupied: set[tuple[int, int]],
    target_pos: dict[str, int] | None,
    current_distance: int,
    can_leave_reach: bool,
    grid_width: int,
    grid_height: int,
) -> dict[str, int] | None:
    candidates: list[dict[str, int]] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            x_pos = int(current.get("x", 0)) + dx
            y_pos = int(current.get("y", 0)) + dy
            if not (0 <= x_pos < grid_width and 0 <= y_pos < grid_height):
                continue
            if (x_pos, y_pos) in occupied:
                continue

            candidate_pos = {"x": x_pos, "y": y_pos}
            nearest_distance = _nearest_party_distance(candidate_pos, alive_party, positions)
            if nearest_distance <= 1 and not can_leave_reach:
                continue
            if nearest_distance <= current_distance:
                continue

            target_distance = chebyshev_distance(candidate_pos, target_pos) if target_pos else 0
            start_distance = chebyshev_distance(candidate_pos, start)
            candidates.append({
                "x": x_pos,
                "y": y_pos,
                "nearest_party_distance": nearest_distance,
                "target_distance": target_distance,
                "start_distance": start_distance,
            })

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (
            item["nearest_party_distance"],
            item["target_distance"],
            -item["start_distance"],
            -item["x"],
            -item["y"],
        ),
    )


def _movement_remaining(turn_state: dict[str, Any]) -> int:
    movement_max = int(turn_state.get("movement_max", 0) or 0)
    movement_used = int(turn_state.get("movement_used", 0) or 0)
    return max(0, movement_max - movement_used)


def _nearest_party_distance(
    position: dict[str, int],
    alive_party: list[dict[str, Any]],
    positions: dict[str, Any],
) -> int:
    distances = [
        chebyshev_distance(position, _position(positions, str(character.get("id") or "")))
        for character in alive_party
    ]
    return min(distances, default=999)


def _occupied_positions(positions: dict[str, Any], actor_id: str) -> set[tuple[int, int]]:
    occupied = set()
    for entity_id, pos in positions.items():
        if str(entity_id) == str(actor_id):
            continue
        if not isinstance(pos, dict):
            continue
        occupied.add((int(pos.get("x", -1)), int(pos.get("y", -1))))
    return occupied


def _position(positions: dict[str, Any], entity_id: str) -> dict[str, int] | None:
    raw = positions.get(str(entity_id))
    if not isinstance(raw, dict):
        return None
    return {"x": int(raw.get("x", 0)), "y": int(raw.get("y", 0))}


def actor_ignores_opportunity_attacks(actor: dict[str, Any]) -> bool:
    texts: list[str] = []
    for key in ("traits", "special_abilities", "actions", "features"):
        values = actor.get(key) or []
        if isinstance(values, dict):
            values = values.values()
        if not isinstance(values, (list, tuple, set)):
            continue
        for value in values:
            if isinstance(value, dict):
                texts.extend(str(value.get(text_key, "")) for text_key in ("name", "description", "desc"))
            else:
                texts.append(str(value))
    combined = " ".join(texts).lower()
    return any(hint in combined for hint in NO_OPPORTUNITY_ESCAPE_HINTS)
