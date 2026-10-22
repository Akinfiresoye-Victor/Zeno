"""Helpers for selecting Gemini models supported by the configured API key."""

from __future__ import annotations

import re
from typing import Any


def list_supported_gemini_models(client: Any) -> list[str]:
    """Return Gemini model IDs that support generateContent, preferring stable Flash models."""
    models: set[str] = set()
    for model in client.models.list():
        name = str(getattr(model, "name", "") or "").rsplit("/", 1)[-1]
        actions = getattr(model, "supported_actions", None) or []
        if (
            name.startswith("gemini-")
            and any(str(action).lower() == "generatecontent" for action in actions)
        ):
            models.add(name)

    def sort_key(name: str) -> tuple[bool, bool, bool, int, int, str]:
        lower_name = name.lower()
        version = re.search(r"gemini-(\d+)(?:\.(\d+))?", lower_name)
        major = int(version.group(1)) if version else 0
        minor = int(version.group(2) or 0) if version else 0
        is_preview = any(marker in lower_name for marker in ("preview", "experimental", "-exp"))
        is_not_flash = "flash" not in lower_name
        is_lite = "lite" in lower_name
        return is_preview, is_not_flash, is_lite, -major, -minor, lower_name

    return sorted(models, key=sort_key)
