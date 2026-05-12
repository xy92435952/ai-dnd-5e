import pytest
from models import Character


@pytest.mark.asyncio
async def test_use_item_returns_updated_equipment(client, db_session, sample_character):
    sample_character.hp_current = 4
    sample_character.equipment = {
        "gold": 10,
        "gear": [
            {
                "name": "Healing Potion",
                "zh": "治疗药水",
                "consumable": True,
                "effect": "heal",
                "heal_dice": "2d4+2",
            }
        ],
    }
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/use-item",
        json={"item_name": "Healing Potion"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["item"] == "Healing Potion"
    assert data["equipment"]["gear"] == []
    assert data["hp_after"] >= 4


@pytest.mark.asyncio
async def test_transfer_item_moves_gear_between_session_characters(client, db_session, sample_character, sample_session):
    target = Character(
        session_id=sample_session.id,
        user_id=None,
        is_player=False,
        name="测试队友",
        race="Human",
        char_class="Cleric",
        level=1,
        ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 14, "cha": 10},
        derived={"hp_max": 8, "ac": 12},
        hp_current=8,
        equipment={"gold": 0, "gear": []},
    )
    sample_character.equipment = {
        "gold": 10,
        "gear": [
            {"name": "Healing Potion", "zh": "治疗药水", "consumable": True, "cost": 50},
            {"name": "Rope", "zh": "绳索", "cost": 1},
        ],
    }
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    response = await client.post(
        f"/characters/{sample_character.id}/transfer-item",
        json={
          "target_character_id": target.id,
          "item_name": "Healing Potion",
          "item_category": "gear",
          "item_index": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["transferred"] == "Healing Potion"
    assert [item["name"] for item in data["source_equipment"]["gear"]] == ["Rope"]
    assert [item["name"] for item in data["target_equipment"]["gear"]] == ["Healing Potion"]
