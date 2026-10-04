"""Unit tests for tools/add_user.py."""

from __future__ import annotations

import json
import importlib
from unittest.mock import MagicMock, patch

add_user_mod = importlib.import_module("tools.add_user")




def _cursor_ctx(cur: MagicMock):
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False
    return ctx


def test_add_user_requires_email():
    result = json.loads(add_user_mod.add_user(Email="", Zip="94587"))
    assert result["success"] is False
    assert "Email" in result["error"]


def test_add_user_requires_zip():
    result = json.loads(add_user_mod.add_user(Email="a@b.com", Zip=""))
    assert result["success"] is False
    assert "Zip" in result["error"]


def test_add_user_existing():
    cur = MagicMock()
    cur.fetchone.return_value = {"UserId": 7, "Email": "a@b.com"}
    with patch.object(add_user_mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(add_user_mod.add_user(Email="a@b.com", Zip="94587"))
    assert result["success"] is True
    assert result["created"] is False
    assert result["UserId"] == "7"


def test_add_user_creates():
    cur = MagicMock()
    cur.fetchone.side_effect = [
        None,
        {
            "UserId": 3,
            "Email": "new@b.com",
            "StreetAddress": "1 Main",
            "City": "Union City",
            "State": "CA",
            "Zip": "94587",
            "Preference": "detail",
        },
    ]
    with patch.object(add_user_mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(
            add_user_mod.add_user(
                Email="new@b.com",
                Zip="94587",
                StreetAddress="1 Main",
                City="Union City",
                State="CA",
                Preference="detail",
            )
        )
    assert result["success"] is True
    assert result["created"] is True
    assert result["UserId"] == "3"
    assert result["Preference"] == "detail"


def test_add_user_rejects_bad_preference():
    result = json.loads(
        add_user_mod.add_user(Email="a@b.com", Zip="94587", Preference="loud")
    )
    assert result["success"] is False
    assert "Preference" in result["error"]


def test_add_user_defaults_preference_to_concise():
    cur = MagicMock()
    cur.fetchone.side_effect = [
        None,
        {
            "UserId": 4,
            "Email": "c@b.com",
            "StreetAddress": None,
            "City": None,
            "State": None,
            "Zip": "94587",
            "Preference": "concise",
        },
    ]
    with patch.object(add_user_mod, "get_cursor", return_value=_cursor_ctx(cur)):
        result = json.loads(add_user_mod.add_user(Email="c@b.com", Zip="94587"))
    assert result["success"] is True
    assert result["Preference"] == "concise"
    # INSERT args include preference
    insert_args = cur.execute.call_args_list[-1][0][1]
    assert insert_args[-1] == "concise"
