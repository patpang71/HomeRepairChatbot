"""Unit tests for tools/update_home_component.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import importlib
from unittest.mock import MagicMock, patch

mod = importlib.import_module("tools.update_home_component")




def _cursor_ctx(cur: MagicMock):
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False
    return ctx


def test_invalid_field():
    result = json.loads(mod.update_home_component(1, 1, "Nope", "x"))
    assert result["success"] is False


def test_unknown_type():
    with patch.object(mod, "component_type_exists", return_value=False), patch.object(
        mod, "list_component_type_names", return_value=["SINK"]
    ):
        result = json.loads(mod.update_home_component(1, 1, "Type", "NOPE"))
    assert result["success"] is False


def test_component_not_found():
    cur = MagicMock()
    cur.fetchone.return_value = None
    with patch.object(mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(
            mod.update_home_component(1, 1, "ProblemDesc", "new problem")
        )
    assert result["success"] is False
    assert "not found" in result["error"]


def test_update_resolved_parses_string():
    cur = MagicMock()
    cur.fetchone.side_effect = [
        {"ComponentId": 1},
        {
            "ComponentId": 1,
            "UserId": 1,
            "Type": "SINK",
            "ManufacturerId": None,
            "ProblemDesc": "x",
            "ResolutionDetail": None,
            "Resolved": True,
            "TimeStamp": datetime(2026, 7, 13, tzinfo=timezone.utc),
        },
    ]
    with patch.object(mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(mod.update_home_component(1, 1, "Resolved", "yes"))
    assert result["success"] is True
    assert result["Resolved"] is True
