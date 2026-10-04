"""get_tool_recommandation tool — look up a recommended tool URL."""

from __future__ import annotations

import json
import re

from db.connection import get_cursor


def get_tool_recommandation(ToolKind: str) -> str:
    """Look up a tool recommendation URL by tool kind."""
    kind = (ToolKind or "").strip()
    if not kind:
        return json.dumps({"success": False, "error": "ToolKind is required."})

    with get_cursor() as cur:
        # 1) Exact match (case-insensitive)
        cur.execute(
            """
            SELECT "ToolKind", "Url"
            FROM "ToolRecommandation"
            WHERE LOWER("ToolKind") = LOWER(%s)
            """,
            (kind,),
        )
        row = cur.fetchone()
        if row:
            return json.dumps(
                {
                    "success": True,
                    "ToolKind": row["ToolKind"],
                    "Url": row["Url"],
                }
            )

        # 2) Fuzzy: require a unique safe match (no random LIMIT 1)
        cur.execute(
            """
            SELECT "ToolKind", "Url"
            FROM "ToolRecommandation"
            WHERE LOWER("ToolKind") LIKE LOWER(%s)
            ORDER BY LENGTH("ToolKind") ASC, "ToolKind" ASC
            """,
            (f"%{kind}%",),
        )
        candidates = cur.fetchall() or []
        chosen = _pick_unique_fuzzy_match(kind, candidates)
        if chosen:
            return json.dumps(
                {
                    "success": True,
                    "ToolKind": chosen["ToolKind"],
                    "Url": chosen["Url"],
                }
            )

        if len(candidates) > 1:
            options = ", ".join(c["ToolKind"] for c in candidates)
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"Ambiguous ToolKind '{kind}'. "
                        f"Matches: {options}. Please be more specific."
                    ),
                }
            )

        return json.dumps(
            {
                "success": False,
                "error": f"No recommendation found for ToolKind '{kind}'.",
            }
        )


def _pick_unique_fuzzy_match(kind: str, candidates: list) -> dict | None:
    """
    Accept a fuzzy match only when it is unambiguous:
    - exactly one LIKE candidate, or
    - exactly one whole-word / token match among candidates.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    kind_l = kind.lower().strip()
    # Prefer whole-word matches (e.g. "wrench" in "pipe wrench")
    pattern = re.compile(rf"(?:^|\s){re.escape(kind_l)}(?:\s|$)", re.IGNORECASE)
    word_hits = [c for c in candidates if pattern.search(c["ToolKind"])]

    if len(word_hits) == 1:
        return word_hits[0]

    # Prefer candidate that starts with the kind as a leading token
    prefix_hits = [
        c
        for c in candidates
        if c["ToolKind"].lower().startswith(kind_l + " ")
        or c["ToolKind"].lower() == kind_l
    ]
    if len(prefix_hits) == 1:
        return prefix_hits[0]

    return None
