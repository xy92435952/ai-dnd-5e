import json

from sqlalchemy.orm.attributes import flag_modified

from models import Character
from services.state_applicator import StateApplicator
from services.loot_service import discover_loot_item


async def _auth_headers(client, sample_user):
    response = await client.post("/auth/login", json={
        "username": sample_user.username,
        "password": "password",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def test_session_loot_can_be_claimed_to_character_inventory(
    client,
    db_session,
    sample_user,
    sample_module,
    sample_session,
    sample_character,
):
    sample_module.parsed_content = {
        "key_rewards": ["25 gp", "Gate Token"],
        "magic_items": [
            {
                "name": "Gate Token",
                "rarity": "common",
                "description": "A brass token.",
            },
        ],
    }
    sample_character.equipment = {"gold": 5, "gear": []}
    flag_modified(sample_module, "parsed_content")
    await db_session.commit()
    headers = await _auth_headers(client, sample_user)

    loot_response = await client.get(
        f"/game/sessions/{sample_session.id}/loot",
        headers=headers,
    )
    assert loot_response.status_code == 200, loot_response.text
    loot = loot_response.json()
    assert loot["items"] == []

    sample_session.game_state = discover_loot_item(
        sample_session.game_state or {},
        sample_module.parsed_content,
        loot_id="loot_gold_0",
    )
    sample_session.game_state = discover_loot_item(
        sample_session.game_state,
        sample_module.parsed_content,
        loot_id="loot_gear_gate_token_1",
    )
    flag_modified(sample_session, "game_state")
    await db_session.commit()

    gold_response = await client.post(
        f"/game/sessions/{sample_session.id}/loot/claim",
        headers=headers,
        json={
            "character_id": sample_character.id,
            "loot_id": "loot_gold_0",
        },
    )
    assert gold_response.status_code == 200, gold_response.text
    data = gold_response.json()
    assert data["equipment"]["gold"] == 30
    assert data["loot_pool"]["items"][0]["status"] == "claimed"

    item_response = await client.post(
        f"/game/sessions/{sample_session.id}/loot/claim",
        headers=headers,
        json={
            "character_id": sample_character.id,
            "loot_id": "loot_gear_gate_token_1",
        },
    )
    assert item_response.status_code == 200, item_response.text
    item_data = item_response.json()
    assert [item["name"] for item in item_data["equipment"]["gear"]] == ["Gate Token"]
    assert item_data["loot_pool"]["items"][1]["claimed_by_character_id"] == sample_character.id


async def test_dm_loot_discovery_reveals_then_claims_hidden_module_reward(
    client,
    db_session,
    sample_user,
    sample_module,
    sample_session,
    sample_character,
):
    sample_module.parsed_content = {
        "key_rewards": ["25 gp"],
        "magic_items": [
            {
                "name": "Moonblade",
                "category": "weapon",
                "rarity": "rare",
                "description": "A silver blade that drinks in moonlight.",
            },
        ],
    }
    sample_character.equipment = {"gold": 0, "gear": [], "weapons": []}
    sample_session.game_state = {}
    flag_modified(sample_module, "parsed_content")
    flag_modified(sample_session, "game_state")
    await db_session.commit()
    headers = await _auth_headers(client, sample_user)

    hidden_loot_response = await client.get(
        f"/game/sessions/{sample_session.id}/loot",
        headers=headers,
    )
    assert hidden_loot_response.status_code == 200, hidden_loot_response.text
    assert hidden_loot_response.json()["items"] == []

    hidden_session_response = await client.get(
        f"/game/sessions/{sample_session.id}",
        headers=headers,
    )
    assert hidden_session_response.status_code == 200, hidden_session_response.text
    assert hidden_session_response.json()["game_state"]["loot_pool"]["items"] == []

    await StateApplicator(db_session).apply(
        sample_session,
        json.dumps({
            "narrative": "Behind the altar stone, moonlight catches on a silver blade.",
            "state_delta": {
                "loot_discoveries": [
                    {
                        "loot_id": "loot_weapon_moonblade_1",
                        "reason": "Discovered behind the altar stone",
                    }
                ],
            },
            "player_choices": [],
        }),
        characters=[sample_character],
    )
    await db_session.commit()

    discovered_loot_response = await client.get(
        f"/game/sessions/{sample_session.id}/loot",
        headers=headers,
    )
    assert discovered_loot_response.status_code == 200, discovered_loot_response.text
    discovered_items = discovered_loot_response.json()["items"]
    assert [item["name"] for item in discovered_items] == ["Moonblade"]
    assert discovered_items[0]["status"] == "available"
    assert discovered_items[0]["discovered"] is True
    assert discovered_items[0]["discovery_reason"] == "Discovered behind the altar stone"

    discovered_session_response = await client.get(
        f"/game/sessions/{sample_session.id}",
        headers=headers,
    )
    assert discovered_session_response.status_code == 200, discovered_session_response.text
    assert [
        item["name"]
        for item in discovered_session_response.json()["game_state"]["loot_pool"]["items"]
    ] == ["Moonblade"]

    claim_response = await client.post(
        f"/game/sessions/{sample_session.id}/loot/claim",
        headers=headers,
        json={
            "character_id": sample_character.id,
            "loot_id": "loot_weapon_moonblade_1",
        },
    )
    assert claim_response.status_code == 200, claim_response.text
    claim_data = claim_response.json()
    assert [item["name"] for item in claim_data["equipment"]["weapons"]] == ["Moonblade"]
    assert claim_data["loot_pool"]["items"][0]["status"] == "claimed"
    assert claim_data["loot_pool"]["items"][0]["claimed_by_character_id"] == sample_character.id


async def test_session_loot_rejects_duplicate_claim(
    client,
    db_session,
    sample_user,
    sample_module,
    sample_session,
    sample_character,
):
    sample_module.parsed_content = {"key_rewards": ["10 gp"]}
    sample_character.equipment = {"gold": 0, "gear": []}
    flag_modified(sample_module, "parsed_content")
    sample_session.game_state = discover_loot_item(
        sample_session.game_state or {},
        sample_module.parsed_content,
        loot_id="loot_gold_0",
    )
    flag_modified(sample_session, "game_state")
    await db_session.commit()
    headers = await _auth_headers(client, sample_user)

    first = await client.post(
        f"/game/sessions/{sample_session.id}/loot/claim",
        headers=headers,
        json={"character_id": sample_character.id, "loot_id": "loot_gold_0"},
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        f"/game/sessions/{sample_session.id}/loot/claim",
        headers=headers,
        json={"character_id": sample_character.id, "loot_id": "loot_gold_0"},
    )
    assert second.status_code == 409


async def test_session_loot_can_split_gold_across_party(
    client,
    db_session,
    sample_user,
    sample_module,
    sample_session,
    sample_character,
):
    companion = Character(
        id="loot-split-companion",
        session_id=sample_session.id,
        user_id=None,
        is_player=False,
        name="Loot Split Companion",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 10, "ac": 10},
        hp_current=10,
        equipment={"gold": 2, "gear": []},
    )
    sample_module.parsed_content = {"key_rewards": ["11 gp"]}
    sample_character.equipment = {"gold": 1, "gear": []}
    sample_session.game_state = {"companion_ids": [companion.id]}
    sample_session.game_state = discover_loot_item(
        sample_session.game_state,
        sample_module.parsed_content,
        loot_id="loot_gold_0",
    )
    db_session.add(companion)
    flag_modified(sample_module, "parsed_content")
    flag_modified(sample_session, "game_state")
    await db_session.commit()
    headers = await _auth_headers(client, sample_user)

    response = await client.post(
        f"/game/sessions/{sample_session.id}/loot/claim",
        headers=headers,
        json={
            "character_id": sample_character.id,
            "loot_id": "loot_gold_0",
            "claim_mode": "split_party",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["equipment_updates"][sample_character.id]["gold"] == 7
    assert data["equipment_updates"][companion.id]["gold"] == 7
    assert data["split_allocations"] == [
        {"character_id": sample_character.id, "character_name": sample_character.name, "amount": 6},
        {"character_id": companion.id, "character_name": companion.name, "amount": 5},
    ]
    assert data["loot_pool"]["items"][0]["claim_mode"] == "split_party"


async def test_session_loot_can_mark_item_as_party_stash(
    client,
    db_session,
    sample_user,
    sample_module,
    sample_session,
    sample_character,
):
    sample_module.parsed_content = {"key_rewards": ["Gate Token"]}
    sample_character.equipment = {"gold": 1, "gear": []}
    flag_modified(sample_module, "parsed_content")
    sample_session.game_state = discover_loot_item(
        sample_session.game_state or {},
        sample_module.parsed_content,
        loot_id="loot_gear_gate_token_0",
    )
    flag_modified(sample_session, "game_state")
    await db_session.commit()
    headers = await _auth_headers(client, sample_user)

    response = await client.post(
        f"/game/sessions/{sample_session.id}/loot/claim",
        headers=headers,
        json={
            "character_id": sample_character.id,
            "loot_id": "loot_gear_gate_token_0",
            "claim_mode": "party_stash",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    item = data["loot_pool"]["items"][0]
    assert item["claim_mode"] == "party_stash"
    assert item["shared_with_party"] is True
    assert data["equipment"]["gear"] == []


async def test_session_loot_can_roll_item_across_party(
    client,
    db_session,
    sample_user,
    sample_module,
    sample_session,
    sample_character,
):
    companion = Character(
        id="loot-roll-companion",
        session_id=sample_session.id,
        user_id=None,
        is_player=False,
        name="Loot Roll Companion",
        race="Human",
        char_class="Fighter",
        level=1,
        ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        derived={"hp_max": 10, "ac": 10},
        hp_current=10,
        equipment={"gold": 2, "gear": []},
    )
    sample_module.parsed_content = {"key_rewards": ["Gate Token"]}
    sample_character.equipment = {"gold": 1, "gear": []}
    sample_session.game_state = {"companion_ids": [companion.id]}
    sample_session.game_state = discover_loot_item(
        sample_session.game_state,
        sample_module.parsed_content,
        loot_id="loot_gear_gate_token_0",
    )
    db_session.add(companion)
    flag_modified(sample_module, "parsed_content")
    flag_modified(sample_session, "game_state")
    await db_session.commit()
    headers = await _auth_headers(client, sample_user)

    response = await client.post(
        f"/game/sessions/{sample_session.id}/loot/claim",
        headers=headers,
        json={
            "character_id": sample_character.id,
            "loot_id": "loot_gear_gate_token_0",
            "claim_mode": "roll_party",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    winner = next(allocation for allocation in data["roll_allocations"] if allocation["winner"])
    assert winner["character_id"] in {sample_character.id, companion.id}
    assert data["character_id"] == winner["character_id"]
    assert data["equipment_updates"][winner["character_id"]]["gear"][0]["name"] == "Gate Token"
    assert data["loot_pool"]["items"][0]["claim_mode"] == "roll_party"
    assert data["loot_pool"]["items"][0]["claimed_by_character_id"] == winner["character_id"]
