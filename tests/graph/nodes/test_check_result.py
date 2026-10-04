"""Unit tests for graph/nodes/check_result helpers and guards."""

from __future__ import annotations

import json
import importlib
from unittest.mock import MagicMock, patch

mod = importlib.import_module("graph.nodes.check_result")




def test_build_resolution_summary_fallback_with_selected_tools():
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("offline")
    state = {
        "tools_selected": [{"ToolKind": "wrench"}],
        "tool_recommendations": [{"ToolKind": "pliers"}],
        "active_component": {"ProblemDesc": "drip"},
    }
    with patch.object(mod, "llm", return_value=llm):
        text = mod._build_resolution_summary(
            state, fixed=True, user_reply="yes", extra_detail=None
        )
    assert "selected tools" in text.lower() or "Used selected tools" in text
    assert "resolved" in text


def test_build_resolution_summary_fallback_suggested_only():
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("offline")
    state = {
        "tools_selected": [],
        "tool_recommendations": [{"ToolKind": "pliers"}],
        "active_component": {"ProblemDesc": "drip"},
    }
    with patch.object(mod, "llm", return_value=llm):
        text = mod._build_resolution_summary(
            state, fixed=False, user_reply="no", extra_detail=None
        )
    assert "Suggested tools" in text
    assert "none selected" in text


def test_check_result_missing_ids_guard():
    state = {
        "awaiting": "satisfaction",
        "last_user_message": "yes",
        "active_component_id": None,
        "user_id": "1",
    }
    with patch.object(
        mod, "_parse_satisfaction_reply", return_value={"decision": "YES", "detail": None}
    ):
        out = mod.check_result(state)
    assert out["awaiting"] == "satisfaction"
    assert "lost track of the active component" in out["assistant_reply"]


def test_check_result_yes_marks_resolved():
    state = {
        "awaiting": "satisfaction",
        "last_user_message": "yes",
        "active_component_id": "10",
        "user_id": "1",
        "tools_selected": [{"ToolKind": "wrench"}],
        "tool_recommendations": [],
        "active_component": {"ProblemDesc": "leak"},
    }

    def fake_update(**kwargs):
        return json.dumps({"success": True})

    with patch.object(
        mod, "_parse_satisfaction_reply", return_value={"decision": "YES", "detail": None}
    ), patch.object(
        mod, "_build_resolution_summary", return_value="Fixed with wrench."
    ), patch.object(mod.db_tools, "update_home_component", side_effect=fake_update), patch.object(
        mod, "load_user", return_value={"found": True, "Components": []}
    ):
        out = mod.check_result(state)
    assert out["awaiting"] == "another_job"
    assert "resolved" in out["assistant_reply"].lower()


def test_check_result_no_with_detail_chains_search():
    state = {
        "awaiting": "satisfaction",
        "last_user_message": "no still leaking under the sink",
        "active_component_id": "10",
        "user_id": "1",
        "tools_selected": [],
        "tool_recommendations": [{"ToolKind": "wrench"}],
        "active_component": {"ProblemDesc": "leak"},
    }

    with patch.object(
        mod,
        "_parse_satisfaction_reply",
        return_value={"decision": "NO", "detail": "still leaking under the sink"},
    ), patch.object(
        mod, "_build_resolution_summary", return_value="Still unresolved."
    ), patch.object(
        mod.db_tools,
        "update_home_component",
        return_value=json.dumps({"success": True}),
    ):
        out = mod.check_result(state)
    assert out.get("pending_problem_desc") == "still leaking under the sink"
    assert out.get("awaiting") == "problem_desc"
