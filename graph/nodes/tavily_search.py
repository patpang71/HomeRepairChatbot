"""TavilySearch node."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from tavily import TavilyClient

import tools as db_tools
from graph.nodes.common import (
    Q_REUSE_TYPE,
    Q_USE_LATEST,
    ask_for_component_type,
    ask_for_manufacturer,
    ask_for_problem,
    ask_use_latest,
    classify_yes_no,
    latest_component,
    llm,
    load_user,
    parse_json_blob,
    reask_yes_no,
    set_active_from_component,
)
from graph.state import ChatState
from tools.common import DEFAULT_USER_PREFERENCE, normalize_user_preference


def tavily_search(state: ChatState) -> dict[str, Any]:
    awaiting = state.get("awaiting")
    user_msg = (state.get("last_user_message") or "").strip()
    user_id = state.get("user_id")
    email = state.get("email")
    user_info = state.get("user_info") or (load_user(email) if email else {})

    # ---- Entry routing when no specific await state ----
    if awaiting is None:
        return _tavily_entry(state, user_info)

    # ---- Step 1: component type, then check prior work on that type ----
    if awaiting == "component_type":
        type_name = _resolve_component_type(user_msg)
        if not type_name:
            return {
                "awaiting": "component_type",
                "assistant_reply": (
                    "I could not recognize a home component type in that message.\n"
                    f"{ask_for_component_type()}"
                ),
            }
        pending = {
            "Type": type_name,
            "ManufacturerId": None,
            "ProblemDesc": None,
        }
        info = load_user(email or "")
        prior = _find_component_by_type(info, type_name)
        if prior:
            return {
                "user_info": info,
                "pending_component": pending,
                "candidate_component": prior,
                "awaiting": "reuse_type_component",
                "assistant_reply": (
                    f"Got it — using component type {type_name}.\n\n"
                    f"{_ask_reuse_type_component(prior, pending)}"
                ),
            }

        return {
            "user_info": info,
            "pending_component": pending,
            "candidate_component": None,
            "awaiting": "component_manufacturer",
            "assistant_reply": (
                f"Got it — using component type {type_name}.\n"
                f"{ask_for_manufacturer()}"
            ),
        }

    # ---- Step 2: manufacturer (new component path) ----
    if awaiting == "component_manufacturer":
        pending = dict(state.get("pending_component") or {})
        if not pending.get("Type"):
            return {
                "awaiting": "component_type",
                "pending_component": None,
                "assistant_reply": ask_for_component_type(),
            }
        manufacturer = _interpret_manufacturer(user_msg)
        pending["ManufacturerId"] = manufacturer
        note = (
            f"Manufacturer set to: {manufacturer}."
            if manufacturer
            else "Okay — I'll leave the manufacturer blank."
        )
        return {
            "pending_component": pending,
            "awaiting": "component_problem",
            "assistant_reply": f"{note}\n{ask_for_problem()}",
        }

    # ---- Step 3: problem for a NEW component, then create ----
    if awaiting == "component_problem":
        pending = dict(state.get("pending_component") or {})
        if not pending.get("Type"):
            return {
                "awaiting": "component_type",
                "pending_component": None,
                "assistant_reply": ask_for_component_type(),
            }
        problem = (user_msg or "").strip()
        if not problem:
            return {
                "awaiting": "component_problem",
                "assistant_reply": (
                    "Please describe the problem you are facing.\n"
                    f"{ask_for_problem()}"
                ),
            }
        pending["ProblemDesc"] = problem

        return _create_component_and_continue(
            state,
            user_id=user_id,
            email=email,
            Type=pending["Type"],
            ManufacturerId=pending.get("ManufacturerId"),
            ProblemDesc=pending.get("ProblemDesc"),
            clear_pending=True,
        )

    # ---- Same TYPE exists: continue with it, or start a new one ----
    if awaiting == "reuse_type_component":
        prior = state.get("candidate_component")
        pending = dict(state.get("pending_component") or {})
        if not prior:
            return {
                "awaiting": "component_type",
                "assistant_reply": ask_for_component_type(),
                "pending_component": None,
                "candidate_component": None,
            }

        decision = classify_yes_no(user_msg, Q_REUSE_TYPE)
        if decision == "IRRELEVANT":
            return {
                "awaiting": "reuse_type_component",
                "assistant_reply": reask_yes_no(
                    Q_REUSE_TYPE + "\n\n" + _ask_reuse_type_component(prior, pending),
                    user_msg,
                ),
            }

        if decision == "YES":
            # Activate existing component and ask for the current problem
            updates = set_active_from_component(state, prior)
            updates["hasActiveProblem"] = False
            updates["pending_component"] = None
            updates["candidate_component"] = None
            updates["user_info"] = load_user(email or "")
            updates["awaiting"] = "problem_desc"
            updates["assistant_reply"] = (
                f"Okay — we'll continue with your existing {prior.get('Type')} "
                f"(ComponentId {prior.get('ComponentId')}).\n"
                f"Previous resolution: {prior.get('ResolutionDetail') or '(none)'}\n"
                f"{ask_for_problem()}"
            )
            return updates

        # NO — collect manufacturer + problem, then create a new component
        return {
            "candidate_component": None,
            "pending_component": {
                "Type": pending.get("Type") or prior.get("Type"),
                "ManufacturerId": None,
                "ProblemDesc": None,
            },
            "awaiting": "component_manufacturer",
            "assistant_reply": (
                f"Okay — we'll create a new {pending.get('Type') or prior.get('Type')} "
                f"component.\n"
                f"{ask_for_manufacturer()}"
            ),
        }

    # ---- No active component, but history exists: use latest? ----
    if awaiting == "use_latest_component":
        latest = latest_component(user_info)
        if not latest:
            return {
                "awaiting": "component_type",
                "assistant_reply": ask_for_component_type(),
            }

        decision = classify_yes_no(user_msg, Q_USE_LATEST)
        if decision == "NO":
            return {
                "hasActiveComponent": False,
                "hasActiveProblem": False,
                "active_component_id": None,
                "active_component": None,
                "awaiting": "component_type",
                "assistant_reply": ask_for_component_type(),
            }

        if decision == "IRRELEVANT":
            return {
                "awaiting": "use_latest_component",
                "assistant_reply": reask_yes_no(
                    Q_USE_LATEST + "\n\n" + ask_use_latest(latest),
                    user_msg,
                ),
            }

        updates = set_active_from_component(state, latest)
        updates["hasActiveProblem"] = False
        updates["awaiting"] = "problem_desc"
        updates["assistant_reply"] = (
            f"Using your latest {latest.get('Type')} component "
            f"(Manufacturer: {latest.get('ManufacturerId') or 'unknown'}).\n"
            f"Previous problem on file: {latest.get('ProblemDesc') or '(none)'}\n"
            "Please enter the problem you are having now."
        )
        return updates

    # ---- Need / refresh ProblemDesc, then search ----
    if awaiting == "problem_desc":
        # Prefer follow-up detail captured by CheckResult (if any)
        pending_problem = (state.get("pending_problem_desc") or "").strip()
        problem = pending_problem or user_msg
        if not problem:
            return {
                "awaiting": "problem_desc",
                "assistant_reply": "Please describe the problem you are having.",
            }

        component_id = state.get("active_component_id")
        if not component_id:
            return {
                "hasActiveComponent": False,
                "hasActiveProblem": False,
                "awaiting": "component_type",
                "pending_problem_desc": None,
                "assistant_reply": (
                    "I lost track of the active component. "
                    f"{ask_for_component_type()}"
                ),
            }

        updated = json.loads(
            db_tools.update_home_component(
                ComponentId=component_id,
                UserId=user_id,
                field="ProblemDesc",
                value=problem,
            )
        )
        if not updated.get("success"):
            return {
                "awaiting": "problem_desc",
                "assistant_reply": f"Could not update problem: {updated.get('error')}",
            }

        active = dict(state.get("active_component") or {})
        active["ProblemDesc"] = problem
        search_updates = _run_search_and_save(
            user_id=user_id,
            component_id=str(component_id),
            component_type=active.get("Type") or updated.get("Type"),
            manufacturer=active.get("ManufacturerId") or updated.get("ManufacturerId"),
            problem=problem,
            preference=_preference_from_state(state, user_info),
        )
        reply = search_updates.get("assistant_reply") or ""
        if pending_problem:
            # Keep CheckResult's apology/summary when auto-continuing in the same turn
            prior_reply = (state.get("assistant_reply") or "").strip()
            follow_up = (
                f"Got it — I'll search using your follow-up problem:\n{problem}\n\n{reply}"
            ).strip()
            reply = f"{prior_reply}\n\n{follow_up}".strip() if prior_reply else follow_up
            search_updates["assistant_reply"] = reply

        return {
            "hasActiveComponent": True,
            "hasActiveProblem": True,
            "active_component": active,
            "user_info": load_user(email or ""),
            "from_check_result": False,
            "pending_problem_desc": None,
            **search_updates,
        }

    return {
        "awaiting": "component_type",
        "assistant_reply": ask_for_component_type(),
    }


def _tavily_entry(state: ChatState, user_info: dict[str, Any]) -> dict[str, Any]:
    """Decide the next Tavily prompt when awaiting is unset."""
    # 1) Already working on a component
    if state.get("hasActiveComponent") and state.get("active_component_id"):
        if state.get("hasActiveProblem"):
            active = state.get("active_component") or {}
            search_updates = _run_search_and_save(
                user_id=state.get("user_id"),
                component_id=str(state.get("active_component_id")),
                component_type=active.get("Type") or "",
                manufacturer=active.get("ManufacturerId"),
                problem=active.get("ProblemDesc") or state.get("latest_search_question") or "",
                preference=_preference_from_state(state, user_info),
            )
            return {
                "from_check_result": False,
                "user_info": user_info,
                **search_updates,
            }
        return {
            "awaiting": "problem_desc",
            "hasActiveProblem": False,
            "from_check_result": False,
            "assistant_reply": (
                "Please enter a new question / problem description for your "
                "current component."
            ),
            "user_info": user_info,
        }

    # 2) No active component — ask for component info (or offer latest if history exists
    #    and we are not explicitly coming from CheckResult new-job paths)
    latest = latest_component(user_info)
    if state.get("from_check_result"):
        return {
            "awaiting": "component_type",
            "from_check_result": False,
            "assistant_reply": ask_for_component_type(),
            "user_info": user_info,
        }

    if latest and state.get("initializer_complete"):
        # Spec: if hasActiveComponent is false and there is a component, ask to use latest
        return {
            "awaiting": "use_latest_component",
            "hasActiveProblem": False,
            "assistant_reply": ask_use_latest(latest),
            "user_info": user_info,
        }

    if latest:
        return {
            "awaiting": "use_latest_component",
            "hasActiveProblem": False,
            "assistant_reply": ask_use_latest(latest),
            "user_info": user_info,
        }

    return {
        "awaiting": "component_type",
        "assistant_reply": ask_for_component_type(),
        "user_info": user_info,
    }


def _find_component_by_type(
    user_info: dict[str, Any] | None,
    component_type: str,
) -> dict[str, Any] | None:
    """Return the most recent component matching Type (Components are latest-first)."""
    if not user_info:
        return None
    wanted = (component_type or "").strip().upper()
    for comp in user_info.get("Components") or []:
        if str(comp.get("Type") or "").strip().upper() == wanted:
            return comp
    return None


def _ask_reuse_type_component(prior: dict[str, Any], pending: dict[str, Any]) -> str:
    detail = prior.get("ResolutionDetail") or "(no resolution detail saved)"
    return (
        f"I found a previous {prior.get('Type')} on your account "
        f"(ComponentId {prior.get('ComponentId')}).\n"
        f"Manufacturer: {prior.get('ManufacturerId') or 'N/A'}\n"
        f"Previous problem: {prior.get('ProblemDesc') or 'N/A'}\n"
        f"Resolved: {prior.get('Resolved')}\n"
        f"Previous resolution: {detail}\n"
        f"Time: {prior.get('TimeStamp') or 'N/A'}\n\n"
        f"You selected type {pending.get('Type')}. "
        "Is this the component you want to work on now?"
    )


def _continue_with_prior_component(
    state: ChatState,
    *,
    prior: dict[str, Any],
    pending: dict[str, Any],
    user_id: str | None,
    email: str | None,
) -> dict[str, Any]:
    """
    Reuse an existing same-type component. Apply ManufacturerId / ProblemDesc from
    the user's latest input when provided, instead of asking again.
    """
    component_id = prior.get("ComponentId")
    active = dict(prior)
    manufacturer = (pending.get("ManufacturerId") or "").strip() or None
    problem = (pending.get("ProblemDesc") or "").strip() or None

    if manufacturer:
        updated = json.loads(
            db_tools.update_home_component(
                ComponentId=component_id,
                UserId=user_id,
                field="ManufacturerId",
                value=manufacturer,
            )
        )
        if updated.get("success"):
            active["ManufacturerId"] = manufacturer

    if problem:
        updated = json.loads(
            db_tools.update_home_component(
                ComponentId=component_id,
                UserId=user_id,
                field="ProblemDesc",
                value=problem,
            )
        )
        if updated.get("success"):
            active["ProblemDesc"] = problem

    base: dict[str, Any] = {
        "hasActiveComponent": True,
        "active_component_id": str(component_id),
        "active_component": active,
        "pending_component": None,
        "candidate_component": None,
        "user_info": load_user(email or ""),
        "from_check_result": False,
    }

    note = (
        f"Continuing with your existing {active.get('Type')} component "
        f"(ComponentId {component_id}).\n"
        f"Previous resolution: {prior.get('ResolutionDetail') or '(none)'}"
    )
    if manufacturer:
        note += f"\nUpdated manufacturer to: {manufacturer}"
    if problem:
        note += f"\nUsing your problem description: {problem}"

    if problem:
        search_updates = _run_search_and_save(
            user_id=user_id,
            component_id=str(component_id),
            component_type=active.get("Type") or "",
            manufacturer=active.get("ManufacturerId"),
            problem=problem,
            preference=_preference_from_state(state),
        )
        search_updates["assistant_reply"] = (
            f"{note}\n\n{search_updates.get('assistant_reply') or ''}"
        ).strip()
        return {
            **base,
            "hasActiveProblem": True,
            **search_updates,
        }

    return {
        **base,
        "hasActiveProblem": False,
        "awaiting": "problem_desc",
        "assistant_reply": (
            f"{note}\n"
            "Please enter the problem you are having now."
        ),
    }


def _create_component_and_continue(
    state: ChatState,
    *,
    user_id: str | None,
    email: str | None,
    Type: str,
    ManufacturerId: str | None,
    ProblemDesc: str | None,
    clear_pending: bool = False,
) -> dict[str, Any]:
    """add_component, set active flags, then ask for problem or run search."""
    created = json.loads(
        db_tools.add_component(
            UserId=user_id,
            Type=Type,
            ManufacturerId=ManufacturerId,
            ProblemDesc=ProblemDesc,
        )
    )
    if not created.get("success"):
        return {
            "awaiting": "component_type",
            "pending_component": None if clear_pending else state.get("pending_component"),
            "candidate_component": None if clear_pending else state.get("candidate_component"),
            "assistant_reply": f"Failed to add component: {created.get('error')}",
        }

    has_problem = bool((ProblemDesc or "").strip())
    updates: dict[str, Any] = {
        "hasActiveComponent": True,
        "hasActiveProblem": has_problem,
        "active_component_id": str(created["ComponentId"]),
        "active_component": created,
        "user_info": load_user(email or ""),
        "from_check_result": False,
    }
    if clear_pending:
        updates["pending_component"] = None
        updates["candidate_component"] = None

    if not has_problem:
        updates.update(
            {
                "awaiting": "problem_desc",
                "assistant_reply": (
                    f"Added a new {created['Type']} component.\n"
                    "What problem are you having with it?"
                ),
            }
        )
        return updates

    search_updates = _run_search_and_save(
        user_id=user_id,
        component_id=str(created["ComponentId"]),
        component_type=created["Type"],
        manufacturer=created.get("ManufacturerId"),
        problem=created.get("ProblemDesc") or "",
        preference=_preference_from_state(state),
    )
    updates.update(search_updates)
    return updates




def _interpret_manufacturer(text: str) -> str | None:
    """
    Return a manufacturer/brand string.
    Leave blank (None) ONLY when the reply means they don't know / not sure /
    unknown / no brand. Otherwise keep whatever brand name they typed,
    even if it is unrecognized.
    """
    raw = (text or "").strip()
    if not raw:
        return None

    prompt = (
        "The user was asked for a home-component manufacturer/brand.\n"
        "Return ONLY JSON: {\"unsure\": true|false, \"manufacturer\": string|null}\n\n"
        "Rules:\n"
        "- Set unsure=true ONLY if the reply clearly means they do not know the brand, "
        "are not sure, say unknown, or say there is no brand / no manufacturer. "
        "In that case manufacturer must be null.\n"
        "- Otherwise set unsure=false and put their brand/name in manufacturer. "
        "Keep their wording as the brand even if you do not recognize it. "
        "You may lightly trim whitespace; do not invent a different brand.\n"
        "- Do NOT treat an unrecognized brand name as unsure.\n\n"
        f"User reply: {raw}\n"
    )
    try:
        response = llm().invoke(prompt)
        parsed = parse_json_blob(
            response.content if hasattr(response, "content") else str(response)
        )
        if isinstance(parsed, dict):
            if parsed.get("unsure") is True:
                return None
            value = parsed.get("manufacturer")
            if value is None:
                # Model said not unsure but gave null — keep original text
                return raw
            value = str(value).strip()
            return value or raw
    except Exception:
        pass

    return None if _manufacturer_looks_unsure(raw) else raw


def _manufacturer_looks_unsure(text: str) -> bool:
    """True only for clear 'I don't know / no brand' style replies (word-safe)."""
    lower = " ".join((text or "").lower().split())
    if not lower:
        return True

    exact = {
        "i'm not sure",
        "im not sure",
        "i am not sure",
        "not sure",
        "unknown",
        "don't know",
        "dont know",
        "do not know",
        "no idea",
        "no brand",
        "no manufacturer",
        "n/a",
        "na",
        "none",
        "no",
    }
    if lower in exact:
        return True

    # Phrase matches with word boundaries (avoid "none" matching "Nonexistent")
    phrase_patterns = (
        r"\bnot sure\b",
        r"\bdon'?t know\b",
        r"\bdo not know\b",
        r"\bno idea\b",
        r"\bunknown\b",
        r"\bno brand\b",
        r"\bno manufacturer\b",
        r"\bn/?a\b",
    )
    return any(re.search(p, lower) for p in phrase_patterns)


def _resolve_component_type(type_input: str) -> str | None:
    """
    Map free-text type input to a ComponentTypeName (SCREAMING_SNAKE_CASE).
    Matches existing DB types via LLM when possible; otherwise adds a new type.
    """
    known = []
    try:
        data = json.loads(db_tools.get_component_types())
        if data.get("success"):
            known = list(data.get("names") or [])
    except Exception:
        known = []

    decision = _normalize_component_type_with_llm(type_input, known)
    if not decision:
        return None

    action = decision.get("action")
    name = (decision.get("ComponentTypeName") or "").strip().upper().replace(" ", "_")
    if not name:
        return None

    if action == "EXISTING":
        # Prefer exact known match; still ensure DB has it
        for k in known:
            if k.upper() == name:
                return k
        # LLM said existing but name not listed — try add (idempotent) then return
        created = json.loads(db_tools.add_component_type(name))
        return created.get("ComponentTypeName") if created.get("success") else None

    if action == "NEW":
        created = json.loads(db_tools.add_component_type(name))
        if not created.get("success"):
            return None
        return created.get("ComponentTypeName")

    return None


def _normalize_component_type_with_llm(
    type_input: str,
    known_types: list[str],
) -> dict[str, Any] | None:
    """
    Use LLM to map user input like 'water heaters' -> WATER_HEATER.
    Returns {"action":"EXISTING"|"NEW"|"REJECT","ComponentTypeName":"..."}.
    """
    prompt = (
        "You normalize a home-repair component type name for a database.\n"
        "Return ONLY JSON:\n"
        '{"action":"EXISTING"|"NEW"|"REJECT","ComponentTypeName":"SCREAMING_SNAKE_CASE"}\n\n'
        "Rules:\n"
        "- Prefer matching an existing type when it is clearly the same thing "
        "(e.g. 'water heaters', 'Water Heater', 'waterheater' -> WATER_HEATER).\n"
        "- ComponentTypeName MUST be SCREAMING_SNAKE_CASE using A-Z, 0-9, underscore "
        "(example: WATER_HEATER, DISHWASHER, GARAGE_DOOR).\n"
        "- If it is a valid home appliance/fixture/component not in the list, action=NEW "
        "and invent a clear SCREAMING_SNAKE_CASE name.\n"
        "- If it is not a home repair component type, action=REJECT "
        "(ComponentTypeName can be empty).\n"
        "- Do not create near-duplicates of existing types.\n\n"
        f"Existing types: {json.dumps(known_types)}\n"
        f"User type input: {type_input}\n"
    )
    try:
        response = llm().invoke(prompt)
        parsed = parse_json_blob(
            response.content if hasattr(response, "content") else str(response)
        )
        if isinstance(parsed, dict):
            action = str(parsed.get("action") or "").strip().upper()
            if action not in {"EXISTING", "NEW", "REJECT"}:
                return None
            if action == "REJECT":
                return {"action": "REJECT", "ComponentTypeName": ""}
            name = str(parsed.get("ComponentTypeName") or "").strip()
            return {"action": action, "ComponentTypeName": name}
    except Exception:
        pass

    # Fallback without LLM: exact / simple normalize against known list
    candidate = type_input.strip().upper().replace(" ", "_")
    if candidate in {k.upper() for k in known_types}:
        return {"action": "EXISTING", "ComponentTypeName": candidate}
    compact = candidate.replace("_", "")
    for k in known_types:
        if k.upper().replace("_", "") == compact:
            return {"action": "EXISTING", "ComponentTypeName": k}
    if candidate and candidate.replace("_", "").isalnum():
        return {"action": "NEW", "ComponentTypeName": candidate}
    return None


def _preference_from_state(
    state: ChatState | None = None,
    user_info: dict[str, Any] | None = None,
) -> str:
    raw = None
    if state:
        raw = (state.get("user_info") or {}).get("Preference")
    if raw is None and user_info:
        raw = user_info.get("Preference")
    return normalize_user_preference(raw) or DEFAULT_USER_PREFERENCE


def _run_search_and_save(
    user_id: str,
    component_id: str,
    component_type: str,
    manufacturer: str | None,
    problem: str,
    preference: str = DEFAULT_USER_PREFERENCE,
) -> dict[str, Any]:
    query_bits = [problem]
    if component_type:
        query_bits.append(f"home repair {component_type.replace('_', ' ').lower()}")
    if manufacturer:
        query_bits.append(manufacturer)
    query = " ".join(q for q in query_bits if q).strip()

    mode = normalize_user_preference(preference) or DEFAULT_USER_PREFERENCE
    search_text = _tavily_search(query, preference=mode)
    try:
        saved = json.loads(
            db_tools.add_search_result(
                ComponentId=component_id,
                UserId=user_id,
                SearchQuestion=query,
                SearchResult=search_text,
            )
        )
    except Exception as exc:
        saved = {"success": False, "error": str(exc)}

    if saved.get("success"):
        save_note = f"(Saved to SearchResult id={saved.get('SearchId')}.)"
    else:
        err = saved.get("error") or "unknown error"
        save_note = f"(Could not save SearchResult: {err})"

    mode_note = "concise (top 2)" if mode == "concise" else "detail (deeper search)"
    reply = (
        f"Search complete for: {query}\n"
        f"Mode: {mode_note}\n\n"
        f"{search_text}\n\n"
        f"{save_note}"
    )
    return {
        "latest_search_question": query,
        "latest_search_result": search_text,
        "tools_presented": False,
        "tool_recommendations": [],
        "tools_selected": [],
        "awaiting": None,
        "assistant_reply": reply,
    }


def _tavily_search(query: str, preference: str = DEFAULT_USER_PREFERENCE) -> str:
    mode = normalize_user_preference(preference) or DEFAULT_USER_PREFERENCE
    # concise → top 2 basic results; detail → more results + advanced depth
    if mode == "detail":
        max_results = 8
        search_depth = "advanced"
    else:
        max_results = 2
        search_depth = "basic"

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        if mode == "detail":
            return (
                f"[Mock Tavily detail result — set TAVILY_API_KEY for live search]\n"
                f"Detailed guide for '{query}':\n"
                f"1) Safety: shut off water/power as needed and photograph the area.\n"
                f"2) Diagnose: inspect seals, cartridges, wiring, or fasteners for wear.\n"
                f"3) Repair: replace the faulty valve/cartridge/part; use a wrench, "
                f"screwdriver, pliers, and Teflon tape as needed.\n"
                f"4) Verify: reopen supply, check for leaks, and retest the fixture.\n"
                f"Common tools/parts: screwdriver, pliers, pipe wrench, bucket, cartridge."
            )
        return (
            f"[Mock Tavily concise result — set TAVILY_API_KEY for live search]\n"
            f"For '{query}': shut off water, inspect for leaks or wear, replace the "
            f"faulty part with a wrench/screwdriver, then retest. "
            f"Common tools: screwdriver, pliers, pipe wrench, bucket."
        )

    client = TavilyClient(api_key=api_key)
    result = client.search(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        include_answer=(mode == "detail"),
    )
    chunks = []
    for item in result.get("results") or []:
        title = item.get("title") or ""
        content = item.get("content") or ""
        url = item.get("url") or ""
        chunks.append(f"- {title}\n  {content}\n  Source: {url}")
    answer = result.get("answer")
    body = "\n\n".join(chunks) if chunks else "No results found."
    if answer:
        return f"{answer}\n\n{body}"
    return body


