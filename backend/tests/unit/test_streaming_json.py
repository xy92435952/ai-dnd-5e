import json

from services.streaming_json import JsonStringFieldDeltaExtractor, format_sse_event


def test_json_string_field_delta_extractor_streams_narrative_only():
    extractor = JsonStringFieldDeltaExtractor("narrative")
    chunks = [
        '{"action_type":"investigation","nar',
        'rative":"雾气',
        '\\n压低了灯火，\\"门\\"后传来回声"',
        ',"state_delta":{}}',
    ]

    deltas = []
    for chunk in chunks:
        deltas.extend(extractor.feed(chunk))

    assert "".join(deltas) == '雾气\n压低了灯火，"门"后传来回声'
    assert extractor.done is True


def test_json_string_field_delta_extractor_handles_split_unicode_escape():
    extractor = JsonStringFieldDeltaExtractor("narrative")

    assert extractor.feed('{"narrative":"钟声\\u') == ["钟声"]
    assert extractor.feed('5728') == ["在"]
    assert extractor.feed('远处响起"}') == ["远处响起"]


def test_format_sse_event_uses_json_payload_and_event_name():
    payload = {"text": "雾气\n变浓"}
    frame = format_sse_event("narrative_delta", payload)

    assert frame.startswith("event: narrative_delta\n")
    assert frame.endswith("\n\n")
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    assert json.loads(data_line.removeprefix("data: ")) == payload
