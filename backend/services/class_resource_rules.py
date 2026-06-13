"""Shared class-resource capacity helpers."""


def get_action_surge_uses(level: int) -> int:
    if level >= 17:
        return 2
    if level >= 2:
        return 1
    return 0
