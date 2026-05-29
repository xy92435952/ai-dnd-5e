from dataclasses import dataclass

from services.dnd_rules import (
    ALL_LANGUAGES,
    ALL_SKILLS,
    ARMOR,
    CLASS_SKILL_CHOICES,
    FIGHTING_STYLE_CLASSES,
    RACIAL_LANGUAGES,
    SHOP_GEAR,
    STARTING_EQUIPMENT,
    STARTING_GEAR_PACKS,
    WEAPONS,
    get_item_zh,
)


STARTING_WEAPON_BUNDLES = {
    "Two Handaxes": ("Handaxe", 2),
    "Five Javelins": ("Javelin", 5),
}


@dataclass
class CharacterCreationError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def build_starting_equipment(cls_key: str, equipment_choice: int | None) -> dict:
    if equipment_choice is None:
        return {}

    eq_options = STARTING_EQUIPMENT.get(cls_key, [])
    if not 0 <= equipment_choice < len(eq_options):
        return {}

    chosen_eq = eq_options[equipment_choice]
    weapons, armor_list, shield, gear = [], [], None, []
    for item in chosen_eq["items"]:
        slot = item.get("slot", "gear")
        name = item.get("name", "")
        if slot == "weapon" or slot == "weapon2":
            weapon = WEAPONS.get(name)
            if weapon:
                weapons.append(_build_weapon_entry(name, weapon, equipped=slot == "weapon"))
            elif name in STARTING_WEAPON_BUNDLES:
                bundle_weapon_name, count = STARTING_WEAPON_BUNDLES[name]
                bundle_weapon = WEAPONS.get(bundle_weapon_name)
                if bundle_weapon:
                    for index in range(count):
                        weapons.append(
                            _build_weapon_entry(
                                bundle_weapon_name,
                                bundle_weapon,
                                equipped=slot == "weapon" and index == 0,
                            )
                        )
            else:
                _append_gear_items(gear, name)
        elif slot == "armor":
            armor = ARMOR.get(name)
            if armor:
                armor_list.append({**armor, "name": name, "equipped": True})
        elif slot == "offhand" and name == "Shield":
            shield = {"name": "Shield", "zh": "盾牌", "ac": 2, "equipped": True}
        else:
            _append_gear_items(gear, name)

    return {"weapons": weapons, "armor": armor_list, "shield": shield, "gear": gear, "gold": 10}


def _append_gear_items(gear: list[dict], name: str) -> None:
    pack_items = STARTING_GEAR_PACKS.get(name)
    if pack_items:
        for item_name, quantity in pack_items:
            for _ in range(max(0, int(quantity))):
                gear.append(_build_gear_entry(item_name, source_pack=name))
        return

    gear.append(_build_gear_entry(name))


def _build_gear_entry(name: str, *, source_pack: str | None = None) -> dict:
    entry = {**SHOP_GEAR.get(name, {}), "name": name, "zh": get_item_zh(name)}
    if source_pack:
        entry["source_pack"] = source_pack
    return entry


def _build_weapon_entry(name: str, weapon: dict, *, equipped: bool) -> dict:
    weapon_entry = {**weapon, "name": name, "equipped": equipped}
    if _has_ammunition_property(weapon_entry):
        weapon_entry["ammo"] = 20
    return weapon_entry


def _has_ammunition_property(weapon: dict) -> bool:
    properties = weapon.get("properties") or []
    if isinstance(properties, str):
        return properties.lower() == "ammunition"
    return any(str(prop).lower() == "ammunition" for prop in properties)


def build_character_languages(
    *,
    race: str,
    background_features: dict | None,
    bonus_languages: list[str] | None,
) -> list[str]:
    race_lang = RACIAL_LANGUAGES.get(race, {"fixed": ["Common"], "bonus": 0})
    languages = list(race_lang["fixed"])
    bg_lang_bonus = (background_features or {}).get("languages", 0)
    total_bonus = race_lang["bonus"] + bg_lang_bonus

    for lang in (bonus_languages or [])[:total_bonus]:
        if lang in ALL_LANGUAGES and lang not in languages:
            languages.append(lang)

    return languages


def normalize_fighting_style(
    *,
    cls_key: str,
    class_label: str,
    level: int,
    fighting_style: str | None,
) -> str | None:
    if not fighting_style:
        return None

    style_config = FIGHTING_STYLE_CLASSES.get(cls_key)
    if not style_config:
        return None
    if level < style_config["level"]:
        return None
    if fighting_style not in style_config["styles"]:
        raise CharacterCreationError(
            400,
            f"战斗风格【{fighting_style}】不在{class_label}可选范围内",
        )
    return fighting_style


def build_proficient_skills(
    *,
    cls_key: str,
    class_label: str,
    selected_skills: list[str] | None,
    background_skills: list[str] | None,
) -> list[str]:
    skill_config = CLASS_SKILL_CHOICES.get(cls_key, {"count": 2, "options": ALL_SKILLS})
    allowed_count = skill_config["count"]
    allowed_options = skill_config["options"]
    chosen_skills = list(selected_skills or [])

    if len(chosen_skills) > allowed_count:
        raise CharacterCreationError(
            400,
            f"{class_label} 只能选 {allowed_count} 个技能熟练，您选了 {len(chosen_skills)} 个",
        )

    for skill in chosen_skills:
        if allowed_options != ALL_SKILLS and skill not in allowed_options:
            raise CharacterCreationError(400, f"技能【{skill}】不在该职业可选范围内")

    for skill in background_skills or []:
        if skill not in chosen_skills:
            chosen_skills.append(skill)

    return chosen_skills
