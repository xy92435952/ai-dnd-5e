import pytest

from services.graphs import dm_agent


class FakeStateGraph:
    compile_calls = 0

    def __init__(self, state_type):
        self.state_type = state_type

    def add_node(self, *args, **kwargs):
        pass

    def set_entry_point(self, *args, **kwargs):
        pass

    def add_conditional_edges(self, *args, **kwargs):
        pass

    def add_edge(self, *args, **kwargs):
        pass

    def compile(self, **kwargs):
        type(self).compile_calls += 1
        return {"graph": type(self).compile_calls, **kwargs}


@pytest.mark.asyncio
async def test_build_dm_agent_graph_reuses_compiled_graph(monkeypatch):
    async def fake_get_memory_saver():
        return "memory"

    FakeStateGraph.compile_calls = 0
    monkeypatch.setattr(dm_agent, "_compiled_graph", None, raising=False)
    monkeypatch.setattr(dm_agent, "StateGraph", FakeStateGraph)
    monkeypatch.setattr(dm_agent, "get_memory_saver", fake_get_memory_saver)

    first = await dm_agent.build_dm_agent_graph()
    second = await dm_agent.build_dm_agent_graph()

    assert first is second
    assert FakeStateGraph.compile_calls == 1
