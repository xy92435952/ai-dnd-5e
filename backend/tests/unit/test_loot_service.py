import pytest

from services.loot_service import (
    build_loot_pool_from_module,
    claim_loot_item,
    discover_loot_item,
    ensure_loot_state,
    grant_loot_to_equipment,
    public_loot_pool,
    LootError,
)


def test_build_loot_pool_from_module_rewards_and_magic_items():
    pool = build_loot_pool_from_module({
        "key_rewards": ["25 gp", "Gate Token"],
        "magic_items": [
            {
                "name": "Gate Token",
                "rarity": "common",
                "description": "A brass token.",
            },
            {
                "name": "Moonblade",
                "type": "weapon",
                "rarity": "rare",
            },
        ],
    })

    assert [item["name"] for item in pool["items"]] == ["25 gp", "Gate Token", "Moonblade"]
    assert pool["items"][0]["category"] == "gold"
    assert pool["items"][0]["amount"] == 25
    assert pool["items"][0]["status"] == "hidden"
    assert pool["items"][0]["discovered"] is False
    assert pool["items"][1]["category"] == "gear"
    assert pool["items"][1]["description"] == "A brass token."
    assert pool["items"][1]["cost"] == 100
    assert pool["items"][2]["category"] == "weapon"
    assert pool["items"][2]["cost"] == 5000


def test_public_loot_pool_hides_module_seeded_rewards_until_discovered():
    pool = build_loot_pool_from_module({
        "key_rewards": ["25 gp", "Gate Token"],
    })

    assert public_loot_pool(pool)["items"] == []


def test_ensure_loot_state_preserves_claims():
    parsed = {"key_rewards": ["10 gp"]}
    state = discover_loot_item({}, parsed, loot_id="loot_gold_0")
    claimed = claim_loot_item(
        state,
        parsed,
        loot_id="loot_gold_0",
        character_id="char-1",
        character_name="Tester",
        equipment={"gold": 2},
    )

    ensured = ensure_loot_state(claimed["game_state"], parsed)

    item = ensured["loot_pool"]["items"][0]
    assert item["status"] == "claimed"
    assert item["claimed_by_character_id"] == "char-1"
    assert claimed["equipment"]["gold"] == 12


def test_claim_hidden_module_loot_is_not_public():
    parsed = {"key_rewards": ["10 gp"]}

    with pytest.raises(LootError) as exc:
        claim_loot_item(
            {},
            parsed,
            loot_id="loot_gold_0",
            character_id="char-1",
            character_name="Tester",
            equipment={"gold": 2},
        )
    assert exc.value.status_code == 404


def test_grant_loot_to_equipment_adds_item_to_correct_bucket():
    equipment = grant_loot_to_equipment(
        {"gold": 0, "weapons": [], "gear": []},
        {
            "name": "Longsword",
            "category": "weapon",
            "item": {"name": "Longsword", "damage": "1d8"},
        },
    )

    assert equipment["weapons"][0]["name"] == "Longsword"
    assert equipment["weapons"][0]["damage"] == "1d8"
    assert equipment["weapons"][0]["equipped"] is False


def test_claim_gold_can_split_across_party():
    parsed = {"key_rewards": ["11 gp"]}
    state = discover_loot_item({}, parsed, loot_id="loot_gold_0")
    result = claim_loot_item(
        state,
        parsed,
        loot_id="loot_gold_0",
        character_id="char-1",
        character_name="Leader",
        equipment={"gold": 1},
        claim_mode="split_party",
        split_targets=[
            {"character_id": "char-1", "character_name": "Leader", "equipment": {"gold": 1}},
            {"character_id": "char-2", "character_name": "Scout", "equipment": {"gold": 2}},
        ],
    )

    assert result["equipment_updates"]["char-1"]["gold"] == 7
    assert result["equipment_updates"]["char-2"]["gold"] == 7
    assert result["split_allocations"] == [
        {"character_id": "char-1", "character_name": "Leader", "amount": 6},
        {"character_id": "char-2", "character_name": "Scout", "amount": 5},
    ]
    item = result["game_state"]["loot_pool"]["items"][0]
    assert item["status"] == "claimed"
    assert item["claim_mode"] == "split_party"
    assert item["split_allocations"] == result["split_allocations"]


def test_claim_item_can_be_marked_as_party_stash():
    parsed = {"key_rewards": ["Gate Token"]}
    state = discover_loot_item({}, parsed, loot_id="loot_gear_gate_token_0")
    result = claim_loot_item(
        state,
        parsed,
        loot_id="loot_gear_gate_token_0",
        character_id="char-1",
        character_name="Leader",
        equipment={"gold": 1, "gear": []},
        claim_mode="party_stash",
    )

    assert result["equipment"] == {"gold": 1, "gear": []}
    item = result["game_state"]["loot_pool"]["items"][0]
    assert item["status"] == "claimed"
    assert item["claim_mode"] == "party_stash"
    assert item["shared_with_party"] is True
    assert item["claimed_by_character_id"] == "char-1"


def test_roll_party_item_awards_highest_roll_and_records_results():
    rolls = iter([7, 18])

    def roller(_notation):
        return {"rolls": [next(rolls)], "total": 0}

    parsed = {"key_rewards": ["Gate Token"]}
    state = discover_loot_item({}, parsed, loot_id="loot_gear_gate_token_0")
    result = claim_loot_item(
        state,
        parsed,
        loot_id="loot_gear_gate_token_0",
        character_id="char-1",
        character_name="Leader",
        equipment={"gold": 1, "gear": []},
        claim_mode="roll_party",
        split_targets=[
            {"character_id": "char-1", "character_name": "Leader", "equipment": {"gold": 1, "gear": []}},
            {"character_id": "char-2", "character_name": "Scout", "equipment": {"gold": 2, "gear": []}},
        ],
        roll_dice_func=roller,
    )

    assert "char-1" not in result["equipment_updates"]
    assert result["equipment_updates"]["char-2"]["gear"][0]["name"] == "Gate Token"
    assert result["roll_allocations"] == [
        {"character_id": "char-1", "character_name": "Leader", "d20": 7, "winner": False},
        {"character_id": "char-2", "character_name": "Scout", "d20": 18, "winner": True},
    ]
    item = result["game_state"]["loot_pool"]["items"][0]
    assert item["claim_mode"] == "roll_party"
    assert item["claimed_by_character_id"] == "char-2"
    assert item["claimed_by_name"] == "Scout"
    assert item["roll_allocations"] == result["roll_allocations"]
