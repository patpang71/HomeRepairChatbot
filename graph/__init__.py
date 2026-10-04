"""LangGraph wiring for Home Repair Chatbot."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from graph.nodes import check_result, initializer, tavily_search, tool_recommendation
from graph.state import ChatState

INIT_AWAITING = {"email", "new_user_details", "preference", "last_resolution_ok"}
TAVILY_AWAITING = {
    "component_type",
    "component_manufacturer",
    "component_problem",
    "reuse_type_component",
    "use_latest_component",
    "problem_desc",
}
TOOL_AWAITING = {"tool_selection"}
CHECK_AWAITING = {"satisfaction", "another_job"}


def route_entry(state: ChatState) -> Literal["initializer", "tavily_search", "tool_recommendation", "check_result", "__end__"]:
    if state.get("done"):
        return "__end__"

    awaiting = state.get("awaiting")
    initializer_complete = bool(state.get("initializer_complete"))

    # After the first Initializer pass, skip returning there (e.g. from CheckResult loops)
    if not state.get("user_id"):
        return "initializer"

    # Always handle initializer awaits here (including last_resolution_ok)
    if awaiting in INIT_AWAITING:
        return "initializer"

    if awaiting in CHECK_AWAITING:
        return "check_result"

    if awaiting in TOOL_AWAITING:
        return "tool_recommendation"

    if awaiting in TAVILY_AWAITING:
        return "tavily_search"

    # Search just finished this turn (awaiting cleared, result present)
    if state.get("latest_search_result") and awaiting is None and not state.get("tools_presented"):
        return "tool_recommendation"

    if initializer_complete:
        return "tavily_search"

    if not state.get("hasActiveComponent"):
        return "tavily_search"

    return "tavily_search"


def after_initializer(state: ChatState) -> Literal["__end__"]:
    # Pause after init prompts so the next user reply is handled by tavily_search.
    return "__end__"


def after_tavily(state: ChatState) -> Literal["tool_recommendation", "__end__"]:
    if state.get("awaiting") in TAVILY_AWAITING:
        return "__end__"
    if state.get("latest_search_result") and not state.get("tools_presented"):
        return "tool_recommendation"
    return "__end__"


def after_tools(state: ChatState) -> Literal["__end__"]:
    return "__end__"


def after_check(state: ChatState) -> Literal["tavily_search", "__end__"]:
    # If CheckResult already captured a follow-up problem, continue into TavilySearch now.
    if state.get("awaiting") == "problem_desc" and state.get("pending_problem_desc"):
        return "tavily_search"
    return "__end__"


def build_graph():
    graph = StateGraph(ChatState)
    graph.add_node("initializer", initializer)
    graph.add_node("tavily_search", tavily_search)
    graph.add_node("tool_recommendation", tool_recommendation)
    graph.add_node("check_result", check_result)

    graph.add_conditional_edges(
        START,
        route_entry,
        {
            "initializer": "initializer",
            "tavily_search": "tavily_search",
            "tool_recommendation": "tool_recommendation",
            "check_result": "check_result",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "initializer",
        after_initializer,
        {END: END},
    )
    graph.add_conditional_edges(
        "tavily_search",
        after_tavily,
        {"tool_recommendation": "tool_recommendation", END: END},
    )
    graph.add_conditional_edges(
        "tool_recommendation",
        after_tools,
        {END: END},
    )
    graph.add_conditional_edges(
        "check_result",
        after_check,
        {"tavily_search": "tavily_search", END: END},
    )
    return graph.compile()
