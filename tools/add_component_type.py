"""add_component_type tool — insert a normalized ComponentTypeName."""

from __future__ import annotations

import json
import re

from db.connection import get_cursor


def add_component_type(ComponentTypeName: str) -> str:
    """
    Add a component type. ComponentTypeName must already be SCREAMING_SNAKE_CASE
    (e.g. WATER_HEATER). Idempotent if the name already exists.
    """
    name = (ComponentTypeName or "").strip().upper().replace(" ", "_")
    name = re.sub(r"[^A-Z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")

    if not name or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        return json.dumps(
            {
                "success": False,
                "error": (
                    "ComponentTypeName must be SCREAMING_SNAKE_CASE "
                    "(e.g. WATER_HEATER)."
                ),
            }
        )

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT "ComponentTypeId", "ComponentTypeName"
            FROM "ComponentType"
            WHERE "ComponentTypeName" = %s
            """,
            (name,),
        )
        existing = cur.fetchone()
        if existing:
            return json.dumps(
                {
                    "success": True,
                    "created": False,
                    "message": "Component type already exists.",
                    "ComponentTypeId": str(existing["ComponentTypeId"]),
                    "ComponentTypeName": existing["ComponentTypeName"],
                }
            )

        cur.execute(
            """
            INSERT INTO "ComponentType" ("ComponentTypeName")
            VALUES (%s)
            RETURNING "ComponentTypeId", "ComponentTypeName"
            """,
            (name,),
        )
        row = cur.fetchone()
        return json.dumps(
            {
                "success": True,
                "created": True,
                "message": "Component type created.",
                "ComponentTypeId": str(row["ComponentTypeId"]),
                "ComponentTypeName": row["ComponentTypeName"],
            }
        )
