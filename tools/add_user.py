"""add_user tool — insert a user if the email does not already exist."""

from __future__ import annotations

import json
from typing import Optional

from db.connection import get_cursor
from tools.common import DEFAULT_USER_PREFERENCE, normalize_user_preference


def add_user(
    Email: str,
    Zip: str,
    StreetAddress: Optional[str] = None,
    City: Optional[str] = None,
    State: Optional[str] = None,
    Preference: Optional[str] = None,
) -> str:
    """Add a user if the email does not already exist. Email and Zip are required."""
    email = (Email or "").strip()
    zip_code = (Zip or "").strip()
    if not email:
        return json.dumps({"success": False, "error": "Email is required."})
    if not zip_code:
        return json.dumps({"success": False, "error": "Zip is required."})

    preference = normalize_user_preference(
        Preference if Preference is not None else DEFAULT_USER_PREFERENCE
    )
    if preference is None:
        return json.dumps(
            {
                "success": False,
                "error": "Preference must be 'concise' or 'detail'.",
            }
        )

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT "UserId", "Email", "Preference"
            FROM "User"
            WHERE LOWER("Email") = LOWER(%s)
            """,
            (email,),
        )
        existing = cur.fetchone()
        if existing:
            return json.dumps(
                {
                    "success": True,
                    "created": False,
                    "message": "User already exists.",
                    "UserId": str(existing["UserId"]),
                    "Email": existing["Email"],
                    "Preference": existing.get("Preference") or DEFAULT_USER_PREFERENCE,
                }
            )

        cur.execute(
            """
            INSERT INTO "User"
                ("Email", "StreetAddress", "City", "State", "Zip", "Preference")
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING
                "UserId", "Email", "StreetAddress", "City", "State", "Zip", "Preference"
            """,
            (email, StreetAddress, City, State, zip_code, preference),
        )
        row = cur.fetchone()
        return json.dumps(
            {
                "success": True,
                "created": True,
                "message": "User created.",
                "UserId": str(row["UserId"]),
                "Email": row["Email"],
                "StreetAddress": row["StreetAddress"],
                "City": row["City"],
                "State": row["State"],
                "Zip": row["Zip"],
                "Preference": row["Preference"],
            }
        )
