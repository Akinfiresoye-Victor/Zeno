"""
Secure filesystem tools restricted to user Documents, Downloads, and Desktop folders.
Categories:
  - file_read: list_directory, read_file, search_files
  - file_write: write_file, append_file
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from zeno.permissions import check_and_confirm_file_overwrite
from zeno.settings import (
    ALLOWED_FOLDER_NAMES,
    ALLOWED_FOLDERS,
    HOME_DIR,
    MAX_FILE_READ_CHARS,
)


def validate_and_resolve_path(raw_path: str | Path) -> Path:
    """
    Safely resolve a path and verify it is strictly inside one of the ALLOWED_FOLDERS.
    Symlinks and parent-directory traversals ('..') are fully resolved and evaluated.

    Args:
        raw_path: User-provided relative or absolute path string.

    Returns:
        Path: Canonical resolved filesystem path.

    Raises:
        PermissionError: If the target path lies outside allowed directories.
    """
    path_str = str(raw_path).strip()
    p = Path(path_str).expanduser()

    # If relative path, check if it starts with one of the allowed folder names
    if not p.is_absolute():
        parts = p.parts
        if parts and parts[0] in ALLOWED_FOLDER_NAMES:
            p = HOME_DIR / p
        else:
            # Default relative paths into Documents folder
            p = HOME_DIR / "Documents" / p

    resolved = p.resolve()

    # Check if resolved path is inside any of the allowed directories
    is_allowed = False
    for allowed_dir in ALLOWED_FOLDERS:
        resolved_allowed = allowed_dir.resolve()
        if resolved == resolved_allowed or resolved_allowed in resolved.parents:
            is_allowed = True
            break

    if not is_allowed:
        allowed_list_str = ", ".join(ALLOWED_FOLDER_NAMES)
        raise PermissionError(
            f"Access denied: '{raw_path}' resolves to '{resolved}', which is outside allowed folders: {allowed_list_str}."
        )

    return resolved


def list_directory(path: str = "Documents") -> list[dict]:
    """
    List contents of a directory within allowed user folders.

    Args:
        path: Folder name or relative path inside allowed folders (e.g. 'Documents', 'Downloads').

    Returns:
        list[dict]: List of items with name, type (file or directory), and size in bytes.
    """
    target = validate_and_resolve_path(path)
    if not target.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    if not target.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    items = []
    for entry in sorted(target.iterdir()):
        try:
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size_bytes": stat.st_size if entry.is_file() else None,
                }
            )
        except (PermissionError, OSError):
            continue

    return items


def read_file(path: str) -> str:
    """
    Read text contents of a file within allowed user folders.
    Output is capped at 20000 characters.

    Args:
        path: Path to the target file.

    Returns:
        str: Text content of the file.
    """
    target = validate_and_resolve_path(path)
    if not target.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not target.is_file():
        raise IsADirectoryError(f"Target is a directory, not a file: {path}")

    with open(target, "r", encoding="utf-8", errors="replace") as f:
        content = f.read(MAX_FILE_READ_CHARS + 1)

    if len(content) > MAX_FILE_READ_CHARS:
        return content[:MAX_FILE_READ_CHARS] + "\n... (truncated to 20000 characters)"
    return content


_active_confirm_callback: Optional[Callable[[str], bool]] = None


def set_active_confirm_callback(callback: Optional[Callable[[str], bool]] = None) -> None:
    """Set the active confirmation callback for filesystem operations."""
    global _active_confirm_callback
    _active_confirm_callback = callback


def write_file(
    path: str,
    text: str,
) -> str:
    """
    Write or overwrite text content to a file within allowed user folders.
    Prompts for confirmation if file already exists.

    Args:
        path: Path to the target file.
        text: String content to write.

    Returns:
        str: Confirmation message with saved path and written byte count.
    """
    target = validate_and_resolve_path(path)

    # Check confirmation rule if overwriting existing file
    confirmed, msg = check_and_confirm_file_overwrite(str(target), _active_confirm_callback)
    if not confirmed:
        return msg

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        bytes_written = f.write(text)

    return f"Successfully wrote {bytes_written} characters to {target.name} ({target})."


def append_file(
    path: str,
    text: str,
) -> str:
    """
    Append text content to a file within allowed user folders.

    Args:
        path: Path to the target file.
        text: String content to append.

    Returns:
        str: Confirmation message.
    """
    target = validate_and_resolve_path(path)

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        bytes_written = f.write(text)

    return f"Successfully appended {bytes_written} characters to {target.name} ({target})."


def search_files(
    folder: str = "Documents",
    name_contains: str = "",
    text_contains: str = "",
) -> list[dict]:
    """
    Search for files by filename substring and optional file content substring
    within allowed user folders.

    Args:
        folder: Root folder to search ('Documents', 'Downloads', or 'Desktop').
        name_contains: Filter by filename substring (case-insensitive).
        text_contains: Filter by content substring (case-insensitive, text files only).

    Returns:
        list[dict]: Matching file paths and sizes.
    """
    target_root = validate_and_resolve_path(folder)
    if not target_root.is_dir():
        raise NotADirectoryError(f"Search folder is not a directory: {folder}")

    results = []
    name_query = name_contains.lower()
    text_query = text_contains.lower()

    for root, _, files in os.walk(target_root):
        for filename in files:
            file_path = Path(root) / filename
            # Resolve to verify still inside allowed sandbox
            try:
                resolved_file = file_path.resolve()
                # Check sandbox
                if not any(a == resolved_file or a in resolved_file.parents for a in ALLOWED_FOLDERS):
                    continue
            except Exception:
                continue

            if name_query and name_query not in filename.lower():
                continue

            if text_query:
                # Check content if text file
                try:
                    with open(resolved_file, "r", encoding="utf-8", errors="ignore") as f:
                        content_sample = f.read(50000).lower()
                        if text_query not in content_sample:
                            continue
                except Exception:
                    continue

            try:
                stat = resolved_file.stat()
                results.append(
                    {
                        "path": str(resolved_file),
                        "name": filename,
                        "size_bytes": stat.st_size,
                    }
                )
            except Exception:
                continue

            if len(results) >= 50:
                break
        if len(results) >= 50:
            break

    return results
