"""Unit tests for tools/get_userinfo_from_email.py and get_component_types.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import importlib
from unittest.mock import MagicMock, patch

types_mod = importlib.import_module("tools.get_component_types")
info_mod = importlib.import_module("tools.get_userinfo_from_email")




def _cursor_ctx(cur: MagicMock):
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False
    return ctx


def test_get_component_types():
    with patch.object(types_mod, "list_component_type_names", return_value=["SINK", "TOILET"]):
        result = json.loads(types_mod.get_component_types())
    assert result["success"] is True
    assert result["names"] == ["SINK", "TOILET"]
    assert result["ComponentTypes"][0]["ComponentTypeName"] == "SINK"


def test_get_userinfo_requires_email():
    result = json.loads(info_mod.get_userinfo_from_email(""))
    assert result["success"] is False


def test_get_userinfo_not_found():
    cur = MagicMock()
    cur.fetchone.return_value = None
    with patch.object(info_mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(info_mod.get_userinfo_from_email("missing@x.com"))
    assert result["found"] is False


def test_get_userinfo_includes_nested_lists():
    cur = MagicMock()
    cur.fetchone.return_value = {
        "UserId": 1,
        "Email": "a@b.com",
        "StreetAddress": "1 A",
        "City": "X",
        "State": "CA",
        "Zip": "94587",
        "Preference": "detail",
    }
    cur.fetchall.side_effect = [
        [
            {
                "ComponentId": 10,
                "Type": "SINK",
                "ManufacturerId": "Kohler",
                "ProblemDesc": "drip",
                "ResolutionDetail": "fixed",
                "Resolved": True,
                "TimeStamp": datetime(2026, 7, 13, tzinfo=timezone.utc),
            }
        ],
        [
            {
                "SearchId": 100,
                "SearchQuestion": "q",
                "SearchResult": "a",
                "TimeStamp": datetime(2026, 7, 13, tzinfo=timezone.utc),
            }
        ],
        [
            {
                "ToolSelectedId": 200,
                "ToolKind": "wrench",
                "Url": "https://x",
            }
        ],
    ]
    with patch.object(info_mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(info_mod.get_userinfo_from_email("a@b.com"))
    assert result["found"] is True
    assert result["Preference"] == "detail"
    assert result["Components"][0]["ComponentId"] == "10"
    assert result["Components"][0]["Searchs"][0]["SearchId"] == "100"
    assert result["Components"][0]["ToolSelected"][0]["ToolKind"] == "wrench"
