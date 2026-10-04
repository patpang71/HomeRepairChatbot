"""Pytest configuration for HomeRepairChatbot."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable (tools/, graph/, db/)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
