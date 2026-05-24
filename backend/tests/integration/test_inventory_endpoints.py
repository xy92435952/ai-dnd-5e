import pytest
from models import Character, CombatState


async def _auth_headers(client, sample_user):
    response = await client.post("/auth/login", json={
        "username": sample_user.username,
        "password": "password",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture(autouse=True)
async def _auth_inventory_client(client, sample_user):
    client.headers.update(await _auth_headers(client, sample_user))
    yield
    client.headers.clear()


@pytest.mark.asyncio
async def test_buy_item_deducts_gold_and_adds_gear(client, db_session, sample_character):
    sample_character.equipment = {"gold": 51, "gear": []}
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/shop/buy",
        json={
            "item_name": "Healing Potion",
            "item_category": "gear",
            "quantity": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["bought"] == "Healing Potion"
    assert data["gold_remaining"] == 1
    assert data["equipment"]["gold"] == 1
    assert [item["name"] for item in data["equipment"]["gear"]] == ["Healing Potion"]


@pytest.mark.asyncio
async def test_buy_item_rejects_non_positive_quantity(client, db_session, sample_character):
    sample_character.equipment = {"gold": 51, "gear": []}
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/shop/buy",
        json={
            "item_name": "Healing Potion",
            "item_category": "gear",
            "quantity": -1,
        },
    )

    assert response.status_code == 400
    assert "购买数量" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sell_item_rejects_equipped_weapon(client, db_session, sample_character):
    sample_character.equipment = {
        "gold": 10,
        "weapons": [
            {"name": "Longsword", "zh": "长剑", "cost": 15, "equipped": True},
        ],
    }
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/shop/sell",
        json={
            "item_name": "Longsword",
            "item_category": "weapon",
            "item_index": 0,
        },
    )

    assert response.status_code == 400
    assert "不能出售装备中的武器" in response.json()["detail"]


@pytest.mark.asyncio
async def test_equipping_shield_recalculates_ac(client, db_session, sample_character):
    sample_character.equipment = {
        "gold": 10,
        "armor": [],
        "shield": {"name": "Shield", "zh": "盾牌", "ac": 2, "equipped": False},
    }
    await db_session.commit()

    response = await client.patch(
        f"/characters/{sample_character.id}/equipment",
        json={
            "item_name": "Shield",
            "item_category": "shield",
            "equip": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["equipment"]["shield"]["equipped"] is True
    assert data["ac"] >= 12


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
async def test_use_fire_resistance_potion_adds_condition_and_consumes_item(
    client, db_session, sample_character,
):
    sample_character.conditions = []
    sample_character.equipment = {
        "gold": 10,
        "gear": [
            {
                "name": "Potion of Fire Resistance",
                "zh": "火焰抗性药水",
                "consumable": True,
                "effect": "fire_resistance",
            }
        ],
    }
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/use-item",
        json={"item_name": "Potion of Fire Resistance"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["added_condition"] == "fire_resistance"
    assert data["conditions"] == ["fire_resistance"]
    assert data["equipment"]["gear"] == []
    await db_session.refresh(sample_character)
    assert sample_character.conditions == ["fire_resistance"]


@pytest.mark.asyncio
async def test_use_healers_kit_stabilizes_target_and_decrements_uses(
    client, db_session, sample_character, sample_session,
):
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
        hp_current=0,
        death_saves={"successes": 1, "failures": 2, "stable": False},
        equipment={"gold": 0, "gear": []},
    )
    sample_character.equipment = {
        "gold": 10,
        "gear": [
            {
                "name": "Healer's Kit",
                "zh": "医疗包",
                "consumable": True,
                "uses": 10,
            }
        ],
    }
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    response = await client.post(
        f"/characters/{sample_character.id}/use-item",
        json={
            "item_name": "Healer's Kit",
            "target_character_id": target.id,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["effect"] == "stabilize"
    assert data["target_character_id"] == target.id
    assert data["target_name"] == "测试队友"
    assert data["death_saves"] == {"successes": 0, "failures": 0, "stable": True}
    assert data["uses_remaining"] == 9
    assert data["equipment"]["gear"][0]["uses"] == 9
    await db_session.refresh(sample_character)
    await db_session.refresh(target)
    assert sample_character.equipment["gear"][0]["uses"] == 9
    assert target.hp_current == 0
    assert target.death_saves == {"successes": 0, "failures": 0, "stable": True}


@pytest.mark.asyncio
async def test_use_healers_kit_rejects_target_outside_same_session_without_consuming(
    client, db_session, sample_character, sample_session,
):
    target = Character(
        session_id=None,
        user_id=None,
        is_player=False,
        name="未入队角色",
        race="Human",
        char_class="Cleric",
        level=1,
        ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 14, "cha": 10},
        derived={"hp_max": 8, "ac": 12},
        hp_current=0,
        death_saves={"successes": 0, "failures": 2, "stable": False},
        equipment={"gold": 0, "gear": []},
    )
    sample_character.equipment = {
        "gold": 10,
        "gear": [
            {
                "name": "Healer's Kit",
                "zh": "医疗包",
                "consumable": True,
                "uses": 10,
            }
        ],
    }
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    response = await client.post(
        f"/characters/{sample_character.id}/use-item",
        json={
            "item_name": "Healer's Kit",
            "target_character_id": target.id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "character does not belong to this session"
    # The permission layer rejects this before item consumption.
    await db_session.refresh(sample_character)
    await db_session.refresh(target)
    assert sample_character.equipment["gear"][0]["uses"] == 10
    assert target.death_saves == {"successes": 0, "failures": 2, "stable": False}


@pytest.mark.asyncio
async def test_use_item_rejects_consumable_without_direct_effect_without_consuming(
    client, db_session, sample_character,
):
    sample_character.equipment = {
        "gold": 10,
        "gear": [
            {
                "name": "Torch",
                "zh": "火把",
                "consumable": True,
                "description": "照明1小时",
            }
        ],
    }
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/use-item",
        json={"item_name": "Torch"},
    )

    assert response.status_code == 400
    assert "暂不支持直接使用" in response.json()["detail"]
    await db_session.refresh(sample_character)
    assert [item["name"] for item in sample_character.equipment["gear"]] == ["Torch"]


@pytest.mark.asyncio
async def test_use_item_in_combat_consumes_current_turn_action(
    client, db_session, sample_character, sample_session,
):
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
    sample_session.combat_active = True
    combat = CombatState(
        session_id=sample_session.id,
        turn_order=[
            {
                "character_id": sample_character.id,
                "name": sample_character.name,
                "initiative": 15,
                "is_player": True,
                "is_enemy": False,
            },
        ],
        current_turn_index=0,
        turn_states={
            sample_character.id: {
                "action_used": False,
                "bonus_action_used": False,
                "reaction_used": False,
                "movement_used": 0,
                "movement_max": 6,
            },
        },
    )
    db_session.add(combat)
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/use-item",
        json={
            "item_name": "Healing Potion",
            "session_id": sample_session.id,
            "use_in_combat": True,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["turn_state"]["action_used"] is True
    assert data["equipment"]["gear"] == []
    await db_session.refresh(combat)
    assert combat.turn_states[sample_character.id]["action_used"] is True


@pytest.mark.asyncio
async def test_use_item_in_combat_rejects_when_action_already_used(
    client, db_session, sample_character, sample_session,
):
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
    sample_session.combat_active = True
    combat = CombatState(
        session_id=sample_session.id,
        turn_order=[
            {
                "character_id": sample_character.id,
                "name": sample_character.name,
                "initiative": 15,
                "is_player": True,
                "is_enemy": False,
            },
        ],
        current_turn_index=0,
        turn_states={
            sample_character.id: {
                "action_used": True,
                "bonus_action_used": False,
                "reaction_used": False,
                "movement_used": 0,
                "movement_max": 6,
            },
        },
    )
    db_session.add(combat)
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/use-item",
        json={
            "item_name": "Healing Potion",
            "session_id": sample_session.id,
            "use_in_combat": True,
        },
    )

    assert response.status_code == 400
    assert "行动已用尽" in response.json()["detail"]
    await db_session.refresh(sample_character)
    assert len(sample_character.equipment["gear"]) == 1


@pytest.mark.asyncio
async def test_use_item_in_combat_rejects_out_of_turn_without_consuming(
    client, db_session, sample_character, sample_session,
):
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
    sample_session.combat_active = True
    combat = CombatState(
        session_id=sample_session.id,
        turn_order=[
            {
                "character_id": "goblin-1",
                "name": "哥布林",
                "initiative": 16,
                "is_player": False,
                "is_enemy": True,
            },
            {
                "character_id": sample_character.id,
                "name": sample_character.name,
                "initiative": 15,
                "is_player": True,
                "is_enemy": False,
            },
        ],
        current_turn_index=0,
        turn_states={
            sample_character.id: {
                "action_used": False,
                "bonus_action_used": False,
                "reaction_used": False,
                "movement_used": 0,
                "movement_max": 6,
            },
        },
    )
    db_session.add(combat)
    await db_session.commit()

    response = await client.post(
        f"/characters/{sample_character.id}/use-item",
        json={
            "item_name": "Healing Potion",
            "session_id": sample_session.id,
            "use_in_combat": True,
        },
    )

    assert response.status_code == 400
    assert "不是该角色的回合" in response.json()["detail"]
    await db_session.refresh(sample_character)
    assert len(sample_character.equipment["gear"]) == 1


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


@pytest.mark.asyncio
async def test_transfer_item_moves_unequipped_shield_between_session_characters(
    client, db_session, sample_character, sample_session,
):
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
        equipment={"gold": 0, "gear": [], "shield": None},
    )
    sample_character.equipment = {
        "gold": 10,
        "shield": {"name": "Shield", "zh": "盾牌", "ac": 2, "equipped": False},
    }
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    response = await client.post(
        f"/characters/{sample_character.id}/transfer-item",
        json={
            "target_character_id": target.id,
            "item_name": "Shield",
            "item_category": "shield",
            "item_index": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source_equipment"]["shield"] is None
    assert data["target_equipment"]["shield"]["name"] == "Shield"


@pytest.mark.asyncio
async def test_transfer_item_rejects_target_outside_same_session(
    client, db_session, sample_character, sample_session,
):
    target = Character(
        session_id=None,
        user_id=None,
        is_player=False,
        name="未入队角色",
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

    assert response.status_code == 403
    assert response.json()["detail"] == "character does not belong to this session"
