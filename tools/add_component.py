"""add_component tool — insert a home component for a user."""

from __future__ import annotations

import json
from typing import Optional

from db.connection import get_cursor
from tools.common import component_type_exists, fmt_ts, list_component_type_names, utc_now


def add_component(
    UserId: str | int,
    Type: str,
    ProblemDesc: Optional[str] = None,
    ManufacturerId: Optional[str] = None,
) -> str:
    """Add a home component for a user. Type must exist in ComponentType."""
    component_type = (Type or "").strip().upper().replace(" ", "_")
    if not component_type_exists(component_type):
        known = list_component_type_names()
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"Unknown Type '{component_type}'. "
                    f"Known types: {', '.join(known) or '(none)'}. "
                    "Add it with add_component_type first."
                ),
            }
        )

    with get_cursor() as cur:
        cur.execute('SELECT "UserId" FROM "User" WHERE "UserId" = %s', (int(UserId),))
        if not cur.fetchone():
            return json.dumps({"success": False, "error": f"UserId {UserId} not found."})

        cur.execute(
            """
            INSERT INTO "HomeComponent"
                ("UserId", "Type", "ManufacturerId", "ProblemDesc", "Resolved", "TimeStamp")
            VALUES (%s, %s, %s, %s, FALSE, %s)
            RETURNING "ComponentId", "UserId", "Type", "ManufacturerId", "ProblemDesc",
                      "ResolutionDetail", "Resolved", "TimeStamp"
            """,
            (int(UserId), component_type, ManufacturerId, ProblemDesc, utc_now()),
        )
        row = cur.fetchone()
        return json.dumps(
            {
                "success": True,
                "ComponentId": str(row["ComponentId"]),
                "UserId": str(row["UserId"]),
                "Type": row["Type"],
                "ManufacturerId": row["ManufacturerId"],
                "ProblemDesc": row["ProblemDesc"],
                "ResolutionDetail": row["ResolutionDetail"],
                "Resolved": row["Resolved"],
                "TimeStamp": fmt_ts(row["TimeStamp"]),
            }
        )
