"""Unit tests for initializer satisfaction classification."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

mod = importlib.import_module("graph.nodes.initializer")


def test_heuristic_satisfied_phrases():
    assert mod._heuristic_resolution_satisfaction("Yes I am satisfy with the resolution") == "YES"
    assert mod._heuristic_resolution_satisfaction("That issue is resolved") == "YES"
    assert mod._heuristic_resolution_satisfaction("I'm happy with it") == "YES"
    assert mod._heuristic_resolution_satisfaction("all good") == "YES"


def test_heuristic_still_needs_help():
    assert mod._heuristic_resolution_satisfaction("still leaking") == "NO"
    assert mod._heuristic_resolution_satisfaction("not satisfied yet") == "NO"
    assert mod._heuristic_resolution_satisfaction("I need more help") == "NO"


def test_classify_uses_heuristic_before_llm():
    llm = MagicMock()
    llm.invoke.side_effect = AssertionError("LLM should not be called")
    with patch.object(mod, "llm", return_value=llm):
        assert (
            mod._classify_resolution_satisfaction(
                "Yes I am satisfy with the resolution",
                {"ResolutionDetail": "still unresolved"},
            )
            == "YES"
        )


def test_yes_path_starts_new_component_and_marks_resolved():
    state = {
        "email": "a@b.com",
        "user_info": {
            "UserId": "2",
            "Components": [
                {
                    "ComponentId": "11",
                    "Type": "DISHWASHER",
                    "ProblemDesc": "red light",
                    "ResolutionDetail": "unresolved note",
                    "Resolved": False,
                }
            ],
        },
        "awaiting": "last_resolution_ok",
        "last_user_message": "Yes I am satisfy with the resolution",
    }
    with patch.object(mod.db_tools, "update_home_component", return_value='{"success": true}') as upd, patch.object(
        mod, "load_user", return_value={"UserId": "2", "Components": []}
    ):
        out = mod._handle_last_resolution_reply(
            state, "Yes I am satisfy with the resolution"
        )
    assert out["awaiting"] == "component_type"
    assert out["active_component_id"] is None
    assert out["hasActiveComponent"] is False
    assert "new repair" in out["assistant_reply"].lower()
    assert upd.called
