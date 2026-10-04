"""Unit tests for tools/common.py helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tools.common import fmt_ts, utc_now


def test_fmt_ts_none():
    assert fmt_ts(None) is None


def test_fmt_ts_datetime_utc():
    dt = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    assert fmt_ts(dt) == "2026-07-13 12:00:00 UTC"


def test_fmt_ts_string_passthrough():
    assert fmt_ts("already-a-string") == "already-a-string"


def test_normalize_user_preference():
    from tools.common import normalize_user_preference

    assert normalize_user_preference(None) == "concise"
    assert normalize_user_preference("") == "concise"
    assert normalize_user_preference("detail") == "detail"
    assert normalize_user_preference("Detailed") == "detail"
    assert normalize_user_preference("brief") == "concise"
    assert normalize_user_preference("nope") is None


def test_utc_now_is_timezone_aware():
    now = utc_now()
    assert now.tzinfo is not None


def test_list_component_type_names():
    from tools import common as common_mod

    cur = MagicMock()
    cur.fetchall.return_value = [
        {"ComponentTypeName": "SINK"},
        {"ComponentTypeName": "TOILET"},
    ]
    ctx = MagicMock()
    ctx.__enter__.return_value = cur
    ctx.__exit__.return_value = False

    with patch.object(common_mod, "get_cursor", return_value=ctx):
        assert common_mod.list_component_type_names() == ["SINK", "TOILET"]
