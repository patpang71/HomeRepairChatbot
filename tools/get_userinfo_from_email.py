"""get_userinfo_from_email tool — user profile with nested components and searches."""

from __future__ import annotations

import json

from db.connection import get_cursor
from tools.common import DEFAULT_USER_PREFERENCE, fmt_ts


def get_userinfo_from_email(Email: str) -> str:
    """Return user info with components (latest first) and nested search results."""
    email = (Email or "").strip()
    if not email:
        return json.dumps({"success": False, "error": "Email is required."})

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT "UserId", "Email", "StreetAddress", "City", "State", "Zip", "Preference"
            FROM "User"
            WHERE LOWER("Email") = LOWER(%s)
            """,
            (email,),
        )
        user = cur.fetchone()
        if not user:
            return json.dumps({"success": False, "found": False, "error": "User not found."})

        cur.execute(
            """
            SELECT "ComponentId", "Type", "ManufacturerId", "ProblemDesc",
                   "ResolutionDetail", "Resolved", "TimeStamp"
            FROM "HomeComponent"
            WHERE "UserId" = %s
            ORDER BY "TimeStamp" DESC
            """,
            (user["UserId"],),
        )
        components = cur.fetchall()

        result_components = []
        for comp in components:
            cur.execute(
                """
                SELECT "SearchId", "SearchQuestion", "SearchResult", "TimeStamp"
                FROM "SearchResult"
                WHERE "ComponentId" = %s
                ORDER BY "TimeStamp" DESC
                """,
                (comp["ComponentId"],),
            )
            searches = cur.fetchall()
            cur.execute(
                """
                SELECT "ToolSelectedId", "ToolKind", "Url"
                FROM "ToolSelected"
                WHERE "ComponentId" = %s
                ORDER BY "ToolSelectedId" ASC
                """,
                (comp["ComponentId"],),
            )
            tool_selected = cur.fetchall()
            result_components.append(
                {
                    "ComponentId": str(comp["ComponentId"]),
                    "Type": comp["Type"],
                    "ManufacturerId": comp["ManufacturerId"],
                    "ProblemDesc": comp["ProblemDesc"],
                    "ResolutionDetail": comp["ResolutionDetail"],
                    "Resolved": bool(comp["Resolved"]),
                    "TimeStamp": fmt_ts(comp["TimeStamp"]),
                    "Searchs": [
                        {
                            "SearchId": str(s["SearchId"]),
                            "SearchQuestion": s["SearchQuestion"],
                            "SearchResult": s["SearchResult"],
                            "TimeStamp": fmt_ts(s["TimeStamp"]),
                        }
                        for s in searches
                    ],
                    "ToolSelected": [
                        {
                            "ToolSelectedId": str(t["ToolSelectedId"]),
                            "ToolKind": t["ToolKind"],
                            "Url": t["Url"],
                        }
                        for t in tool_selected
                    ],
                }
            )

        return json.dumps(
            {
                "success": True,
                "found": True,
                "UserId": str(user["UserId"]),
                "Email": user["Email"],
                "StreetAddress": user["StreetAddress"],
                "City": user["City"],
                "State": user["State"],
                "Zip": user["Zip"],
                "Preference": user.get("Preference") or DEFAULT_USER_PREFERENCE,
                "Components": result_components,
            }
        )
