"""Unit tests for graph/nodes/common.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from graph.nodes import common as mod


def test_parse_json_blob_raw_object():
    assert mod.parse_json_blob('{"a": 1}') == {"a": 1}


def test_parse_json_blob_embedded():
    assert mod.parse_json_blob('Here you go:\n{"decision":"YES"}\nThanks') == {
        "decision": "YES"
    }


def test_parse_json_blob_array():
    assert mod.parse_json_blob('["wrench", "pliers"]') == ["wrench", "pliers"]


def test_parse_json_blob_invalid():
    assert mod.parse_json_blob("not json") is None


def test_latest_component():
    assert mod.latest_component(None) is None
    assert mod.latest_component({"Components": []}) is None
    assert (
        mod.latest_component({"Components": [{"ComponentId": "1"}, {"ComponentId": "2"}]})
        == {"ComponentId": "1"}
    )


def test_set_active_from_component():
    out = mod.set_active_from_component(
        {},
        {"ComponentId": 9, "ProblemDesc": "leak"},
    )
    assert out["active_component_id"] == "9"
    assert out["hasActiveComponent"] is True
    assert out["hasActiveProblem"] is True


def test_classify_yes_no_uses_llm():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="YES")
    with patch.object(mod, "llm", return_value=llm):
        assert mod.classify_yes_no("yep", "ok?") == "YES"


def test_classify_yes_no_fallback_irrelevant():
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("offline")
    with patch.object(mod, "llm", return_value=llm):
        assert mod.classify_yes_no("maybe", "ok?") == "IRRELEVANT"


def test_reask_yes_no_fallback():
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("offline")
    with patch.object(mod, "llm", return_value=llm):
        text = mod.reask_yes_no("Are you ready?", "asdf")
    assert "Are you ready?" in text
