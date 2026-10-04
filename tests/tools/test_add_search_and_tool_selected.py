"""Unit tests for tools/add_search_result.py and tools/add_tool_selected.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import importlib
from unittest.mock import MagicMock, patch

search_mod = importlib.import_module("tools.add_search_result")
tool_mod = importlib.import_module("tools.add_tool_selected")




def _cursor_ctx(cur: MagicMock):
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False
    return ctx


def test_add_search_result_requires_fields():
    assert json.loads(search_mod.add_search_result(1, 1, "", "x"))["success"] is False
    assert json.loads(search_mod.add_search_result(1, 1, "q", ""))["success"] is False


def test_add_search_result_component_missing():
    cur = MagicMock()
    cur.fetchone.return_value = None
    with patch.object(search_mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(
            search_mod.add_search_result(1, 1, "q", "answer")
        )
    assert result["success"] is False


def test_add_search_result_success():
    cur = MagicMock()
    cur.fetchone.side_effect = [
        {"ComponentId": 1},
        {
            "SearchId": 5,
            "ComponentId": 1,
            "UserId": 2,
            "SearchQuestion": "q",
            "SearchResult": "a",
            "TimeStamp": datetime(2026, 7, 13, tzinfo=timezone.utc),
        },
    ]
    with patch.object(search_mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(search_mod.add_search_result(1, 2, "q", "a"))
    assert result["success"] is True
    assert result["SearchId"] == "5"


def test_add_tool_selected_requires_fields():
    assert json.loads(tool_mod.add_tool_selected(1, 1, "", "u"))["success"] is False
    assert json.loads(tool_mod.add_tool_selected(1, 1, "wrench", ""))["success"] is False


def test_add_tool_selected_success():
    cur = MagicMock()
    cur.fetchone.side_effect = [
        {"ComponentId": 1},
        {
            "ToolSelectedId": 9,
            "ComponentId": 1,
            "UserId": 2,
            "ToolKind": "wrench",
            "Url": "https://x",
        },
    ]
    with patch.object(tool_mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(
            tool_mod.add_tool_selected(1, 2, "wrench", "https://x")
        )
    assert result["success"] is True
    assert result["ToolSelectedId"] == "9"
