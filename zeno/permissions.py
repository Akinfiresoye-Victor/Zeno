"""
Permission management, categories, persistence in permissions.json,
and confirmation tracking for Zeno Desktop AI Assistant.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from zeno.i18n import t
from zeno.settings import CONFIRM_DESTRUCTIVE, PERMISSIONS_PATH

CATEGORIES = [
    "system_read",
    "screen_capture",
    "clipboard",
    "file_read",
    "file_write",
    "app_launch",
    "python_exec",
    "web_search",
    "dev_tools",
]

# In-memory tracking for this session
_session_denied_categories: set[str] = set()
_session_confirmed_paths: set[str] = set()
_permissions_state: dict[str, bool] = {}


def load_permissions() -> dict[str, bool]:
    """Load persisted permissions from permissions.json."""
    global _permissions_state
    if PERMISSIONS_PATH.exists():
        try:
            with open(PERMISSIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _permissions_state = {k: bool(v) for k, v in data.items() if k in CATEGORIES}
                    return _permissions_state
        except Exception:
            pass
    _permissions_state = {}
    return _permissions_state


def save_permissions(state: dict[str, bool]) -> None:
    """Save permissions dictionary to permissions.json."""
    global _permissions_state
    _permissions_state = dict(state)
    try:
        with open(PERMISSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(_permissions_state, f, indent=2)
    except Exception:
        pass


def is_category_allowed(category: str) -> bool:
    """Check if category is currently allowed."""
    if not _permissions_state:
        load_permissions()
    return _permissions_state.get(category, False) is True


def is_category_denied_in_session(category: str) -> bool:
    """Check if category was denied in this session or in permissions.json."""
    if category in _session_denied_categories:
        return True
    if not _permissions_state:
        load_permissions()
    return _permissions_state.get(category) is False


def set_category_permission(category: str, allowed: bool) -> None:
    """Set permission for a category and persist it."""
    load_permissions()
    _permissions_state[category] = allowed
    if not allowed:
        _session_denied_categories.add(category)
    else:
        _session_denied_categories.discard(category)
    save_permissions(_permissions_state)


def request_permission_if_needed(
    category: str,
    dialog_callback: Optional[Callable[[str, str], bool]] = None,
) -> tuple[bool, str]:
    """
    Check if category permission is granted.
    If already allowed, returns (True, "").
    If denied in session, returns (False, error_message).
    If unprompted and dialog_callback is provided, shows prompt and saves result.
    """
    load_permissions()

    # Already allowed
    if _permissions_state.get(category) is True:
        return True, ""

    # Already denied in session or explicitly False
    if is_category_denied_in_session(category):
        return False, t("permission_denied_message", category=category)

    # Not yet asked
    if dialog_callback is not None:
        description = get_category_description(category)
        allowed = dialog_callback(category, description)
        set_category_permission(category, allowed)
        if allowed:
            return True, ""
        return False, t("permission_denied_message", category=category)

    # If no dialog can be shown, default to deny for safety
    return False, t("permission_denied_message", category=category)


def get_category_description(category: str) -> str:
    """Return plain sentence description for permission category."""
    desc_key = f"category_{category}"
    return t(desc_key)


def check_and_confirm_file_overwrite(
    path_str: str,
    dialog_callback: Optional[Callable[[str], bool]] = None,
) -> tuple[bool, str]:
    """
    Check CONFIRM_DESTRUCTIVE rule.
    If file exists and hasn't been confirmed in this session, ask user.
    """
    if not CONFIRM_DESTRUCTIVE:
        return True, ""

    target_path = Path(path_str).resolve()
    target_str = str(target_path)

    # If file does not exist, no destructive overwrite
    if not target_path.exists():
        return True, ""

    # Already confirmed once in this session
    if target_str in _session_confirmed_paths:
        return True, ""

    if dialog_callback is not None:
        confirmed = dialog_callback(target_str)
        if confirmed:
            _session_confirmed_paths.add(target_str)
            return True, ""
        return False, t("destructive_cancelled")

    return True, ""
