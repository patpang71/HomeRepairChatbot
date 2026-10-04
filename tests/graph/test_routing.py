"""Unit tests for graph routing helpers."""

from __future__ import annotations

from graph import after_check, after_tavily, route_entry


def test_route_done_ends():
    assert route_entry({"done": True}) == "__end__"


def test_route_missing_user_to_initializer():
    assert route_entry({}) == "initializer"


def test_route_last_resolution_ok_to_initializer():
    assert (
        route_entry({"user_id": "1", "awaiting": "last_resolution_ok"})
        == "initializer"
    )


def test_route_preference_to_initializer():
    assert route_entry({"user_id": "1", "awaiting": "preference"}) == "initializer"


def test_route_satisfaction_to_check_result():
    assert route_entry({"user_id": "1", "awaiting": "satisfaction"}) == "check_result"


def test_route_tool_selection():
    assert (
        route_entry({"user_id": "1", "awaiting": "tool_selection"})
        == "tool_recommendation"
    )


def test_route_tavily_awaiting():
    assert (
        route_entry({"user_id": "1", "awaiting": "component_type"}) == "tavily_search"
    )


def test_route_search_ready_to_tools():
    assert (
        route_entry(
            {
                "user_id": "1",
                "awaiting": None,
                "latest_search_result": "use a wrench",
                "tools_presented": False,
            }
        )
        == "tool_recommendation"
    )


def test_route_initializer_complete_to_tavily():
    assert (
        route_entry(
            {
                "user_id": "1",
                "awaiting": None,
                "initializer_complete": True,
            }
        )
        == "tavily_search"
    )


def test_after_tavily_pauses_while_awaiting():
    assert after_tavily({"awaiting": "component_manufacturer"}) == "__end__"


def test_after_tavily_continues_to_tools():
    assert (
        after_tavily(
            {
                "awaiting": None,
                "latest_search_result": "answer",
                "tools_presented": False,
            }
        )
        == "tool_recommendation"
    )


def test_after_check_chains_to_tavily_on_pending_problem():
    assert (
        after_check(
            {"awaiting": "problem_desc", "pending_problem_desc": "still leaking"}
        )
        == "tavily_search"
    )


def test_after_check_ends_otherwise():
    assert after_check({"awaiting": "another_job"}) == "__end__"
