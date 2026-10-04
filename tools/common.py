"""Shared helpers for SQL-backed tools."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from db.connection import get_cursor

UPDATABLE_COMPONENT_FIELDS = {
    "Type",
    "ManufacturerId",
    "ProblemDesc",
    "ResolutionDetail",
    "Resolved",
}

USER_PREFERENCES = {"concise", "detail"}
DEFAULT_USER_PREFERENCE = "concise"


def normalize_user_preference(value: Any) -> str | None:
    """
    Map free-text to 'concise' or 'detail'.
    Returns None when the value cannot be interpreted.
    """
    raw = " ".join(str(value or "").strip().lower().split())
    if not raw:
        return DEFAULT_USER_PREFERENCE

    if raw in USER_PREFERENCES:
        return raw

    concise_aliases = {
        "brief",
        "short",
        "summary",
        "summarized",
        "simple",
        "quick",
        "concise mode",
        "prefer concise",
    }
    detail_aliases = {
        "detailed",
        "details",
        "long",
        "full",
        "thorough",
        "in depth",
        "in-depth",
        "verbose",
        "detail mode",
        "prefer detail",
        "prefer detailed",
    }
    if raw in concise_aliases:
        return "concise"
    if raw in detail_aliases:
        return "detail"
    return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fmt_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(value)


def list_component_type_names() -> list[str]:
    """Return all ComponentTypeName values from the database."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT "ComponentTypeName"
            FROM "ComponentType"
            ORDER BY "ComponentTypeName" ASC
            """
        )
        rows = cur.fetchall()
        return [r["ComponentTypeName"] for r in rows]


def component_type_exists(name: str) -> bool:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM "ComponentType"
            WHERE "ComponentTypeName" = %s
            LIMIT 1
            """,
            (name,),
        )
        return cur.fetchone() is not None
