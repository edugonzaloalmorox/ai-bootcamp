import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pydantic_ai.messages import FunctionToolCallEvent
from wikiagent.wikiagent import build_wikipedia_agent
from wikiagent import tools


@pytest.fixture
def mock_tools(monkeypatch):
    """Mock both Wikipedia tools so we don't hit the network."""
    calls = {"search": 0, "get_page": 0}

    def fake_search(query: str, limit: int = 5):
        calls["search"] += 1
        return [
            {"title": "Capybara", "snippet": "Largest living rodent."},
            {"title": "Hydrochoerus", "snippet": "Genus of capybaras."},
        ]

    def fake_get_page(title: str) -> str:
        calls["get_page"] += 1
        return f"{title} lives in South America near water."

    monkeypatch.setattr(tools, "wikipedia_search", fake_search)
    monkeypatch.setattr(tools, "wikipedia_get_page", fake_get_page)
    return calls


@pytest.mark.asyncio
async def test_agent_invokes_tools_and_includes_references(mock_tools):
    calls = mock_tools
    agent = build_wikipedia_agent()
    events = []

    async with agent.run_stream("where do capybaras live?") as result:
        chunks: list[str] = []

        async for chunk in result.stream_text():
            # If you still want to record “events”, keep collecting here
            events.append(chunk)
            chunks.append(chunk)

    # Final answer = concatenation of all streamed text
    final_answer = "".join(chunks)

    # 1) search tool invoked
    assert calls["search"] == 1

    # 2) get_page invoked multiple times
    assert calls["get_page"] >= 2

    # 3) references included in final answer
    assert "(source:" in final_answer
