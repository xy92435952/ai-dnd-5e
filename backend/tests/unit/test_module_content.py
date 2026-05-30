from services.module_content import get_first_scene_description, normalize_module_content


def test_normalize_module_content_accepts_json_string():
    parsed = normalize_module_content('{"setting": "Mine", "scenes": []}')

    assert parsed == {"setting": "Mine", "scenes": []}


def test_first_scene_description_handles_parser_variants():
    assert get_first_scene_description({
        "scenes": [{"title": "Gate", "description": "Rain at the gate."}],
    }) == "Rain at the gate."
    assert get_first_scene_description({
        "scenes": [{"title": "Gate Without Description"}],
    }) == "Gate Without Description"
    assert get_first_scene_description({
        "scenes": ["A plain scene line."],
    }) == "A plain scene line."
    assert get_first_scene_description({"scenes": "not a list"}) == ""
