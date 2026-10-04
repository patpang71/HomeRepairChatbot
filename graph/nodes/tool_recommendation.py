"""ToolRecommendation node."""

from __future__ import annotations

import json
from typing import Any

import tools as db_tools
from graph.nodes.common import (
    Q_SATISFIED,
    llm,
    parse_json_blob,
)
from graph.state import ChatState

def tool_recommendation(state: ChatState) -> dict[str, Any]:
    awaiting = state.get("awaiting")
    user_msg = (state.get("last_user_message") or "").strip()
    component_id = state.get("active_component_id")
    user_id = state.get("user_id")

    # User is choosing which recommended tools to save
    if awaiting == "tool_selection":
        recommendations = state.get("tool_recommendations") or []
        if not recommendations:
            return {
                "awaiting": "satisfaction",
                "assistant_reply": (
                    "There were no catalog tools to select.\n"
                    f"{Q_SATISFIED}"
                ),
            }

        parsed = _parse_tool_selection(user_msg, recommendations)
        if parsed is None:
            catalog = "\n".join(
                f"- {t['ToolKind']}: {t['Url']}" for t in recommendations
            )
            return {
                "awaiting": "tool_selection",
                "assistant_reply": (
                    "Sorry, I wasn't sure which tools you meant.\n"
                    "Please name one or more from this list, or say you do not want any:\n"
                    f"{catalog}"
                ),
            }

        if not component_id or not user_id:
            return {
                "awaiting": "satisfaction",
                "tools_selected": [],
                "assistant_reply": (
                    "I understood your tool selection, but I lost the active component "
                    "or user id so I could not save tools to ToolSelected.\n"
                    f"{Q_SATISFIED}"
                ),
            }

        # Empty selection = user deliberately chose none
        if not parsed:
            return {
                "awaiting": "satisfaction",
                "tools_selected": [],
                "assistant_reply": (
                    "Okay, I did not save any tools for this component.\n"
                    f"{Q_SATISFIED}"
                ),
            }

        saved_lines: list[str] = []
        saved_tools: list[dict[str, str]] = []
        failed_lines: list[str] = []
        for item in parsed:
            try:
                result = json.loads(
                    db_tools.add_tool_selected(
                        ComponentId=component_id,
                        UserId=user_id,
                        ToolKind=item["ToolKind"],
                        Url=item["Url"],
                    )
                )
            except Exception as exc:
                result = {"success": False, "error": str(exc)}

            if result.get("success"):
                saved_lines.append(f"- {item['ToolKind']}: {item['Url']}")
                saved_tools.append({"ToolKind": item["ToolKind"], "Url": item["Url"]})
            else:
                err = result.get("error") or "unknown error"
                failed_lines.append(f"- {item['ToolKind']}: {err}")

        parts: list[str] = []
        if saved_lines:
            parts.append(
                "Got it — I saved these tools for your component:\n"
                + "\n".join(saved_lines)
            )
        if failed_lines:
            parts.append(
                "I could not save these tools:\n" + "\n".join(failed_lines)
            )
        if not saved_lines and failed_lines:
            parts.insert(
                0,
                "I tried to save your selected tools, but none were saved.",
            )
        parts.append(Q_SATISFIED)

        return {
            "awaiting": "satisfaction",
            "tools_selected": saved_tools,
            "assistant_reply": "\n\n".join(parts),
        }

    # First pass: extract tools from search, look up URLs, ask user to select
    search_result = state.get("latest_search_result") or ""
    search_preamble = state.get("assistant_reply") or ""
    mentioned = _extract_tools_from_search(search_result)

    recommendations: list[dict[str, str]] = []
    lines = ["Based on the search result, here are recommended tools and replacement parts:"]
    if not mentioned:
        lines.append(
            "I did not detect specific tools or replacement parts. "
            "Trying a few common repair tools..."
        )
        mentioned = ["screwdriver", "pliers", "wrench"]

    for kind in mentioned:
        data = json.loads(db_tools.get_tool_recommandation(kind))
        if data.get("success"):
            recommendations.append({"ToolKind": data["ToolKind"], "Url": data["Url"]})
            lines.append(f"- {data['ToolKind']}: {data['Url']}")
        else:
            lines.append(f"- {kind}: (no catalog URL found)")

    if recommendations:
        lines.append(
            "\nWould you like to select one or more of these tools or replacement parts "
            "to save for this repair? You can name them "
            "(e.g. \"screwdriver and shower head\"), or say you do not want any."
        )
        awaiting_next = "tool_selection"
    else:
        lines.append(
            "\nI could not match any tools in the catalog.\n"
            f"{Q_SATISFIED}"
        )
        awaiting_next = "satisfaction"

    tools_block = "\n".join(lines)
    combined = f"{search_preamble}\n\n{tools_block}".strip() if search_preamble else tools_block
    return {
        "tool_recommendations": recommendations,
        "tools_presented": True,
        "tools_selected": [],
        "awaiting": awaiting_next,
        "assistant_reply": combined,
    }


def _parse_tool_selection(
    user_message: str,
    recommendations: list[dict[str, str]],
) -> list[dict[str, str]] | None:
    """
    Interpret which recommended tools the user wants.
    Returns matched recommendation dicts, empty list for none, or None if unclear.
    """
    catalog = [{"ToolKind": t["ToolKind"], "Url": t["Url"]} for t in recommendations]
    prompt = (
        "The user was shown home-repair tool recommendations and asked to select "
        "one or more to save, or to decline.\n"
        "Return ONLY JSON in this exact shape:\n"
        '{"decision":"SELECT"|"NONE"|"UNCLEAR","tools":["ToolKind", ...]}\n\n'
        "Rules:\n"
        "- SELECT: user picked one or more tools; list matching ToolKind values from the catalog.\n"
        "- NONE: user clearly wants none / skip / no tools.\n"
        "- UNCLEAR: cannot tell what they want.\n"
        "Match ToolKind values case-insensitively to the catalog names.\n\n"
        f"Catalog: {json.dumps(catalog)}\n"
        f"User reply: {user_message}\n"
    )
    try:
        response = llm().invoke(prompt)
        parsed = parse_json_blob(
            response.content if hasattr(response, "content") else str(response)
        )
        if not isinstance(parsed, dict):
            return None
        decision = str(parsed.get("decision") or "").strip().upper()
        if decision == "NONE":
            return []
        if decision == "UNCLEAR":
            return None
        if decision == "SELECT":
            wanted = parsed.get("tools") or []
            if not isinstance(wanted, list) or not wanted:
                return None
            by_kind = {t["ToolKind"].lower(): t for t in recommendations}
            selected: list[dict[str, str]] = []
            seen: set[str] = set()
            for name in wanted:
                key = str(name).strip().lower()
                match = by_kind.get(key)
                if not match:
                    # partial contains match
                    for k, t in by_kind.items():
                        if key in k or k in key:
                            match = t
                            break
                if match and match["ToolKind"] not in seen:
                    selected.append(match)
                    seen.add(match["ToolKind"])
            return selected if selected else None
    except Exception:
        pass
    return None


def _extract_tools_from_search(search_result: str) -> list[str]:
    prompt = (
        "From the home repair search result below, list items the homeowner may need.\n"
        "Include BOTH:\n"
        "1) Hand tools / supplies (e.g. screwdriver, pliers, pipe wrench, plunger, Teflon tape)\n"
        "2) Replacement parts or components to buy/replace "
        "(e.g. recessed light, fuse, water faucet, garbage disposal, shower head, "
        "cartridge, valve, flapper, aerator, circuit breaker)\n\n"
        "Return ONLY a JSON array of short lowercase-or-normal product/tool name strings. "
        "Prefer concrete nouns (not verbs or vague words like 'part' or 'unit'). "
        "Deduplicate near-synonyms. If none, return [].\n\n"
        f"Search result:\n{search_result[:4000]}"
    )
    try:
        response = llm().invoke(prompt)
        parsed = parse_json_blob(
            response.content if hasattr(response, "content") else str(response)
        )
        if isinstance(parsed, list):
            names = [str(x).strip() for x in parsed if str(x).strip()]
            # Preserve order, drop duplicates case-insensitively
            seen: set[str] = set()
            ordered: list[str] = []
            for name in names:
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    ordered.append(name)
            if ordered:
                return ordered
    except Exception:
        pass

    known = [
        # Hand tools / supplies
        "screwdriver",
        "pliers",
        "pipe wrench",
        "pipe",
        "wrench",
        "hammer",
        "plunger",
        "tape measure",
        "adjustable wrench",
        "Teflon tape",
        "putty knife",
        "multimeter",
        "bucket",
        # Replacement components / parts
        "recessed light",
        "recess light",
        "fuse",
        "water facet",
        "water faucet",
        "faucet",
        "garbage disposal",
        "shower head",
        "showerhead",
        "cartridge",
        "valve",
        "flapper",
        "aerator",
        "circuit breaker",
        "light bulb",
        "washer",
        "o-ring",
        "supply line",
        "drain assembly",
    ]
    lower = search_result.lower()
    # Longer names first so "pipe wrench" wins before "pipe"/"wrench"
    known_sorted = sorted(known, key=lambda k: len(k), reverse=True)
    found: list[str] = []
    for k in known_sorted:
        if k.lower() in lower and k not in found:
            found.append(k)
    return found


