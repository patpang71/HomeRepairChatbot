"""Initializer node."""

from __future__ import annotations

import json
import re
from typing import Any

import tools as db_tools
from graph.nodes.common import (
    Q_LAST_RESOLUTION,
    ask_for_component,
    latest_component,
    llm,
    load_user,
    set_active_from_component,
)
from graph.state import ChatState
from tools.common import normalize_user_preference

Q_PREFERENCE = (
    "Would you like Concise answers (short summary of the top findings) "
    "or Detail answers (more sources and fuller explanations)?\n"
    "Reply with Concise or Detail. (Default is Concise.)"
)


def initializer(state: ChatState) -> dict[str, Any]:
    awaiting = state.get("awaiting")
    user_msg = (state.get("last_user_message") or "").strip()

    # Bootstrap: ask for email
    if not awaiting and not state.get("email"):
        return {
            "awaiting": "email",
            "assistant_reply": (
                "Welcome to the Home Repair Chatbot!\n"
                "Please enter your email address to get started."
            ),
        }

    if awaiting == "email":
        email = _extract_email(user_msg)
        if not email:
            return {
                "awaiting": "email",
                "assistant_reply": (
                    "I could not find a valid email in that message. "
                    "Please enter your email address (for example, name@example.com)."
                ),
            }

        info = load_user(email)
        if info.get("found"):
            name = email.split("@")[0]
            greet = (
                f"Welcome back, {name}!\n"
                f"Loaded your profile ({info.get('StreetAddress') or 'no street on file'}, "
                f"{info.get('City') or ''}, {info.get('State') or ''} {info.get('Zip') or ''}).\n"
                f"Answer preference: {info.get('Preference') or 'concise'}."
            )
            # Refresh user info via tool, then continue based on last component
            info = load_user(email)
            return {
                "email": email,
                "user_id": str(info["UserId"]),
                "user_info": info,
                **_continue_after_user_info(info, greet),
            }

        return {
            "email": email,
            "awaiting": "new_user_details",
            "assistant_reply": (
                f"I could not find an account for {email}.\n"
                "Please enter your Street Address, City, State, and Zip as:\n"
                "StreetAddress | City | State | Zip\n"
                "(Street, City, and State are optional, but Zip is required.)\n"
                "Example: 123 B St | Union City | CA | 94587"
            ),
        }

    if awaiting == "new_user_details":
        email = state.get("email") or ""
        parts = [p.strip() for p in user_msg.split("|")]
        if len(parts) == 1 and parts[0]:
            street, city, region, zip_code = None, None, None, parts[0]
        elif len(parts) >= 4:
            street, city, region, zip_code = parts[0], parts[1], parts[2], parts[3]
        elif len(parts) == 2:
            street, city, region, zip_code = None, None, parts[0], parts[1]
        else:
            return {
                "awaiting": "new_user_details",
                "assistant_reply": (
                    "Please provide details as: StreetAddress | City | State | Zip\n"
                    "Or just your Zip if that is all you have."
                ),
            }

        if not zip_code:
            return {
                "awaiting": "new_user_details",
                "assistant_reply": "Zip is required. Please try again.",
            }

        # Collect Preference before calling add_user
        return {
            "email": email,
            "pending_new_user": {
                "Email": email,
                "Zip": zip_code,
                "StreetAddress": street or None,
                "City": city or None,
                "State": region or None,
            },
            "awaiting": "preference",
            "assistant_reply": Q_PREFERENCE,
        }

    if awaiting == "preference":
        pending = state.get("pending_new_user") or {}
        email = state.get("email") or pending.get("Email") or ""
        if not pending.get("Zip") or not email:
            return {
                "pending_new_user": None,
                "awaiting": "new_user_details",
                "assistant_reply": (
                    "I lost the sign-up details. Please re-enter "
                    "StreetAddress | City | State | Zip "
                    "(or just Zip)."
                ),
            }

        preference = _parse_preference(user_msg)
        if preference is None:
            return {
                "awaiting": "preference",
                "assistant_reply": (
                    "Sorry, I wasn't sure which preference you want.\n"
                    f"{Q_PREFERENCE}"
                ),
            }

        created = json.loads(
            db_tools.add_user(
                Email=email,
                Zip=pending["Zip"],
                StreetAddress=pending.get("StreetAddress"),
                City=pending.get("City"),
                State=pending.get("State"),
                Preference=preference,
            )
        )
        if not created.get("success"):
            return {
                "awaiting": "preference",
                "assistant_reply": (
                    f"Could not create user: {created.get('error')}. "
                    "Please choose Concise or Detail again."
                ),
            }

        info = load_user(email)
        greet = (
            f"Thanks! Your account has been created for {email} "
            f"with a {preference} answer preference."
        )
        return {
            "email": email,
            "user_id": str(info["UserId"]),
            "user_info": info,
            "pending_new_user": None,
            **_continue_after_user_info(info, greet),
        }

    if awaiting == "last_resolution_ok":
        return _handle_last_resolution_reply(state, user_msg)

    if state.get("user_id") and state.get("awaiting") is None:
        return {"assistant_reply": state.get("assistant_reply") or "Continuing..."}

    return {
        "awaiting": "email",
        "assistant_reply": "Please enter your email address to continue.",
    }


def _parse_preference(text: str) -> str | None:
    """Interpret Concise vs Detail (empty reply -> default concise)."""
    raw = (text or "").strip()
    if not raw:
        return normalize_user_preference("concise")

    preferred = normalize_user_preference(raw)
    if preferred:
        return preferred

    prompt = (
        "The user was asked whether they prefer Concise or Detail answers.\n"
        "Return ONLY one token: CONCISE, DETAIL, or UNCLEAR.\n"
        "- CONCISE = short / brief / summary style\n"
        "- DETAIL = detailed / thorough / fuller explanations\n"
        "- UNCLEAR = cannot tell\n\n"
        f"User reply: {raw}\n"
    )
    try:
        response = llm().invoke(prompt)
        content = (
            response.content if hasattr(response, "content") else str(response)
        ).strip().upper()
        if re.search(r"\bCONCISE\b", content):
            return "concise"
        if re.search(r"\bDETAIL\b", content):
            return "detail"
    except Exception:
        pass
    return None


def _extract_email(text: str) -> str | None:
    """Use LLM (with regex fallback) to pull an email address from user text."""
    raw = (text or "").strip()
    if not raw:
        return None

    prompt = (
        "Extract the email address from the user message.\n"
        "Return ONLY the email address, or NONE if no valid email is present.\n\n"
        f"User message: {raw}\n"
    )
    try:
        response = llm().invoke(prompt)
        content = (response.content if hasattr(response, "content") else str(response)).strip()
        if content.upper() != "NONE":
            match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", content, re.I)
            if match:
                return match.group(0)
    except Exception:
        pass

    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", raw, re.I)
    return match.group(0) if match else None


def _continue_after_user_info(info: dict[str, Any], greet: str) -> dict[str, Any]:
    """
    After get_userinfo_from_email:
    1) No component -> TavilySearch to add a new component
    2) Has last component -> discuss ResolutionDetail and ask if satisfied
    """
    latest = latest_component(info)
    if not latest:
        return {
            "hasActiveComponent": False,
            "hasActiveProblem": False,
            "active_component_id": None,
            "active_component": None,
            "awaiting": "component_type",
            "initializer_complete": True,
            "from_check_result": False,
            "assistant_reply": (
                f"{greet}\n\n"
                "I do not see any home components on your account yet.\n"
                f"{ask_for_component()}"
            ),
        }

    question = _ask_about_last_resolution(latest)
    return {
        "hasActiveComponent": False,
        "hasActiveProblem": False,
        "active_component_id": None,
        "active_component": None,
        "awaiting": "last_resolution_ok",
        "initializer_complete": False,
        "from_check_result": False,
        "assistant_reply": f"{greet}\n\n{question}",
    }


def _ask_about_last_resolution(latest: dict[str, Any]) -> str:
    """Open a short conversation about the last component's ResolutionDetail."""
    prompt = (
        "You are a helpful home-repair assistant. Using the last component record below, "
        "write a short friendly message (3-5 sentences) that:\n"
        "1) Reminds the user what component/problem they last worked on\n"
        "2) Summarizes the saved ResolutionDetail if present (or notes that none was saved)\n"
        "3) Asks whether they are satisfied with that resolution, or if more help is needed\n"
        "Do not mention being an AI. Do not ask them to answer only yes/no.\n\n"
        f"Component Type: {latest.get('Type')}\n"
        f"Manufacturer: {latest.get('ManufacturerId') or 'N/A'}\n"
        f"Problem: {latest.get('ProblemDesc') or 'N/A'}\n"
        f"Resolved: {latest.get('Resolved')}\n"
        f"ResolutionDetail: {latest.get('ResolutionDetail') or '(none)'}\n"
        f"TimeStamp: {latest.get('TimeStamp') or 'N/A'}\n"
    )
    try:
        response = llm().invoke(prompt)
        text = (response.content if hasattr(response, "content") else str(response)).strip()
        if text:
            return text
    except Exception:
        pass

    detail = latest.get("ResolutionDetail") or "No resolution note was saved yet."
    return (
        f"Looking at your latest {latest.get('Type')} work "
        f"(problem: {latest.get('ProblemDesc') or 'N/A'}):\n"
        f"{detail}\n\n"
        f"{Q_LAST_RESOLUTION}"
    )


def _handle_last_resolution_reply(state: ChatState, user_msg: str) -> dict[str, Any]:
    """
    Scenario 2: happy with last resolution -> add a new component via TavilySearch
    Scenario 3: not happy -> keep last component active and expect a new problem
    """
    email = state.get("email") or ""
    info = state.get("user_info") or load_user(email)
    latest = latest_component(info)

    decision = _classify_resolution_satisfaction(user_msg, latest)
    if decision == "IRRELEVANT":
        detail_q = (
            _ask_about_last_resolution(latest)
            if latest
            else Q_LAST_RESOLUTION
        )
        return {
            "awaiting": "last_resolution_ok",
            "assistant_reply": (
                "Sorry, I wasn't sure whether you are satisfied with the last resolution "
                "or still need help on that same repair.\n\n"
                f"{detail_q}"
            ),
        }

    if decision == "YES":
        # Happy — mark last component resolved, then start a new component
        if latest and info.get("UserId"):
            try:
                json.loads(
                    db_tools.update_home_component(
                        ComponentId=latest["ComponentId"],
                        UserId=info["UserId"],
                        field="Resolved",
                        value=True,
                    )
                )
            except Exception:
                pass
            # Refresh so downstream nodes do not keep stale unresolved data
            info = load_user(email)

        return {
            "user_info": info,
            "hasActiveComponent": False,
            "hasActiveProblem": False,
            "active_component_id": None,
            "active_component": None,
            "candidate_component": None,
            "pending_component": None,
            "awaiting": "component_type",
            "initializer_complete": True,
            "from_check_result": False,
            "assistant_reply": (
                "Glad that resolution worked for you!\n"
                "Let's start a new repair item.\n"
                f"{ask_for_component()}"
            ),
        }

    # Not happy — continue with the last component and collect a new problem
    if not latest:
        return {
            "hasActiveComponent": False,
            "hasActiveProblem": False,
            "awaiting": "component_type",
            "initializer_complete": True,
            "from_check_result": False,
            "assistant_reply": (
                "I could not find your last component, so let's add one.\n"
                f"{ask_for_component()}"
            ),
        }

    updates = set_active_from_component(state, latest)
    updates["hasActiveProblem"] = False
    updates["awaiting"] = "problem_desc"
    updates["user_info"] = info
    updates["initializer_complete"] = True
    updates["from_check_result"] = False
    updates["assistant_reply"] = (
        f"Okay — we'll keep working on your {latest.get('Type')} "
        f"(ComponentId {latest.get('ComponentId')}).\n"
        f"Previous problem on file: {latest.get('ProblemDesc') or '(none)'}\n"
        f"Previous resolution note: {latest.get('ResolutionDetail') or '(none)'}\n"
        "Please enter the new question / problem you still need help with."
    )
    return updates


def _classify_resolution_satisfaction(
    user_message: str,
    latest: dict[str, Any] | None,
) -> str:
    """
    Classify whether the user is happy with the last resolution.
    YES = satisfied / done, NO = needs more help, IRRELEVANT = unclear.
    """
    heuristic = _heuristic_resolution_satisfaction(user_message)
    if heuristic in {"YES", "NO"}:
        return heuristic

    prompt = (
        "A homeowner was asked if they are satisfied with their last repair resolution "
        "or if they still need help on THAT SAME repair.\n"
        "Decide from the USER REPLY only. Do not use the old ResolutionDetail to override "
        "what the homeowner just said.\n"
        "Return ONLY one token: YES, NO, or IRRELEVANT.\n"
        "- YES = satisfied / happy / issue is resolved / fixed / all good / ready for a new item\n"
        "- NO = still broken / not fixed / need more help on the same job\n"
        "- IRRELEVANT = unclear / off-topic\n\n"
        f"User reply: {user_message}\n"
        "Classification:"
    )
    try:
        response = llm().invoke(prompt)
        content = (
            response.content if hasattr(response, "content") else str(response)
        ).strip().upper()
        # Prefer an explicit first-token YES/NO over accidental substring matches
        first = content.split()[0].strip(".,:;!") if content.split() else ""
        if first in {"YES", "NO", "IRRELEVANT"}:
            return first
        for label in ("IRRELEVANT", "YES", "NO"):
            if re.search(rf"\b{label}\b", content):
                return label
    except Exception:
        pass
    return "IRRELEVANT"


def _heuristic_resolution_satisfaction(user_message: str) -> str | None:
    """Fast path for clear satisfied / still-need-help wording."""
    lower = " ".join((user_message or "").lower().split())
    if not lower:
        return None

    # Negated satisfaction first
    no_patterns = (
        r"\bnot (fixed|resolved|satisfied|happy|done)\b",
        r"\bstill (broken|leaking|flickering|not|have|need|unresolved)\b",
        r"\bneed(s)? more (help|assistance)\b",
        r"\bmore help\b",
        r"\bunresolved\b",
        r"\bkeep working\b",
        r"\bnot yet\b",
        r"^(no|nope|nah)\b",
    )
    if any(re.search(p, lower) for p in no_patterns):
        return "NO"

    yes_patterns = (
        r"\bsatisf",  # satisfy / satisfied / satisfaction
        r"\b(that |the |this )?(issue|problem|it) (is |was )?(fixed|resolved)\b",
        r"\b(fixed|resolved)( it| the problem| the issue)?\b",
        r"\ball good\b",
        r"\ball set\b",
        r"\b(i'?m |i am )?happy\b",
        r"\bworks?( now| fine| good)?\b",
        r"\bno (more )?help (needed|necessary)\b",
        r"\bready for (a )?new\b",
        r"^(yes|yep|yeah|y)\b",
    )
    if any(re.search(p, lower) for p in yes_patterns):
        return "YES"

    return None
