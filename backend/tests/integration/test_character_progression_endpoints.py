import uuid

import pytest

from models import Character
from services.character_leveling_service import SPELLS_KNOWN
from services.dnd_rules import calc_derived, get_cantrips_count
from services.spell_service import spell_service

pytestmark = pytest.mark.integration


async def _auth_headers(client, sample_user):
    response = await client.post("/auth/login", json={
        "username": sample_user.username,
        "password": "password",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _progression_count(table, level):
    count = 0
    for threshold, value in sorted(table.items()):
        if level >= threshold:
            count = value
    return count


def _max_spell_rank(spell_slots_max):
    slot_levels = {
        "1st": 1,
        "2nd": 2,
        "3rd": 3,
        "4th": 4,
        "5th": 5,
        "6th": 6,
        "7th": 7,
        "8th": 8,
        "9th": 9,
    }
    return max(
        [
            slot_levels.get(slot_key, 0)
            for slot_key, count in (spell_slots_max or {}).items()
            if int(count or 0) > 0
        ]
        or [0]
    )


def _legal_spell_names(char_class, max_level):
    return [
        spell["name"]
        for spell in spell_service.get_for_class(char_class)
        if 0 < spell.get("level", 0) <= max_level
    ]


def _class_cantrip_names(char_class):
    return [
        spell["name"]
        for spell in spell_service.get_for_class(char_class)
        if spell.get("level", 0) == 0
    ]


def _spell_name_by_english(name_en):
    return next(
        spell["name"]
        for spell in spell_service.get_all()
        if spell.get("name_en") == name_en
    )


async def test_level_up_adds_new_spell_slots_without_refilling_spent_slots(client, db_session, sample_user):
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    old_derived = calc_derived("Wizard", 2, ability_scores, None, race="Human")
    wizard = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="测试升阶法师",
        race="Human",
        char_class="Wizard",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 0},
        proficient_skills=["奥秘", "调查"],
        proficient_saves=["int", "wis"],
        is_player=True,
    )
    db_session.add(wizard)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{wizard.id}/level-up",
        headers=headers,
        json={"use_average_hp": True},
    )

    assert response.status_code == 200, response.text
    data = response.json()["character"]
    assert data["level"] == 3
    assert data["spell_slots"]["1st"] == 1
    assert data["spell_slots"]["2nd"] == 2


async def test_level_up_updates_class_resources_and_serializes_them(client, db_session, sample_user):
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived("Fighter", 1, ability_scores, None, race="Human")
    fighter = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Leveling Fighter",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        class_resources={"second_wind_used": True},
        proficient_skills=[],
        proficient_saves=["str", "con"],
        is_player=True,
    )
    db_session.add(fighter)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{fighter.id}/level-up",
        headers=headers,
        json={"use_average_hp": True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    resources = payload["character"]["class_resources"]
    assert payload["character"]["level"] == 2
    assert resources["second_wind_used"] is True
    assert resources["action_surge_used"] is False
    assert payload["level_up_details"]["class_resources"] == resources

    await db_session.refresh(fighter)
    assert fighter.class_resources == resources


async def test_level_up_endpoint_applies_subclass_style_and_maneuver_choices(client, db_session, sample_user):
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived("Fighter", 2, ability_scores, None, race="Human")
    fighter = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Battle Master Candidate",
        race="Human",
        char_class="Fighter",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        class_resources={"second_wind_used": True, "action_surge_used": True},
        proficient_skills=[],
        proficient_saves=["str", "con"],
        is_player=True,
    )
    db_session.add(fighter)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{fighter.id}/level-up",
        headers=headers,
        json={
            "use_average_hp": True,
            "subclass_choice": "Battle Master",
            "fighting_style_choice": "Defense",
            "maneuver_choices": ["precision", "trip", "disarm"],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    data = payload["character"]
    details = payload["level_up_details"]
    assert data["level"] == 3
    assert data["subclass"] == "Battle Master"
    assert data["fighting_style"] == "Defense"
    assert data["derived"]["subclass_effects"]["battle_master"] is True
    assert data["class_resources"]["maneuvers_known"] == ["precision", "trip", "disarm"]
    assert details["subclass"] == "Battle Master"
    assert details["fighting_style"] == "Defense"
    assert details["maneuver_choices"] == ["precision", "trip", "disarm"]

    await db_session.refresh(fighter)
    assert fighter.subclass == "Battle Master"
    assert fighter.fighting_style == "Defense"
    assert fighter.class_resources["maneuvers_known"] == ["precision", "trip", "disarm"]


async def test_level_up_endpoint_requires_subclass_choice_at_unlock(client, db_session, sample_user):
    ability_scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8}
    old_derived = calc_derived("Fighter", 2, ability_scores, None, race="Human")
    fighter = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Subclass Required Fighter",
        race="Human",
        char_class="Fighter",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={},
        class_resources={"second_wind_used": True, "action_surge_used": True},
        proficient_skills=[],
        proficient_saves=["str", "con"],
        is_player=True,
    )
    db_session.add(fighter)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{fighter.id}/level-up",
        headers=headers,
        json={"use_average_hp": True},
    )

    assert response.status_code == 400, response.text
    assert "must choose a subclass" in response.json()["detail"]

    await db_session.refresh(fighter)
    assert fighter.level == 2
    assert fighter.subclass in (None, "")


async def test_level_up_adds_requested_wizard_spell_learning(client, db_session, sample_user):
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 16, "wis": 12, "cha": 10}
    old_derived = calc_derived("Wizard", 2, ability_scores, None, race="Human")
    wizard_spells = [
        spell
        for spell in spell_service.get_for_class("Wizard")
        if 0 < spell.get("level", 0) <= 2
    ]
    known_spell = wizard_spells[0]["name"]
    learned_spells = [spell["name"] for spell in wizard_spells[1:3]]
    wizard = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Spell Learning Wizard",
        race="Human",
        char_class="Wizard",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 1},
        known_spells=[known_spell],
        prepared_spells=[known_spell],
        cantrips=["Fire Bolt", "Mage Hand", "Light"],
        proficient_skills=[],
        proficient_saves=["int", "wis"],
        is_player=True,
    )
    db_session.add(wizard)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{wizard.id}/level-up",
        headers=headers,
        json={"use_average_hp": True, "learned_spells": learned_spells},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    data = payload["character"]
    assert data["level"] == 3
    assert data["known_spells"] == [known_spell, *learned_spells]
    assert payload["level_up_details"]["learned_spells"] == learned_spells
    assert payload["level_up_details"]["preparation_type"] == "spellbook"

    await db_session.refresh(wizard)
    assert wizard.known_spells == [known_spell, *learned_spells]


async def test_level_up_endpoint_persists_higher_level_known_caster_spell_and_cantrip_learning(
    client,
    db_session,
    sample_user,
):
    ability_scores = {"str": 10, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 18}
    old_level = 9
    new_level = 10
    old_derived = calc_derived("Bard", old_level, ability_scores, "Lore", race="Human")
    new_derived = calc_derived("Bard", new_level, ability_scores, "Lore", race="Human")
    old_known_count = _progression_count(SPELLS_KNOWN["Bard"], old_level)
    new_known_count = _progression_count(SPELLS_KNOWN["Bard"], new_level)
    old_cantrip_count = get_cantrips_count("Bard", old_level)
    new_cantrip_count = get_cantrips_count("Bard", new_level)
    legal_spells = _legal_spell_names(
        "Bard",
        _max_spell_rank(new_derived.get("spell_slots_max", {})),
    )
    cantrips = _class_cantrip_names("Bard")
    known_spells = legal_spells[:old_known_count]
    learned_spells = legal_spells[old_known_count:new_known_count]
    known_cantrips = cantrips[:old_cantrip_count]
    learned_cantrips = cantrips[old_cantrip_count:new_cantrip_count]
    bard = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Higher Level Bard",
        race="Human",
        char_class="Bard",
        subclass="Lore",
        level=old_level,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots=dict(old_derived.get("spell_slots_max", {})),
        known_spells=known_spells,
        prepared_spells=known_spells,
        cantrips=known_cantrips,
        proficient_skills=[],
        proficient_saves=["dex", "cha"],
        is_player=True,
    )
    db_session.add(bard)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{bard.id}/level-up",
        headers=headers,
        json={
            "use_average_hp": True,
            "learned_spells": learned_spells,
            "learned_cantrips": learned_cantrips,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    data = payload["character"]
    expected_spells = [*known_spells, *learned_spells]
    expected_cantrips = [*known_cantrips, *learned_cantrips]
    assert data["level"] == new_level
    assert data["known_spells"] == expected_spells
    assert data["prepared_spells"] == expected_spells
    assert data["cantrips"] == expected_cantrips
    assert payload["level_up_details"]["learned_spells"] == learned_spells
    assert payload["level_up_details"]["learned_cantrips"] == learned_cantrips
    assert payload["level_up_details"]["preparation_type"] == "known"

    await db_session.refresh(bard)
    assert bard.known_spells == expected_spells
    assert bard.prepared_spells == expected_spells
    assert bard.cantrips == expected_cantrips


async def test_level_up_endpoint_persists_higher_level_wizard_spellbook_and_cantrip_learning(
    client,
    db_session,
    sample_user,
):
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 18, "wis": 12, "cha": 10}
    old_level = 9
    new_level = 10
    old_derived = calc_derived("Wizard", old_level, ability_scores, "Evocation", race="Human")
    new_derived = calc_derived("Wizard", new_level, ability_scores, "Evocation", race="Human")
    legal_spells = _legal_spell_names(
        "Wizard",
        _max_spell_rank(new_derived.get("spell_slots_max", {})),
    )
    cantrips = _class_cantrip_names("Wizard")
    old_cantrip_count = get_cantrips_count("Wizard", old_level)
    new_cantrip_count = get_cantrips_count("Wizard", new_level)
    known_spells = legal_spells[:8]
    learned_spells = legal_spells[8:10]
    known_cantrips = cantrips[:old_cantrip_count]
    learned_cantrips = cantrips[old_cantrip_count:new_cantrip_count]
    prepared_spells = known_spells[:6]
    wizard = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Higher Level Wizard",
        race="Human",
        char_class="Wizard",
        subclass="Evocation",
        level=old_level,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots=dict(old_derived.get("spell_slots_max", {})),
        known_spells=known_spells,
        prepared_spells=prepared_spells,
        cantrips=known_cantrips,
        proficient_skills=[],
        proficient_saves=["int", "wis"],
        is_player=True,
    )
    db_session.add(wizard)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{wizard.id}/level-up",
        headers=headers,
        json={
            "use_average_hp": True,
            "learned_spells": learned_spells,
            "learned_cantrips": learned_cantrips,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    data = payload["character"]
    expected_spells = [*known_spells, *learned_spells]
    expected_cantrips = [*known_cantrips, *learned_cantrips]
    assert data["level"] == new_level
    assert data["known_spells"] == expected_spells
    assert data["prepared_spells"] == prepared_spells
    assert data["cantrips"] == expected_cantrips
    assert payload["level_up_details"]["learned_spells"] == learned_spells
    assert payload["level_up_details"]["learned_cantrips"] == learned_cantrips
    assert payload["level_up_details"]["preparation_type"] == "spellbook"

    await db_session.refresh(wizard)
    assert wizard.known_spells == expected_spells
    assert wizard.prepared_spells == prepared_spells
    assert wizard.cantrips == expected_cantrips


async def test_level_up_endpoint_allows_subclass_expanded_known_spell_learning(
    client,
    db_session,
    sample_user,
):
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 18}
    old_derived = calc_derived("Warlock", 2, ability_scores, "Fiend", race="Human")
    known_spells = [
        spell["name"]
        for spell in spell_service.get_for_class("Warlock")
        if 0 < spell.get("level", 0) <= 2
    ][:3]
    command_spell = _spell_name_by_english("Command")
    assert command_spell not in known_spells
    warlock = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Fiend Expanded Warlock",
        race="Human",
        char_class="Warlock",
        subclass="Fiend",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots=dict(old_derived.get("spell_slots_max", {})),
        known_spells=known_spells,
        prepared_spells=known_spells,
        cantrips=["Eldritch Blast"],
        proficient_skills=[],
        proficient_saves=["wis", "cha"],
        is_player=True,
    )
    db_session.add(warlock)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{warlock.id}/level-up",
        headers=headers,
        json={"use_average_hp": True, "learned_spells": [command_spell]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    data = payload["character"]
    expected_spells = [*known_spells, command_spell]
    assert data["level"] == 3
    assert data["known_spells"] == expected_spells
    assert data["prepared_spells"] == expected_spells
    assert payload["level_up_details"]["learned_spells"] == [command_spell]

    await db_session.refresh(warlock)
    assert warlock.known_spells == expected_spells
    assert warlock.prepared_spells == expected_spells


async def test_level_up_replaces_known_caster_spell(client, db_session, sample_user):
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 16}
    old_derived = calc_derived("Sorcerer", 2, ability_scores, None, race="Human")
    sorcerer_spells = [
        spell
        for spell in spell_service.get_for_class("Sorcerer")
        if 0 < spell.get("level", 0) <= 2
    ]
    old_spell = sorcerer_spells[0]["name"]
    kept_spell = sorcerer_spells[1]["name"]
    new_spell = sorcerer_spells[2]["name"]
    sorcerer = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Spell Swapping Sorcerer",
        race="Human",
        char_class="Sorcerer",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 1},
        known_spells=[old_spell, kept_spell],
        prepared_spells=[old_spell, kept_spell],
        cantrips=["Fire Bolt"],
        proficient_skills=[],
        proficient_saves=["con", "cha"],
        is_player=True,
    )
    db_session.add(sorcerer)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{sorcerer.id}/level-up",
        headers=headers,
        json={
            "use_average_hp": True,
            "spell_replacements": [{"old_spell": old_spell, "new_spell": new_spell}],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    data = payload["character"]
    assert data["level"] == 3
    assert data["known_spells"] == [new_spell, kept_spell]
    assert data["prepared_spells"] == [new_spell, kept_spell]
    assert payload["level_up_details"]["spell_replacements"] == [
        {"old_spell": old_spell, "new_spell": new_spell}
    ]

    await db_session.refresh(sorcerer)
    assert sorcerer.known_spells == [new_spell, kept_spell]
    assert sorcerer.prepared_spells == [new_spell, kept_spell]


async def test_level_up_rejects_relearning_replaced_spell(client, db_session, sample_user):
    ability_scores = {"str": 8, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 16}
    old_derived = calc_derived("Sorcerer", 2, ability_scores, None, race="Human")
    sorcerer_spells = [
        spell
        for spell in spell_service.get_for_class("Sorcerer")
        if 0 < spell.get("level", 0) <= 2
    ]
    old_spell = sorcerer_spells[0]["name"]
    kept_spell = sorcerer_spells[1]["name"]
    replacement_spell = sorcerer_spells[2]["name"]
    sorcerer = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Spell Loop Sorcerer",
        race="Human",
        char_class="Sorcerer",
        level=2,
        ability_scores=ability_scores,
        derived=old_derived,
        hp_current=old_derived["hp_max"],
        spell_slots={"1st": 1},
        known_spells=[old_spell, kept_spell],
        prepared_spells=[old_spell, kept_spell],
        cantrips=["Fire Bolt"],
        proficient_skills=[],
        proficient_saves=["con", "cha"],
        is_player=True,
    )
    db_session.add(sorcerer)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.post(
        f"/characters/{sorcerer.id}/level-up",
        headers=headers,
        json={
            "use_average_hp": True,
            "learned_spells": [old_spell],
            "spell_replacements": [{"old_spell": old_spell, "new_spell": replacement_spell}],
        },
    )

    assert response.status_code == 400, response.text
    assert "cannot also be learned again" in response.json()["detail"]

    await db_session.refresh(sorcerer)
    assert sorcerer.level == 2
    assert sorcerer.known_spells == [old_spell, kept_spell]
    assert sorcerer.prepared_spells == [old_spell, kept_spell]


async def test_prepared_caster_can_prepare_spells_from_class_list(client, db_session, sample_user):
    ability_scores = {"str": 10, "dex": 12, "con": 14, "int": 10, "wis": 16, "cha": 10}
    derived = calc_derived("Cleric", 1, ability_scores, None, race="Human")
    cleric_spell = next(
        spell["name"]
        for spell in spell_service.get_for_class("Cleric")
        if spell.get("level", 0) > 0
    )
    cleric = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="Prepared Cleric",
        race="Human",
        char_class="Cleric",
        level=1,
        ability_scores=ability_scores,
        derived=derived,
        hp_current=derived["hp_max"],
        spell_slots=dict(derived.get("spell_slots_max", {})),
        known_spells=[],
        prepared_spells=[],
        proficient_skills=[],
        proficient_saves=["wis", "cha"],
        is_player=True,
    )
    db_session.add(cleric)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.patch(
        f"/characters/{cleric.id}/prepared-spells",
        headers=headers,
        json={"prepared_spells": [cleric_spell]},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["prepared_spells"] == [cleric_spell]
    assert data["max_prepared"] == 4
    assert data["preparation_type"] == "prepared"

    await db_session.refresh(cleric)
    assert cleric.prepared_spells == [cleric_spell]


async def test_prepared_caster_can_prepare_subclass_bonus_spell(
    client,
    db_session,
    sample_user,
):
    ability_scores = {"str": 14, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12}
    derived = calc_derived("Cleric", 1, ability_scores, "War", race="Human")
    divine_favor = _spell_name_by_english("Divine Favor")
    assert divine_favor not in [
        spell["name"]
        for spell in spell_service.get_for_class("Cleric")
        if spell.get("level", 0) > 0
    ]
    cleric = Character(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        name="War Domain Prepared Cleric",
        race="Human",
        char_class="Cleric",
        subclass="War",
        level=1,
        ability_scores=ability_scores,
        derived=derived,
        hp_current=derived["hp_max"],
        spell_slots=dict(derived.get("spell_slots_max", {})),
        known_spells=[],
        prepared_spells=[],
        proficient_skills=[],
        proficient_saves=["wis", "cha"],
        is_player=True,
    )
    db_session.add(cleric)
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.patch(
        f"/characters/{cleric.id}/prepared-spells",
        headers=headers,
        json={"prepared_spells": [divine_favor]},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["prepared_spells"] == [divine_favor]
    assert data["preparation_type"] == "prepared"

    await db_session.refresh(cleric)
    assert cleric.prepared_spells == [divine_favor]


async def test_exhaustion_level_4_clamps_hp_and_serializes_effective_max(
    client, db_session, sample_character, sample_user,
):
    sample_character.hp_current = 12
    sample_character.conditions = ["exhaustion"]
    sample_character.condition_durations = {"exhaustion_level": 3}
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.patch(
        f"/characters/{sample_character.id}/exhaustion",
        headers=headers,
        json={"change": 1},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["exhaustion_level"] == 4
    assert "hp_max_halved" in data["effects"]
    assert data["is_dead"] is False
    assert data["hp_current"] == 6
    assert data["hp_max"] == 6
    assert data["base_hp_max"] == 12

    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 6
    assert sample_character.derived["hp_max"] == 12


async def test_exhaustion_level_6_sets_death_state(
    client, db_session, sample_character, sample_user,
):
    sample_character.hp_current = 6
    sample_character.conditions = ["exhaustion"]
    sample_character.condition_durations = {"exhaustion_level": 5}
    sample_character.death_saves = {"successes": 2, "failures": 0, "stable": False}
    await db_session.commit()

    headers = await _auth_headers(client, sample_user)
    response = await client.patch(
        f"/characters/{sample_character.id}/exhaustion",
        headers=headers,
        json={"change": 1},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["exhaustion_level"] == 6
    assert "death" in data["effects"]
    assert data["is_dead"] is True
    assert data["hp_current"] == 0
    assert data["death_saves"] == {"successes": 0, "failures": 3, "stable": False}

    await db_session.refresh(sample_character)
    assert sample_character.hp_current == 0
    assert sample_character.death_saves == {"successes": 0, "failures": 3, "stable": False}
