from services import llm


class FakeSettings:
    llm_api_key = "test-key"
    llm_base_url = "https://example.test/v1"
    llm_model = "dm-model"
    llm_fast_model = "fast-model"
    llm_module_model = "module-model"


def test_resolve_model_uses_task_specific_model(monkeypatch):
    monkeypatch.setattr(llm, "settings", FakeSettings())

    assert llm.resolve_model("fast") == "fast-model"
    assert llm.resolve_model("module") == "module-model"
    assert llm.resolve_model("dm") == "dm-model"
    assert llm.resolve_model("unknown") == "dm-model"


def test_get_llm_passes_task_model(monkeypatch):
    seen = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr(llm, "settings", FakeSettings())
    monkeypatch.setattr(llm, "ChatOpenAI", FakeChatOpenAI)

    llm.get_llm(task="fast", temperature=0.1, max_tokens=99)

    assert seen["model"] == "fast-model"
    assert seen["temperature"] == 0.1
    assert seen["max_tokens"] == 99
