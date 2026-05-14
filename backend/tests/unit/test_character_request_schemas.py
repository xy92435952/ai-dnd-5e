from pydantic import ValidationError

from schemas.character_requests import AbilityScores, BuyItemRequest, UseItemRequest


def test_ability_scores_accept_str_and_int_aliases():
    scores = AbilityScores.model_validate({
        "str": 15,
        "dex": 14,
        "con": 13,
        "int": 12,
        "wis": 10,
        "cha": 8,
    })

    assert scores.model_dump(by_alias=True)["str"] == 15
    assert scores.model_dump(by_alias=True)["int"] == 12


def test_ability_scores_reject_out_of_range_value():
    try:
        AbilityScores.model_validate({
            "str": 2,
            "dex": 14,
            "con": 13,
            "int": 12,
            "wis": 10,
            "cha": 8,
        })
    except ValidationError as exc:
        assert "greater than or equal to 3" in str(exc)
    else:
        raise AssertionError("expected validation error")


def test_inventory_request_defaults_stay_stable():
    assert BuyItemRequest(item_name="Torch", item_category="gear").quantity == 1
    assert UseItemRequest(item_name="Healing Potion").use_in_combat is False
