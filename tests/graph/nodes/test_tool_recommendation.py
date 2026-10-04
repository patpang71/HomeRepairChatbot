"""Unit tests for graph/nodes/tool_recommendation helpers and selection flow."""

from __future__ import annotations

import json
import importlib
from unittest.mock import MagicMock, patch

mod = importlib.import_module("graph.nodes.tool_recommendation")




def test_extract_tools_fallback_keyword_scan():
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("offline")
    text = "Use a pipe wrench and Teflon tape on the faucet valve."
    with patch.object(mod, "llm", return_value=llm):
        found = mod._extract_tools_from_search(text)
    assert "pipe wrench" in found
    assert "Teflon tape" in found
    assert "faucet" in found


def test_extract_tools_from_llm_json():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content='["wrench", "wrench", "pliers"]')
    with patch.object(mod, "llm", return_value=llm):
        found = mod._extract_tools_from_search("ignored when llm works")
    assert found == ["wrench", "pliers"]


def test_parse_tool_selection_none():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(
        content='{"decision":"NONE","tools":[]}'
    )
    catalog = [{"ToolKind": "wrench", "Url": "https://x"}]
    with patch.object(mod, "llm", return_value=llm):
        assert mod._parse_tool_selection("skip", catalog) == []


def test_parse_tool_selection_select():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(
        content='{"decision":"SELECT","tools":["Wrench"]}'
    )
    catalog = [
        {"ToolKind": "wrench", "Url": "https://x"},
        {"ToolKind": "pliers", "Url": "https://y"},
    ]
    with patch.object(mod, "llm", return_value=llm):
        selected = mod._parse_tool_selection("the wrench", catalog)
    assert selected == [{"ToolKind": "wrench", "Url": "https://x"}]


def test_tool_recommendation_empty_selection():
    state = {
        "awaiting": "tool_selection",
        "last_user_message": "none",
        "active_component_id": "1",
        "user_id": "2",
        "tool_recommendations": [{"ToolKind": "wrench", "Url": "https://x"}],
    }
    with patch.object(mod, "_parse_tool_selection", return_value=[]):
        out = mod.tool_recommendation(state)
    assert out["awaiting"] == "satisfaction"
    assert out["tools_selected"] == []


def test_tool_recommendation_missing_ids():
    state = {
        "awaiting": "tool_selection",
        "last_user_message": "wrench",
        "active_component_id": None,
        "user_id": "2",
        "tool_recommendations": [{"ToolKind": "wrench", "Url": "https://x"}],
    }
    with patch.object(
        mod,
        "_parse_tool_selection",
        return_value=[{"ToolKind": "wrench", "Url": "https://x"}],
    ):
        out = mod.tool_recommendation(state)
    assert out["awaiting"] == "satisfaction"
    assert "lost the active component" in out["assistant_reply"]


def test_tool_recommendation_saves_tools():
    state = {
        "awaiting": "tool_selection",
        "last_user_message": "wrench",
        "active_component_id": "1",
        "user_id": "2",
        "tool_recommendations": [{"ToolKind": "wrench", "Url": "https://x"}],
    }
    with patch.object(
        mod,
        "_parse_tool_selection",
        return_value=[{"ToolKind": "wrench", "Url": "https://x"}],
    ), patch.object(
        mod.db_tools,
        "add_tool_selected",
        return_value=json.dumps({"success": True}),
    ):
        out = mod.tool_recommendation(state)
    assert out["awaiting"] == "satisfaction"
    assert out["tools_selected"] == [{"ToolKind": "wrench", "Url": "https://x"}]
    assert "saved these tools" in out["assistant_reply"]
