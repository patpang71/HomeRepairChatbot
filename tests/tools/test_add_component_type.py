"""Unit tests for tools/add_component_type.py."""

from __future__ import annotations

import json
import importlib
from unittest.mock import MagicMock, patch

mod = importlib.import_module("tools.add_component_type")




def _cursor_ctx(cur: MagicMock):
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False
    return ctx


def test_rejects_invalid_name():
    result = json.loads(mod.add_component_type("!!!"))
    assert result["success"] is False


def test_normalizes_and_creates():
    cur = MagicMock()
    cur.fetchone.side_effect = [
        None,
        {"ComponentTypeId": 9, "ComponentTypeName": "WATER_HEATER"},
    ]
    with patch.object(mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(mod.add_component_type("water heater"))
    assert result["success"] is True
    assert result["created"] is True
    assert result["ComponentTypeName"] == "WATER_HEATER"


def test_existing_type_is_idempotent():
    cur = MagicMock()
    cur.fetchone.return_value = {
        "ComponentTypeId": 1,
        "ComponentTypeName": "TOILET",
    }
    with patch.object(mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(mod.add_component_type("TOILET"))
    assert result["success"] is True
    assert result["created"] is False
