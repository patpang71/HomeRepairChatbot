"""CheckResult node."""

from __future__ import annotations

import json
from typing import Any

import tools as db_tools
from graph.nodes.common import (
    Q_ANOTHER_JOB,
    Q_SATISFIED,
    ask_for_component,
    classify_yes_no,
    llm,
    load_user,
    parse_json_blob,
    reask_yes_no,
)
from graph.state import ChatState


def check_result(state: ChatState) -> dict[str, Any]:
    awaiting = state.get("awaiting")
    user_msg = (state.get("last_user_message") or "").strip()

    if awaiting == "another_job":
        decision = classify_yes_no(user_msg, Q_ANOTHER_JOB)
        if decision == "YES":
            user_info = load_user(state.get("email") or "")
            return {
                "user_info": user_info,
                "hasActiveComponent": False,
                "hasActiveProblem": False,
                "active_component_id": None,
                "active_component": None,
                "awaiting": "component_type",
                "assistant_reply": (
                    "Let's start a new repair item.\n"
                    f"{ask_for_component()}"
                ),
                "latest_search_result": None,
                "tool_recommendations": [],
                "tools_presented": False,
                "tools_selected": [],
                "pending_problem_desc": None,
                "initializer_complete": True,
                "from_check_result": True,
            }
        if decision == "NO":
            return {
                "done": True,
                "awaiting": None,
                "assistant_reply": "Thanks for using the Home Repair Chatbot. Goodbye!",
            }
        return {
            "awaiting": "another_job",
            "assistant_reply": reask_yes_no(Q_ANOTHER_JOB, user_msg),
        }

    if awaiting != "satisfaction":
        return {
            "awaiting": "satisfaction",
            "assistant_reply": Q_SATISFIED,
        }

    parsed = _parse_satisfaction_reply(user_msg)
    decision = parsed["decision"]
    detail = (parsed.get("detail") or "").strip() or None

    if decision == "IRRELEVANT":
        return {
            "awaiting": "satisfaction",
            "assistant_reply": reask_yes_no(Q_SATISFIED, user_msg),
        }

    component_id = state.get("active_component_id")
    user_id = state.get("user_id")
    fixed = decision == "YES"

    if not component_id or not user_id:
        return {
            "awaiting": "satisfaction",
            "assistant_reply": (
                "I lost track of the active component, so I could not save the "
                "resolution note. Please restart this repair flow or enter your "
                "email again.\n"
                f"{Q_SATISFIED}"
            ),
        }

    summary = _build_resolution_summary(
        state,
        fixed=fixed,
        user_reply=user_msg,
        extra_detail=detail if fixed else None,
    )
    detail_update = json.loads(
        db_tools.update_home_component(
            ComponentId=component_id,
            UserId=user_id,
            field="ResolutionDetail",
            value=summary,
        )
    )
    detail_saved = bool(detail_update.get("success"))
    detail_error = detail_update.get("error") if not detail_saved else None

    if fixed:
        updated = json.loads(
            db_tools.update_home_component(
                ComponentId=component_id,
                UserId=user_id,
                field="Resolved",
                value=True,
            )
        )
        msg = (
            "Great! Glad the tools helped and the issue is fixed. "
            "I marked this component as resolved."
        )
        if not updated.get("success"):
            msg = f"Tried to mark resolved, but got: {updated.get('error')}"
        if detail_saved:
            if detail:
                msg += "\nI also noted your extra detail in the resolution summary."
            msg += f"\nResolution summary: {summary}"
        else:
            msg += (
                "\nI could not save the ResolutionDetail note"
                + (f": {detail_error}" if detail_error else ".")
            )
        msg += f"\n{Q_ANOTHER_JOB}"
        return {
            "hasActiveProblem": False,
            "awaiting": "another_job",
            "assistant_reply": msg,
            "user_info": load_user(state.get("email") or ""),
            "pending_problem_desc": None,
            "initializer_complete": True,
            "from_check_result": True,
        }

    # Not fixed — back to TavilySearch (skip Initializer)
    if detail_saved:
        note_line = (
            "Sorry that did not fully fix it. I saved a short note on what we tried:\n"
            f"{summary}"
        )
    else:
        note_line = (
            "Sorry that did not fully fix it. I could not save the ResolutionDetail note"
            + (f": {detail_error}" if detail_error else ".")
        )

    if detail:
        return {
            "hasActiveProblem": False,
            "awaiting": "problem_desc",
            "pending_problem_desc": detail,
            "assistant_reply": (
                f"{note_line}\n\n"
                f"I'll search again using your follow-up: {detail}"
            ),
            "latest_search_result": None,
            "tool_recommendations": [],
            "tools_presented": False,
            "tools_selected": [],
            "initializer_complete": True,
            "from_check_result": True,
        }

    return {
        "hasActiveProblem": False,
        "awaiting": "problem_desc",
        "pending_problem_desc": None,
        "assistant_reply": (
            f"{note_line}\n\n"
            "Let's search again — please enter a new question / problem description."
        ),
        "latest_search_result": None,
        "tool_recommendations": [],
        "tools_presented": False,
        "tools_selected": [],
        "initializer_complete": True,
        "from_check_result": True,
    }


def _parse_satisfaction_reply(user_message: str) -> dict[str, Any]:
    """
    Parse whether the user fixed the issue (YES/NO/IRRELEVANT) and any extra detail
    (follow-up question / notes included in the same message).
    """
    prompt = (
        "The user was asked whether the home-repair tools were useful and whether "
        "they were able to fix the issue.\n"
        "Their reply may be a simple yes/no, OR yes/no plus extra detail "
        "(another question, remaining symptoms, notes).\n\n"
        "Return ONLY JSON in this exact shape:\n"
        '{"decision":"YES"|"NO"|"IRRELEVANT","detail":string|null}\n\n'
        "Rules:\n"
        "- decision YES = they fixed it / are satisfied / tools helped enough\n"
        "- decision NO = not fixed / still need help / tools were not enough\n"
        "- decision IRRELEVANT = cannot tell yes vs no\n"
        "- detail = any follow-up problem, question, or useful note beyond the yes/no "
        "that appears in the user reply. Copy/closely paraphrase only what they added. "
        "Use null if there is no extra substance (simple yes/no/nope/etc with nothing else).\n"
        "- Never invent detail that the user did not write.\n"
        "- Do not put the words yes/no alone into detail.\n\n"
        f"Question: {Q_SATISFIED}\n"
        f"User reply: {user_message}\n"
    )
    try:
        response = llm().invoke(prompt)
        parsed = parse_json_blob(
            response.content if hasattr(response, "content") else str(response)
        )
        if isinstance(parsed, dict):
            decision = str(parsed.get("decision") or "").strip().upper()
            if decision not in {"YES", "NO", "IRRELEVANT"}:
                decision = "IRRELEVANT"
            detail = parsed.get("detail")
            if detail is not None:
                detail = str(detail).strip() or None
            return {"decision": decision, "detail": detail}
    except Exception:
        pass

    # Fallback: classification only
    return {
        "decision": classify_yes_no(user_message, Q_SATISFIED),
        "detail": None,
    }


def _build_resolution_summary(
    state: ChatState,
    *,
    fixed: bool,
    user_reply: str,
    extra_detail: str | None = None,
) -> str:
    """Generate a ResolutionDetail summary under 35 words."""
    selected = state.get("tools_selected") or []
    suggested = state.get("tool_recommendations") or []
    selected_names = ", ".join(
        t.get("ToolKind", "") for t in selected if t.get("ToolKind")
    ) or "none"
    suggested_names = ", ".join(
        t.get("ToolKind", "") for t in suggested if t.get("ToolKind")
    ) or "none"
    user_selected_tools = bool(selected)

    active = state.get("active_component") or {}
    problem = active.get("ProblemDesc") or state.get("latest_search_question") or ""
    search = (state.get("latest_search_result") or "")[:800]
    outcome = "fixed" if fixed else "not fixed yet"

    if user_selected_tools:
        tool_instruction = (
            "The user SELECTED one or more home-repair tools. You may mention those "
            "selected tools. If the outcome is fixed, you may say the issue was addressed "
            "with help from those selected tools. If not fixed, do not claim resolution."
        )
        tools_line = (
            f"Selected tools: {selected_names}\n"
            f"Suggested catalog tools: {suggested_names}"
        )
    else:
        tool_instruction = (
            "The user did NOT select any home-repair tools. You MUST say that we only "
            "SUGGESTED tools (do not say the user used them, chose them, or that the "
            "issue was resolved using those tools). Phrase it as suggestions only, "
            "even if the outcome is fixed."
        )
        tools_line = f"Suggested tools (none selected): {suggested_names}"

    extra_instruction = ""
    if extra_detail:
        extra_instruction = (
            "The user also provided extra detail while saying the issue was fixed. "
            "Incorporate that detail into the ResolutionDetail summary.\n"
            f"Extra detail: {extra_detail}\n"
        )

    prompt = (
        "Write a brief home-repair resolution note for the database.\n"
        "Hard limit: fewer than 35 words.\n"
        "Mention the problem, tool situation, and whether the issue was fixed.\n"
        f"{tool_instruction}\n"
        f"{extra_instruction}"
        "Return plain text only — no quotes or prefix.\n\n"
        f"Problem: {problem}\n"
        f"{tools_line}\n"
        f"User selected tools: {'yes' if user_selected_tools else 'no'}\n"
        f"Search excerpt: {search}\n"
        f"User said: {user_reply}\n"
        f"Outcome: {outcome}\n"
    )
    try:
        response = llm().invoke(prompt)
        text = (response.content if hasattr(response, "content") else str(response)).strip()
        words = text.split()
        if len(words) > 34:
            text = " ".join(words[:34])
        if text:
            return text
    except Exception:
        pass

    status = "resolved" if fixed else "unresolved"
    if user_selected_tools:
        fallback = (
            f"Used selected tools ({selected_names}) for '{problem or 'repair'}'; "
            f"status: {status}."
        )
    else:
        fallback = (
            f"Suggested tools ({suggested_names}) for '{problem or 'repair'}'; "
            f"none selected; status: {status}."
        )
    if extra_detail:
        fallback += f" Note: {extra_detail}"
    return " ".join(fallback.split()[:34])
