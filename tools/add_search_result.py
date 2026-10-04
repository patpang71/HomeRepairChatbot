"""add_search_result tool — store a search Q&A for a component."""

from __future__ import annotations

import json

from db.connection import get_cursor
from tools.common import fmt_ts, utc_now


def add_search_result(
    ComponentId: str | int,
    UserId: str | int,
    SearchQuestion: str,
    SearchResult: str,
) -> str:
    """Add a search result entry for a component."""
    if not (SearchQuestion or "").strip():
        return json.dumps({"success": False, "error": "SearchQuestion is required."})
    if not (SearchResult or "").strip():
        return json.dumps({"success": False, "error": "SearchResult is required."})

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT "ComponentId" FROM "HomeComponent"
            WHERE "ComponentId" = %s AND "UserId" = %s
            """,
            (int(ComponentId), int(UserId)),
        )
        if not cur.fetchone():
            return json.dumps({"success": False, "error": "The component is not found."})

        cur.execute(
            """
            INSERT INTO "SearchResult"
                ("ComponentId", "UserId", "SearchQuestion", "SearchResult", "TimeStamp")
            VALUES (%s, %s, %s, %s, %s)
            RETURNING "SearchId", "ComponentId", "UserId", "SearchQuestion",
                      "SearchResult", "TimeStamp"
            """,
            (
                int(ComponentId),
                int(UserId),
                SearchQuestion.strip(),
                SearchResult.strip(),
                utc_now(),
            ),
        )
        row = cur.fetchone()
        return json.dumps(
            {
                "success": True,
                "SearchId": str(row["SearchId"]),
                "ComponentId": str(row["ComponentId"]),
                "UserId": str(row["UserId"]),
                "SearchQuestion": row["SearchQuestion"],
                "SearchResult": row["SearchResult"],
                "TimeStamp": fmt_ts(row["TimeStamp"]),
            }
        )
