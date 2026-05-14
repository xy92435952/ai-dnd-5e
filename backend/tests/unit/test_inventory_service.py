import pytest

from services import inventory_service


def test_buy_gear_deducts_gold_and_does_not_mutate_input():
    original = {"gold": 51, "gear": []}

    result = inventory_service.buy_item(
        original,
        item_name="Healing Potion",
        item_category="gear",
        quantity=1,
    )

    assert original == {"gold": 51, "gear": []}
    assert result["bought"] == "Healing Potion"
    assert result["gold_remaining"] == 1
    assert result["equipment"]["gold"] == 1
    assert [item["name"] for item in result["equipment"]["gear"]] == ["Healing Potion"]


def test_buy_rejects_non_positive_quantity():
    with pytest.raises(inventory_service.InventoryError, match="购买数量"):
        inventory_service.buy_item(
            {"gold": 51, "gear": []},
            item_name="Healing Potion",
            item_category="gear",
            quantity=0,
        )


def test_sell_equipped_weapon_is_rejected():
    equipment = {
        "gold": 10,
        "weapons": [
            {"name": "Longsword", "zh": "长剑", "cost": 15, "equipped": True},
        ],
    }

    with pytest.raises(inventory_service.InventoryError, match="不能出售装备中的武器"):
        inventory_service.sell_item(
            equipment,
            item_name="Longsword",
            item_category="weapon",
            item_index=0,
        )


def test_sell_duplicate_gear_uses_requested_match_index():
    equipment = {
        "gold": 0,
        "gear": [
            {"name": "Rope", "zh": "旧绳索", "cost": 1},
            {"name": "Rope", "zh": "新绳索", "cost": 2},
        ],
    }

    result = inventory_service.sell_item(
        equipment,
        item_name="Rope",
        item_category="gear",
        item_index=1,
    )

    assert result["sell_price"] == 1
    assert result["equipment"]["gold"] == 1
    assert result["equipment"]["gear"] == [
        {"name": "Rope", "zh": "旧绳索", "cost": 1},
    ]


def test_transfer_unequipped_shield_uses_shield_slot():
    source = {
        "gold": 10,
        "shield": {"name": "Shield", "zh": "盾牌", "ac": 2, "equipped": False},
    }
    target = {"gold": 0, "gear": [], "shield": None}

    result = inventory_service.transfer_item(
        source,
        target,
        item_name="Shield",
        item_category="shield",
        item_index=0,
    )

    assert result["transferred"] == "Shield"
    assert result["source_equipment"]["shield"] is None
    assert result["target_equipment"]["shield"]["name"] == "Shield"
    assert source["shield"]["name"] == "Shield"
    assert target["shield"] is None


def test_update_gold_rejects_spending_more_than_available():
    with pytest.raises(inventory_service.InventoryError, match="金币不足"):
        inventory_service.update_gold({"gold": 3}, amount=-5)


def test_update_ammo_clamps_to_zero_and_preserves_other_equipment():
    equipment = {
        "gold": 10,
        "weapons": [
            {"name": "Longbow", "zh": "长弓", "ammo": 1},
            {"name": "Longsword", "zh": "长剑"},
        ],
        "gear": [{"name": "Rope"}],
    }

    result = inventory_service.update_ammo(equipment, weapon_name="Longbow", change=-3)

    assert result["ammo"] == 0
    assert result["equipment"]["weapons"][0]["ammo"] == 0
    assert result["equipment"]["weapons"][1] == {"name": "Longsword", "zh": "长剑"}
    assert result["equipment"]["gear"] == [{"name": "Rope"}]
    assert equipment["weapons"][0]["ammo"] == 1


def test_update_equipment_equips_one_armor_and_unequips_other_armor():
    equipment = {
        "armor": [
            {"name": "Leather", "equipped": True},
            {"name": "Chain Mail", "equipped": False},
        ],
    }

    result = inventory_service.update_equipment(
        equipment,
        item_name="Chain Mail",
        item_category="armor",
        equip=True,
    )

    assert result["equipment"]["armor"] == [
        {"name": "Leather", "equipped": False},
        {"name": "Chain Mail", "equipped": True},
    ]


def test_update_equipment_toggles_shield_slot():
    equipment = {
        "shield": {"name": "Shield", "zh": "盾牌", "ac": 2, "equipped": False},
    }

    result = inventory_service.update_equipment(
        equipment,
        item_name="Shield",
        item_category="shield",
        equip=True,
    )

    assert result["equipment"]["shield"]["equipped"] is True


def test_prepare_gear_item_use_merges_shop_defaults_for_legacy_string_item():
    prepared = inventory_service.prepare_gear_item_use(
        {"gear": ["Healing Potion"]},
        item_name="Healing Potion",
    )

    assert prepared.item_index == 0
    assert prepared.item_data["name"] == "Healing Potion"
    assert prepared.item_data["effect"] == "heal"


def test_consume_gear_item_use_decrements_uses_without_removing_item():
    prepared = inventory_service.prepare_gear_item_use(
        {"gear": [{"name": "Healer's Kit", "uses": 3}]},
        item_name="Healer's Kit",
    )

    result = inventory_service.consume_gear_item_use(prepared)

    assert result["uses_remaining"] == 2
    assert result["equipment"]["gear"] == [{"name": "Healer's Kit", "uses": 2}]


def test_prepare_gear_item_use_rejects_missing_item():
    with pytest.raises(inventory_service.InventoryError, match="背包中未找到物品"):
        inventory_service.prepare_gear_item_use(
            {"gear": []},
            item_name="Healing Potion",
        )
