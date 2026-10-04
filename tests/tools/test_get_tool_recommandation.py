"""Unit tests for tools/get_tool_recommandation.py."""

from __future__ import annotations

import json
import importlib
from unittest.mock import MagicMock, patch

mod = importlib.import_module("tools.get_tool_recommandation")




def _cursor_ctx(cur: MagicMock):
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False
    return ctx


def test_requires_tool_kind():
    result = json.loads(mod.get_tool_recommandation(""))
    assert result["success"] is False


def test_exact_match():
    cur = MagicMock()
    cur.fetchone.return_value = {
        "ToolKind": "screwdriver",
        "Url": "https://tools.example.com/screwdriver",
    }
    with patch.object(mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(mod.get_tool_recommandation("Screwdriver"))
    assert result["success"] is True
    assert result["ToolKind"] == "screwdriver"


def test_ambiguous_fuzzy_match():
    cur = MagicMock()
    cur.fetchone.return_value = None
    cur.fetchall.return_value = [
        {"ToolKind": "pipe wrench", "Url": "u1"},
        {"ToolKind": "adjustable wrench", "Url": "u2"},
    ]
    with patch.object(mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(mod.get_tool_recommandation("wrench"))
    assert result["success"] is False
    assert "Ambiguous" in result["error"]


def test_unique_fuzzy_match():
    cur = MagicMock()
    cur.fetchone.return_value = None
    cur.fetchall.return_value = [
        {"ToolKind": "wire stripper", "Url": "https://tools.example.com/wire-stripper"},
    ]
    with patch.object(mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(mod.get_tool_recommandation("stripper"))
    assert result["success"] is True
    assert result["ToolKind"] == "wire stripper"


def test_pick_unique_fuzzy_whole_word():
    candidates = [
        {"ToolKind": "pipe wrench", "Url": "a"},
        {"ToolKind": "screwdriver", "Url": "b"},
    ]
    chosen = mod._pick_unique_fuzzy_match("wrench", candidates)
    assert chosen is not None
    assert chosen["ToolKind"] == "pipe wrench"
