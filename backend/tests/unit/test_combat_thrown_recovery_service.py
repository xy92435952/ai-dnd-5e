from services.combat_thrown_recovery_service import (
    public_thrown_recovery_pool,
    record_recoverable_thrown_weapon,
    recover_thrown_weapons,
)


def test_record_recoverable_thrown_weapon_adds_available_pool_item():
    state = record_recoverable_thrown_weapon(
        {"flags": {}},
        character_id="char-1",
        character_name="Smoke Sentinel",
        weapon_resource={
            "weapon": "Javelin",
            "resource_type": "thrown_weapon",
            "consumed": True,
            "quantity_remaining": 1,
            "recoverable": True,
            "recovery_timing": "after_combat_search",
            "recoverable_weapon": {
                "name": "Javelin",
                "type": "simple_melee",
                "damage": "1d6",
                "properties": ["thrown(30/120)"],
                "quantity": 1,
                "equipped": False,
            },
        },
        source="attack_roll",
    )

    pool = state["thrown_weapon_recovery_pool"]
    assert pool["version"] == 1
    item = pool["items"][0]
    assert item["status"] == "available"
    assert item["character_id"] == "char-1"
    assert item["character_name"] == "Smoke Sentinel"
    assert item["weapon"] == "Javelin"
    assert item["quantity"] == 1
    assert item["item"]["equipped"] is False
    assert item["source"] == "attack_roll"
    assert item["recovery_timing"] == "after_combat_search"


def test_record_recoverable_thrown_weapon_ignores_non_recoverable_resources():
    assert record_recoverable_thrown_weapon(
        {},
        character_id="char-1",
        character_name="Smoke Sentinel",
        weapon_resource={
            "weapon": "Longbow",
            "resource_type": "ammunition",
            "consumed": True,
            "ammo_remaining": 19,
        },
    ) is None


def test_recover_thrown_weapons_restores_quantity_and_marks_pool_item_recovered():
    state = {
        "thrown_weapon_recovery_pool": {
            "version": 1,
            "items": [{
                "id": "thrown-1",
                "status": "available",
                "character_id": "char-1",
                "character_name": "Smoke Sentinel",
                "weapon": "Javelin",
                "quantity": 1,
                "item": {
                    "name": "Javelin",
                    "type": "simple_melee",
                    "damage": "1d6",
                    "properties": ["thrown(30/120)"],
                    "quantity": 1,
                    "equipped": False,
                },
                "public": True,
            }],
        },
    }

    result = recover_thrown_weapons(
        state,
        character_id="char-1",
        character_name="Smoke Sentinel",
        equipment={
            "weapons": [{
                "name": "Javelin",
                "type": "simple_melee",
                "damage": "1d6",
                "properties": ["thrown(30/120)"],
                "quantity": 1,
                "equipped": True,
            }],
        },
    )

    assert result["equipment"]["weapons"][0]["quantity"] == 2
    assert result["equipment"]["weapons"][0]["equipped"] is True
    assert result["recovered"] == [{
        "id": "thrown-1",
        "weapon": "Javelin",
        "quantity": 1,
        "item": {
            "name": "Javelin",
            "type": "simple_melee",
            "damage": "1d6",
            "properties": ["thrown(30/120)"],
            "quantity": 1,
            "equipped": False,
        },
    }]
    recovered_item = result["game_state"]["thrown_weapon_recovery_pool"]["items"][0]
    assert recovered_item["status"] == "recovered"
    assert recovered_item["recovered_by_character_id"] == "char-1"
    assert result["recovery_pool"]["items"][0]["status"] == "recovered"


def test_recover_thrown_weapons_is_idempotent_after_recovery():
    state = {
        "thrown_weapon_recovery_pool": {
            "version": 1,
            "items": [{
                "id": "thrown-1",
                "status": "recovered",
                "character_id": "char-1",
                "weapon": "Javelin",
                "quantity": 1,
                "item": {"name": "Javelin", "quantity": 1},
                "public": True,
            }],
        },
    }

    result = recover_thrown_weapons(
        state,
        character_id="char-1",
        character_name="Smoke Sentinel",
        equipment={"weapons": []},
    )

    assert result["recovered"] == []
    assert result["equipment"]["weapons"] == []


def test_public_thrown_recovery_pool_hides_private_items():
    pool = {
        "version": 1,
        "items": [
            {"id": "public", "status": "available", "public": True},
            {"id": "private", "status": "available", "public": False},
        ],
    }

    public = public_thrown_recovery_pool(pool)

    assert [item["id"] for item in public["items"]] == ["public"]
