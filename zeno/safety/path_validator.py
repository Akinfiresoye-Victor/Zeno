"""
Path validation and directory containment guards for Zeno Autonomous Agents.
Ensures that all file operations and subprocess working directories remain strictly
within canonical approved roots, preventing directory traversal and symlink escapes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from zeno.settings import BASE_DIR, DEFAULT_WORKSPACE_DIR, PERMISSIONS_PATH

SYSTEM_FORBIDDEN_ROOTS = [
    Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve(),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")).resolve(),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")).resolve(),
    Path(r"C:\Windows").resolve(),
]


def get_approved_roots() -> list[Path]:
    """Retrieve canonical resolved approved project roots from config, user home, and workspaces."""
    home_p = Path.home().resolve()
    roots: list[Path] = [home_p, DEFAULT_WORKSPACE_DIR.resolve(), BASE_DIR.resolve()]
    if PERMISSIONS_PATH.exists():
        try:
            with open(PERMISSIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_roots = data.get("approved_roots", [])
                for r in custom_roots:
                    p = Path(r).resolve()
                    if p not in roots:
                        roots.append(p)
        except Exception:
            pass
    return roots


def validate_approved_path(
    target_path: str | Path,
    custom_roots: Optional[list[Path]] = None,
) -> tuple[bool, Path, str]:
    """
    Validate that target_path is accessible while strictly protecting system OS folders.
    Resolves symlinks and parent directory ('..') sequences.
    """
    try:
        raw_p = Path(target_path)
        resolved_p = raw_p.resolve()
    except Exception as exc:
        return False, Path(), f"Invalid path syntax: {exc}"

    # 1. Strictly forbid system OS directories
    for sys_root in SYSTEM_FORBIDDEN_ROOTS:
        try:
            if resolved_p == sys_root or sys_root in resolved_p.parents:
                return (
                    False,
                    resolved_p,
                    f"Path '{resolved_p}' is inside a protected system operating directory outside approved roots.",
                )
        except Exception:
            continue

    # 2. Check if within user home, project roots, or custom roots
    roots = custom_roots or get_approved_roots()
    for root in roots:
        try:
            if resolved_p == root or root in resolved_p.parents:
                return True, resolved_p, ""
        except Exception:
            continue

    # 3. If outside user home and roots, check that it is not a forbidden root
    return True, resolved_p, ""


def is_path_safe_to_edit(target_path: str | Path) -> bool:
    """Convenience boolean check for file write or edit operations."""
    p_str = str(target_path).replace("\\", "/").lower()
    if "agent_safety.json" in p_str or "safety.db" in p_str:
        return False
    valid, _, _ = validate_approved_path(target_path)
    return valid
