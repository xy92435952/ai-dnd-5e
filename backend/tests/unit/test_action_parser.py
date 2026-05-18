import pytest

from services.action_parser import parse_combat_action


def _state():
    return {
        "characters": [
            {"id": "pc-1", "name": "洛温", "hp_current": 12, "hp_max": 12},
            {"id": "ally-1", "name": "米拉", "hp_current": 8, "hp_max": 10},
        ],
        "enemies": [
            {"id": "skel-1", "name": "潮湿骷髅", "hp_current": 7, "hp_max": 7},
            {"id": "rat-1", "name": "巨鼠", "hp_current": 5, "hp_max": 5},
        ],
    }


def _positions():
    return {
        "pc-1": {"x": 2, "y": 3},
        "ally-1": {"x": 2, "y": 4},
        "skel-1": {"x": 7, "y": 3},
        "rat-1": {"x": 12, "y": 9},
    }


def _far_positions():
    return {
        "pc-1": {"x": 2, "y": 3},
        "ally-1": {"x": 2, "y": 4},
        "skel-1": {"x": 17, "y": 8},
        "rat-1": {"x": 12, "y": 9},
    }


@pytest.mark.asyncio
async def test_local_parser_handles_move_and_attack_without_llm(monkeypatch):
    async def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("LLM should not be called for common move+attack intent")

    monkeypatch.setattr("services.action_parser._parse_with_llm", fail_if_llm_called)

    result = await parse_combat_action(
        player_input="我向最近的潮湿骷髅移动并用长剑攻击它。",
        game_state=_state(),
        player_id="pc-1",
        player_data={"name": "洛温"},
        positions=_positions(),
        move_remaining=6,
    )

    assert result["_fallback"] is False
    assert result["actions"] == [
        {"type": "move", "target_id": "skel-1", "target_pos": None, "reason": "靠近目标"},
        {"type": "attack", "target_id": "skel-1", "is_ranged": False, "reason": "近战攻击"},
    ]


@pytest.mark.asyncio
async def test_local_parser_attacks_adjacent_enemy_without_move(monkeypatch):
    async def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("LLM should not be called for adjacent attack")

    monkeypatch.setattr("services.action_parser._parse_with_llm", fail_if_llm_called)
    positions = _positions()
    positions["skel-1"] = {"x": 3, "y": 3}

    result = await parse_combat_action(
        player_input="我用长剑攻击身旁的潮湿骷髅。",
        game_state=_state(),
        player_id="pc-1",
        player_data={"name": "洛温"},
        positions=positions,
        move_remaining=6,
    )

    assert result["actions"] == [
        {"type": "attack", "target_id": "skel-1", "is_ranged": False, "reason": "近战攻击"},
    ]


@pytest.mark.asyncio
async def test_llm_timeout_fallback_moves_toward_nearest_enemy_then_attacks(monkeypatch):
    async def timeout_llm(*args, **kwargs):
        raise TimeoutError("simulated")

    monkeypatch.setattr("services.action_parser._parse_with_llm", timeout_llm)

    result = await parse_combat_action(
        player_input="我冲过去攻击。",
        game_state=_state(),
        player_id="pc-1",
        player_data={"name": "洛温"},
        positions=_positions(),
        move_remaining=6,
    )

    assert result["_fallback"] is True
    assert result["actions"] == [
        {"type": "move", "target_id": "skel-1", "target_pos": None, "reason": "靠近最近敌人"},
        {"type": "attack", "target_id": "skel-1", "is_ranged": False, "reason": "我冲过去攻击。"},
    ]


@pytest.mark.asyncio
async def test_unreachable_melee_target_moves_only_without_fake_attack(monkeypatch):
    async def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("LLM should not be called for common move+attack intent")

    monkeypatch.setattr("services.action_parser._parse_with_llm", fail_if_llm_called)

    result = await parse_combat_action(
        player_input="我向最近的潮湿骷髅移动并用长剑攻击它。",
        game_state=_state(),
        player_id="pc-1",
        player_data={"name": "洛温"},
        positions=_far_positions(),
        move_remaining=6,
    )

    assert result["actions"] == [
        {
            "type": "move",
            "target_id": "skel-1",
            "target_pos": None,
            "reason": "靠近目标",
            "followup_hint": "已靠近，下一回合可继续攻击",
        },
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("text", "expected"), [
    ("我采取闪避动作", {"type": "dodge"}),
    ("我使用冲刺", {"type": "dash"}),
    ("我脱离接战后退", {"type": "disengage"}),
])
async def test_local_parser_handles_common_tactical_actions_without_llm(monkeypatch, text, expected):
    async def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("LLM should not be called for common tactical actions")

    monkeypatch.setattr("services.action_parser._parse_with_llm", fail_if_llm_called)

    result = await parse_combat_action(
        player_input=text,
        game_state=_state(),
        player_id="pc-1",
        player_data={"name": "洛温"},
        positions=_positions(),
        move_remaining=6,
    )

    assert result["_fallback"] is False
    assert result["actions"] == [expected]


@pytest.mark.asyncio
async def test_local_parser_handles_help_action_with_named_ally_without_llm(monkeypatch):
    async def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("LLM should not be called for common help action")

    monkeypatch.setattr("services.action_parser._parse_with_llm", fail_if_llm_called)

    result = await parse_combat_action(
        player_input="我协助米拉攻击潮湿骷髅",
        game_state=_state(),
        player_id="pc-1",
        player_data={"name": "洛温"},
        positions=_positions(),
        move_remaining=6,
    )

    assert result["_fallback"] is False
    assert result["actions"] == [{"type": "help", "target_id": "ally-1", "reason": "协助盟友"}]


@pytest.mark.asyncio
async def test_local_parser_handles_cover_movement_to_coordinates_without_llm(monkeypatch):
    async def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("LLM should not be called for coordinate cover movement")

    monkeypatch.setattr("services.action_parser._parse_with_llm", fail_if_llm_called)

    result = await parse_combat_action(
        player_input="我移动到 8,3 的掩体后",
        game_state=_state(),
        player_id="pc-1",
        player_data={"name": "洛温"},
        positions=_positions(),
        move_remaining=6,
    )

    assert result["_fallback"] is False
    assert result["actions"] == [{
        "type": "move",
        "target_id": None,
        "target_pos": {"x": 8, "y": 3},
        "reason": "移动到掩体后",
    }]
