"""Unit tests for graph/nodes/tavily_search helpers."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

mod = importlib.import_module("graph.nodes.tavily_search")




def test_manufacturer_looks_unsure_exact():
    assert mod._manufacturer_looks_unsure("not sure") is True
    assert mod._manufacturer_looks_unsure("unknown") is True
    assert mod._manufacturer_looks_unsure("none") is True


def test_manufacturer_looks_unsure_does_not_match_substring():
    assert mod._manufacturer_looks_unsure("Nonexistent") is False
    assert mod._manufacturer_looks_unsure("Kohler") is False


def test_manufacturer_looks_unsure_phrase():
    assert mod._manufacturer_looks_unsure("I don't know the brand") is True
    assert mod._manufacturer_looks_unsure("no brand listed") is True


def test_interpret_manufacturer_fallback_brand():
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("offline")
    with patch.object(mod, "llm", return_value=llm):
        assert mod._interpret_manufacturer("Kohler") == "Kohler"
        assert mod._interpret_manufacturer("not sure") is None


def test_find_component_by_type():
    info = {
        "Components": [
            {"ComponentId": "1", "Type": "SINK"},
            {"ComponentId": "2", "Type": "TOILET"},
        ]
    }
    found = mod._find_component_by_type(info, "toilet")
    assert found["ComponentId"] == "2"
    assert mod._find_component_by_type(info, "DISHWASHER") is None


def test_tavily_search_concise_limits_results(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key

        def search(self, **kwargs):
            captured["kwargs"] = kwargs
            return {
                "results": [
                    {"title": "A", "content": "one", "url": "https://a"},
                    {"title": "B", "content": "two", "url": "https://b"},
                ]
            }

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setattr(mod, "TavilyClient", FakeClient)
    text = mod._tavily_search("leaky sink", preference="concise")
    assert captured["kwargs"]["max_results"] == 2
    assert captured["kwargs"]["search_depth"] == "basic"
    assert "A" in text


def test_tavily_search_detail_uses_advanced(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, api_key):
            pass

        def search(self, **kwargs):
            captured["kwargs"] = kwargs
            return {"answer": "Long answer", "results": []}

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setattr(mod, "TavilyClient", FakeClient)
    text = mod._tavily_search("leaky sink", preference="detail")
    assert captured["kwargs"]["max_results"] == 8
    assert captured["kwargs"]["search_depth"] == "advanced"
    assert captured["kwargs"]["include_answer"] is True
    assert "Long answer" in text
