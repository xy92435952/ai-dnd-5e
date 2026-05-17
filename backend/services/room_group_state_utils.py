from typing import Optional


DEFAULT_GROUP_ID = "main"
DEFAULT_GROUP_NAME = "主队"
DEFAULT_GROUP_LOCATION = "当前场景"
READINESS_STATUSES = {"drafting", "ready", "waiting"}


def clean_group_id_value(group_id: Optional[str]) -> str:
    clean = "".join(
        ch for ch in (group_id or DEFAULT_GROUP_ID).strip().lower()
        if ch.isalnum() or ch in {"_", "-"}
    )
    return clean[:40] or DEFAULT_GROUP_ID


def normalize_party_groups(raw_groups, member_ids: list[str]) -> list[dict]:
    member_id_set = set(member_ids)
    groups: list[dict] = []
    assigned: set[str] = set()

    if isinstance(raw_groups, list):
        for raw in raw_groups:
            if not isinstance(raw, dict):
                continue
            group_id = clean_group_id_value(raw.get("id"))
            members = [
                uid for uid in unique_preserve_order(raw.get("member_user_ids") or [])
                if uid in member_id_set and uid not in assigned
            ]
            assigned.update(members)
            groups.append({
                "id": group_id,
                "name": (raw.get("name") or (DEFAULT_GROUP_NAME if group_id == DEFAULT_GROUP_ID else group_id)).strip(),
                "location": (raw.get("location") or DEFAULT_GROUP_LOCATION).strip(),
                "member_user_ids": members,
            })

    if not groups:
        groups = [{
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }]

    main = next((group for group in groups if group["id"] == DEFAULT_GROUP_ID), None)
    if main is None:
        main = {
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }
        groups.insert(0, main)

    missing = [uid for uid in member_ids if uid not in assigned]
    main["member_user_ids"] = unique_preserve_order([
        *main.get("member_user_ids", []),
        *missing,
    ])
    return drop_empty_non_default_groups(groups)


def normalize_group_actions(raw_pending, groups: list[dict]) -> dict:
    group_ids = [group["id"] for group in groups]
    pending = raw_pending if isinstance(raw_pending, dict) else {}
    normalized = {}
    for group_id in group_ids:
        actions = pending.get(group_id) if isinstance(pending, dict) else []
        normalized[group_id] = [
            action for action in (actions or [])
            if isinstance(action, dict) and action.get("text")
        ][-20:]
    return normalized


def normalize_group_readiness(raw_readiness, groups: list[dict], member_id_set: set[str]) -> dict:
    readiness = raw_readiness if isinstance(raw_readiness, dict) else {}
    normalized = {}
    for group in groups:
        group_id = group["id"]
        member_ids = set(group.get("member_user_ids") or [])
        raw_group = readiness.get(group_id) if isinstance(readiness, dict) else {}
        if not isinstance(raw_group, dict):
            raw_group = {}
        normalized[group_id] = {
            uid: status
            for uid, status in raw_group.items()
            if uid in member_id_set
            and uid in member_ids
            and status in READINESS_STATUSES
        }
    return normalized


def drop_empty_non_default_groups(groups: list[dict]) -> list[dict]:
    kept = [
        group for group in groups
        if group.get("id") == DEFAULT_GROUP_ID or group.get("member_user_ids")
    ]
    if not kept:
        return [{
            "id": DEFAULT_GROUP_ID,
            "name": DEFAULT_GROUP_NAME,
            "location": DEFAULT_GROUP_LOCATION,
            "member_user_ids": [],
        }]
    return kept


def unique_preserve_order(values) -> list:
    out = []
    seen = set()
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
