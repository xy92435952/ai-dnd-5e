from services.combat_spell_aoe_geometry_service import filter_spell_aoe_targets


def test_line_template_filters_targets_against_direction_anchor():
    result = filter_spell_aoe_targets(
        spell={
            "name": "Lightning Bolt",
            "aoe": True,
            "desc": "100 ft line",
        },
        target_ids=["line-near", "line-far", "off-line", "behind"],
        positions={
            "caster": {"x": 5, "y": 5},
            "line-near": {"x": 6, "y": 5},
            "line-far": {"x": 12, "y": 5},
            "off-line": {"x": 6, "y": 6},
            "behind": {"x": 4, "y": 5},
        },
        caster_id="caster",
        aoe_center="15_5",
    )

    assert result.geometry_applied is True
    assert result.target_ids == ["line-near", "line-far"]
    assert result.excluded_ids == ["off-line", "behind"]


def test_cone_template_uses_existing_45_degree_grid_shape():
    result = filter_spell_aoe_targets(
        spell={
            "name": "Burning Hands",
            "aoe": True,
            "desc": "15 ft cone",
        },
        target_ids=["front", "front-edge", "side", "behind"],
        positions={
            "caster": {"x": 5, "y": 5},
            "front": {"x": 5, "y": 6},
            "front-edge": {"x": 4, "y": 7},
            "side": {"x": 8, "y": 5},
            "behind": {"x": 5, "y": 4},
        },
        caster_id="caster",
        aoe_center="5_8",
    )

    assert result.target_ids == ["front", "front-edge"]
    assert result.excluded_ids == ["side", "behind"]


def test_cube_template_filters_around_locked_center():
    result = filter_spell_aoe_targets(
        spell={
            "name": "Thunderwave",
            "aoe": True,
            "desc": "15 ft cube",
        },
        target_ids=["inside-a", "inside-b", "outside"],
        positions={
            "caster": {"x": 5, "y": 5},
            "inside-a": {"x": 4, "y": 4},
            "inside-b": {"x": 6, "y": 6},
            "outside": {"x": 7, "y": 7},
        },
        caster_id="caster",
        aoe_center="5_5",
    )

    assert result.target_ids == ["inside-a", "inside-b"]
    assert result.excluded_ids == ["outside"]


def test_chinese_aura_template_uses_caster_position_without_locked_center():
    result = filter_spell_aoe_targets(
        spell={
            "name": "神灵守护",
            "name_en": "Spirit Guardians",
            "aoe": True,
            "range": 3,
            "desc": "15尺内敌人减速，进入区域需WIS豁免。",
        },
        target_ids=["near-a", "near-b", "outside"],
        positions={
            "caster": {"x": 5, "y": 5},
            "near-a": {"x": 7, "y": 5},
            "near-b": {"x": 5, "y": 8},
            "outside": {"x": 9, "y": 5},
        },
        caster_id="caster",
        aoe_center=None,
    )

    assert result.geometry_applied is True
    assert result.target_ids == ["near-a", "near-b"]
    assert result.excluded_ids == ["outside"]


def test_missing_direction_anchor_preserves_legacy_target_list():
    result = filter_spell_aoe_targets(
        spell={
            "name": "Lightning Bolt",
            "aoe": True,
            "desc": "100 ft line",
        },
        target_ids=["target-a", "target-b"],
        positions={
            "caster": {"x": 5, "y": 5},
            "target-a": {"x": 6, "y": 5},
            "target-b": {"x": 6, "y": 6},
        },
        caster_id="caster",
        aoe_center=None,
    )

    assert result.geometry_applied is False
    assert result.target_ids == ["target-a", "target-b"]
    assert result.excluded_ids == []
