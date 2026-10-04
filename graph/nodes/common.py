"""Shared helpers and constants for graph nodes."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from langchain_openai import ChatOpenAI

import tools as db_tools
from graph.state import ChatState


def llm() -> ChatOpenAI:
    return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)


def parse_json_blob(text: str) -> dict[str, Any] | list[Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
        return None


def classify_yes_no(user_message: str, question: str) -> str:
    """Interpret a user reply as YES, NO, or IRRELEVANT using the LLM."""
    prompt = (
        "You classify a user's reply to a yes/no question.\n"
        "Return ONLY one token: YES, NO, or IRRELEVANT.\n\n"
        "Rules:\n"
        "- YES if the user clearly agrees, affirms, accepts, or confirms "
        "(including casual phrases like 'sure', 'sounds good', 'yep', 'please do').\n"
        "- NO if the user clearly declines, refuses, or disagrees "
        "(including 'nah', 'not really', 'I'd rather not').\n"
        "- IRRELEVANT if the reply does not clearly answer the question, "
        "changes the subject, asks something else, or is too ambiguous.\n\n"
        f"Question: {question}\n"
        f"User reply: {user_message}\n"
        "Classification:"
    )
    try:
        response = llm().invoke(prompt)
        content = (response.content if hasattr(response, "content") else str(response)).strip().upper()
        # Prefer the first token / first matching label
        for label in ("IRRELEVANT", "YES", "NO"):
            if re.search(rf"\b{label}\b", content):
                return label
        first = content.split()[0] if content.split() else ""
        if first in {"YES", "NO", "IRRELEVANT"}:
            return first
    except Exception:
        pass
    return "IRRELEVANT"


def reask_yes_no(question: str, user_message: str = "") -> str:
    """Politely rephrase a yes/no question when the reply was irrelevant."""
    prompt = (
        "The user gave an unclear answer to a yes/no question. "
        "Write a short, polite message that:\n"
        "1) Briefly acknowledges you did not understand their answer as yes or no\n"
        "2) Rephrases the original question clearly\n"
        "3) Invites them to answer in their own words (agreement or decline is fine)\n"
        "Do not mention being an AI. Keep it to 2-4 sentences.\n\n"
        f"Original question: {question}\n"
        f"User reply: {user_message or '(empty)'}\n"
    )
    try:
        response = llm().invoke(prompt)
        text = (response.content if hasattr(response, "content") else str(response)).strip()
        if text:
            return text
    except Exception:
        pass
    return (
        "Sorry, I wasn't sure how to take that. "
        f"{question} Feel free to answer in your own words."
    )


Q_USE_LATEST = "Would you like to continue with your latest home component?"
Q_REUSE_TYPE = "Is this the existing component you want to work on now?"
Q_SATISFIED = (
    "Were the home repair tool(s) you chose useful, and were you able to fix the issue?"
)
Q_ANOTHER_JOB = "Would you like to work on another repair question?"
Q_LAST_RESOLUTION = (
    "Are you satisfied with that last resolution, or is there more we still need to do?"
)


def load_user(email: str) -> dict[str, Any]:
    return json.loads(db_tools.get_userinfo_from_email(email))


def latest_component(user_info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user_info:
        return None
    components = user_info.get("Components") or []
    return components[0] if components else None


def set_active_from_component(state: ChatState, component: dict[str, Any]) -> dict[str, Any]:
    problem = (component.get("ProblemDesc") or "").strip()
    return {
        "active_component_id": str(component["ComponentId"]),
        "active_component": component,
        "hasActiveComponent": True,
        "hasActiveProblem": bool(problem),
    }


def ask_for_component() -> str:
    """Start of the multi-step component intake (type first)."""
    return ask_for_component_type()


def ask_for_component_type() -> str:
    types = _known_component_types()
    type_line = ", ".join(types) if types else "(none yet — any home component type is ok)"
    return (
        "What type of home component are you working on?\n"
        f"Known types: {type_line}\n"
        "You can also enter a new type (e.g. DISHWASHER or \"water heaters\")."
    )


def ask_for_manufacturer() -> str:
    return (
        "What is the manufacturer for the component?\n"
        "Enter the brand name (even if uncommon). "
        "Only say you don't know / not sure / unknown / no brand if you truly do not have one."
    )


def ask_for_problem() -> str:
    return "What is the problem you are facing?"


def _known_component_types() -> list[str]:
    try:
        data = json.loads(db_tools.get_component_types())
        if data.get("success"):
            return list(data.get("names") or [])
    except Exception:
        pass
    return []


def ask_use_latest(latest: dict[str, Any]) -> str:
    return (
        "I found a recent component on your account:\n"
        f"  Type: {latest.get('Type')}\n"
        f"  Manufacturer: {latest.get('ManufacturerId') or 'N/A'}\n"
        f"  Problem: {latest.get('ProblemDesc') or 'N/A'}\n"
        f"  Resolved: {latest.get('Resolved')}\n"
        f"  Time: {latest.get('TimeStamp')}\n\n"
        "Would you like to continue with this latest component?"
    )


