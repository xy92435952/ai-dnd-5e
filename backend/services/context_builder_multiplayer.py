def build_multiplayer_context(
    *,
    session,
    characters: list,
    current_actor_id: str | None = None,
) -> dict:
    mp = (session.game_state or {}).get("multiplayer", {}) or {}
    groups = mp.get("party_groups") if isinstance(mp.get("party_groups"), list) else []
    active_group_id = mp.get("active_group_id") or (groups[0].get("id") if groups else None)
    pending_by_group = (
        mp.get("pending_actions_by_group")
        if isinstance(mp.get("pending_actions_by_group"), dict)
        else {}
    )

    user_to_character = {
        char.user_id: char
        for char in characters
        if getattr(char, "user_id", None)
    }
    actor_user_id = None
    if current_actor_id:
        for char in characters:
            if char.id == current_actor_id:
                actor_user_id = char.user_id
                break

    normalized_groups = []
    active_group = None
    for group in groups:
        if not isinstance(group, dict):
            continue
        member_user_ids = group.get("member_user_ids") or []
        member_character_names = [
            user_to_character[uid].name
            for uid in member_user_ids
            if uid in user_to_character
        ]
        item = {
            "id": group.get("id"),
            "name": group.get("name") or group.get("id") or "分队",
            "location": group.get("location") or "当前场景",
            "member_user_ids": member_user_ids,
            "member_character_names": member_character_names,
        }
        normalized_groups.append(item)
        if item["id"] == active_group_id:
            active_group = item

    actor_group = None
    if actor_user_id:
        actor_group = next(
            (
                group for group in normalized_groups
                if actor_user_id in (group.get("member_user_ids") or [])
            ),
            None,
        )
    focus_group = actor_group or active_group or (normalized_groups[0] if normalized_groups else None)
    focus_group_id = focus_group.get("id") if focus_group else active_group_id

    return {
        "active_group_id": active_group_id,
        "actor_group_id": actor_group.get("id") if actor_group else None,
        "focus_group_id": focus_group_id,
        "active_group": focus_group,
        "party_groups": normalized_groups,
        "pending_actions": list(pending_by_group.get(focus_group_id, [])) if focus_group_id else [],
        "pending_actions_by_group": pending_by_group,
    }
