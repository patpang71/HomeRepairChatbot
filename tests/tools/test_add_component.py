"""Unit tests for tools/add_component.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import importlib
from unittest.mock import MagicMock, patch

mod = importlib.import_module("tools.add_component")




def _cursor_ctx(cur: MagicMock):
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False
    return ctx


def test_unknown_type_rejected():
    with patch.object(mod, "component_type_exists", return_value=False), patch.object(
        mod, "list_component_type_names", return_value=["SINK"]
    ):
        result = json.loads(mod.add_component(UserId=1, Type="NOPE"))
    assert result["success"] is False
    assert "Unknown Type" in result["error"]


def test_user_not_found():
    cur = MagicMock()
    cur.fetchone.return_value = None
    with patch.object(mod, "component_type_exists", return_value=True), patch.object(
        mod, "get_cursor", return_value=_cursor_ctx(cur)
    ):
        result = json.loads(mod.add_component(UserId=99, Type="SINK"))
    assert result["success"] is False
    assert "not found" in result["error"]


def test_add_component_success():
    cur = MagicMock()
    cur.fetchone.side_effect = [
        {"UserId": 1},
        {
            "ComponentId": 11,
            "UserId": 1,
            "Type": "SINK",
            "ManufacturerId": "Kohler",
            "ProblemDesc": "Leak",
            "ResolutionDetail": None,
            "Resolved": False,
            "TimeStamp": datetime(2026, 7, 13, tzinfo=timezone.utc),
        },
    ]
    with patch.object(mod, "component_type_exists", return_value=True), patch.object(
        mod, "get_cursor", return_value=_cursor_ctx(cur)
    ):
        result = json.loads(
            mod.add_component(
                UserId=1,
                Type="SINK",
                ManufacturerId="Kohler",
                ProblemDesc="Leak",
            )
        )
    assert result["success"] is True
    assert result["ComponentId"] == "11"
    assert result["Type"] == "SINK"
