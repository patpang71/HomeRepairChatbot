"""get_component_types tool — list known home component types."""

from __future__ import annotations

import json

from tools.common import list_component_type_names


def get_component_types() -> str:
    """Return all ComponentType rows as JSON."""
    names = list_component_type_names()
    return json.dumps(
        {
            "success": True,
            "ComponentTypes": [
                {"ComponentTypeName": name} for name in names
            ],
            "names": names,
        }
    )
