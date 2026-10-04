"""add_tool_selected tool — save a recommended tool for a component."""

from __future__ import annotations

import json

from db.connection import get_cursor


def add_tool_selected(
    ComponentId: str | int,
    UserId: str | int,
    ToolKind: str,
    Url: str,
) -> str:
    """Insert a ToolSelected row for the given component and user."""
    kind = (ToolKind or "").strip()
    url = (Url or "").strip()
    if not kind:
        return json.dumps({"success": False, "error": "ToolKind is required."})
    if not url:
        return json.dumps({"success": False, "error": "Url is required."})

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
            INSERT INTO "ToolSelected"
                ("ComponentId", "UserId", "ToolKind", "Url")
            VALUES (%s, %s, %s, %s)
            RETURNING "ToolSelectedId", "ComponentId", "UserId", "ToolKind", "Url"
            """,
            (int(ComponentId), int(UserId), kind, url),
        )
        row = cur.fetchone()
        return json.dumps(
            {
                "success": True,
                "ToolSelectedId": str(row["ToolSelectedId"]),
                "ComponentId": str(row["ComponentId"]),
                "UserId": str(row["UserId"]),
                "ToolKind": row["ToolKind"],
                "Url": row["Url"],
            }
        )
