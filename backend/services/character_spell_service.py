from dataclasses import dataclass


@dataclass
class CharacterSpellError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def build_prepared_spells_update(
    *,
    known_spells: list[str] | None,
    requested_spells: list[str],
    level: int,
    derived: dict | None,
) -> dict:
    known = set(known_spells or [])
    for spell in requested_spells:
        if spell not in known:
            raise CharacterSpellError(400, f"法术【{spell}】不在已知法术列表中")

    derived_data = derived or {}
    modifiers = derived_data.get("ability_modifiers", {})
    spell_ability = derived_data.get("spell_ability")
    spell_modifier = modifiers.get(spell_ability, 0) if spell_ability else 0
    max_prepared = max(1, level + spell_modifier)

    if len(requested_spells) > max_prepared:
        raise CharacterSpellError(
            400,
            f"已备法术上限为 {max_prepared}（等级{level}+修正{spell_modifier}），"
            f"你选了 {len(requested_spells)} 个",
        )

    return {
        "prepared_spells": list(requested_spells),
        "max_prepared": max_prepared,
    }
