"""LangGraph state for the Home Repair Chatbot."""

from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    last_user_message: str
    assistant_reply: str
    awaiting: Optional[str]
    email: Optional[str]
    user_id: Optional[str]
    user_info: Optional[dict[str, Any]]
    hasActiveComponent: bool
    hasActiveProblem: bool
    active_component_id: Optional[str]
    active_component: Optional[dict[str, Any]]
    latest_search_question: Optional[str]
    latest_search_result: Optional[str]
    tool_recommendations: list[dict[str, str]]
    tools_selected: list[dict[str, str]]
    tools_presented: bool
    initializer_complete: bool
    from_check_result: bool
    pending_component: Optional[dict[str, Any]]
    candidate_component: Optional[dict[str, Any]]
    pending_new_user: Optional[dict[str, Any]]
    pending_problem_desc: Optional[str]
    done: bool
