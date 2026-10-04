"""update_home_component tool — update one field and refresh TimeStamp."""

from __future__ import annotations

import json
from typing import Any

from db.connection import get_cursor
from tools.common import (
    UPDATABLE_COMPONENT_FIELDS,
    component_type_exists,
    fmt_ts,
    list_component_type_names,
    utc_now,
)


def update_home_component(
    ComponentId: str | int,
    UserId: str | int,
    field: str,
    value: Any,
) -> str:
    """Update one field on a HomeComponent, then refresh TimeStamp."""
    field_name = (field or "").strip()
    if field_name not in UPDATABLE_COMPONENT_FIELDS:
        return json.dumps(
            {
                "success": False,
                "error": (
                    "Invalid field. Allowed: "
                    f"{', '.join(sorted(UPDATABLE_COMPONENT_FIELDS))}"
                ),
            }
        )

    if field_name == "Type":
        value = str(value).strip().upper().replace(" ", "_")
        if not component_type_exists(value):
            known = list_component_type_names()
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"Unknown Type '{value}'. "
                        f"Known types: {', '.join(known) or '(none)'}."
                    ),
                }
            )

    if field_name == "Resolved":
        if isinstance(value, str):
            value = value.strip().lower() in {"true", "1", "yes", "y"}
        else:
            value = bool(value)

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT "ComponentId" FROM "HomeComponent"
            WHERE "ComponentId" = %s AND "UserId" = %s
            """,
            (int(ComponentId), int(UserId)),
        )
        if not cur.fetchone():
            return json.dumps(
                {
                    "success": False,
                    "error": "The component is not found.",
                }
            )

        set_clause = f'"{field_name}" = %s'
        cur.execute(
            f"""
            UPDATE "HomeComponent"
            SET {set_clause}, "TimeStamp" = %s
            WHERE "ComponentId" = %s AND "UserId" = %s
            RETURNING "ComponentId", "UserId", "Type", "ManufacturerId", "ProblemDesc",
                      "ResolutionDetail", "Resolved", "TimeStamp"
            """,
            (value, utc_now(), int(ComponentId), int(UserId)),
        )
        row = cur.fetchone()
        return json.dumps(
            {
                "success": True,
                "message": f"Updated {field_name}.",
                "ComponentId": str(row["ComponentId"]),
                "UserId": str(row["UserId"]),
                "Type": row["Type"],
                "ManufacturerId": row["ManufacturerId"],
                "ProblemDesc": row["ProblemDesc"],
                "ResolutionDetail": row["ResolutionDetail"],
                "Resolved": bool(row["Resolved"]),
                "TimeStamp": fmt_ts(row["TimeStamp"]),
            }
        )
