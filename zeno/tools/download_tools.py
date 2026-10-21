"""
Download and file-display tools for Zeno.
Provides: download_file, open_in_explorer, read_file_as_base64.
Category: file_write / file_read
"""

from __future__ import annotations

import base64
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from zeno.settings import DEFAULT_WORKSPACE_DIR
from zeno.tools.file_tools import get_active_project_dir


def download_file(url: str, destination_path: str = "", filename: str = "") -> dict[str, Any]:
    """
    Download a file from a URL and save it into the current session workspace.

    Args:
        url: The URL to download from.
        destination_path: Optional folder path to save the file into. Defaults to session workspace.
        filename: Optional filename override. If omitted, derived from the URL.

    Returns:
        dict with 'ok', 'path', 'name', 'size_bytes', 'mime_type', 'base64' (for images).
    """
    from zeno.settings import DEFAULT_WORKSPACE_DIR

    if not url or not url.strip():
        return {"ok": False, "error": "No URL provided."}

    url = url.strip()

    # Determine save directory
    if destination_path and destination_path.strip():
        save_dir = Path(destination_path)
    else:
        save_dir = DEFAULT_WORKSPACE_DIR

    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return {"ok": False, "error": f"Cannot create destination directory: {exc}"}

    # Determine filename
    if filename and filename.strip():
        safe_name = filename.strip()
    else:
        # Extract from URL path
        url_path = url.split("?")[0].rstrip("/")
        safe_name = url_path.split("/")[-1] if "/" in url_path else "downloaded_file"
        if not safe_name or "." not in safe_name:
            safe_name = f"zeno_download_{os.urandom(4).hex()}.bin"

    save_path = save_dir / safe_name

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()

        save_path.write_bytes(data)

        mime_type, _ = mimetypes.guess_type(str(save_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        result: dict[str, Any] = {
            "ok": True,
            "path": str(save_path.resolve()),
            "name": safe_name,
            "size_bytes": len(data),
            "mime_type": mime_type,
        }

        # For images, also return base64 so the UI can display them
        if mime_type.startswith("image/"):
            b64 = base64.b64encode(data).decode("utf-8")
            result["base64"] = f"data:{mime_type};base64,{b64}"

        return result

    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}: {exc.reason} — {url}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"Network error: {exc.reason} — {url}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _resolve_file_or_dir(raw_path: str) -> Optional[Path]:
    """Helper to resolve a path expanding ~, active project directory, and workspace root."""
    clean = (raw_path or "").strip()
    if not clean:
        return None

    # 1. Expand user (e.g. ~/Documents/...) and direct check
    try:
        p = Path(clean).expanduser().resolve()
        if p.exists():
            return p
    except Exception:
        pass

    # 2. Check relative to active project directory
    try:
        proj = get_active_project_dir()
        if proj and (proj / clean).resolve().exists():
            return (proj / clean).resolve()
    except Exception:
        pass

    # 3. Check relative to DEFAULT_WORKSPACE_DIR
    try:
        ws_p = (DEFAULT_WORKSPACE_DIR / clean).resolve()
        if ws_p.exists():
            return ws_p
    except Exception:
        pass

    # 4. Search by filename inside active project directory, then workspace
    try:
        fname = Path(clean).name
        search_roots = []
        proj = get_active_project_dir()
        if proj and proj.exists():
            search_roots.append(proj)
        if DEFAULT_WORKSPACE_DIR.exists():
            search_roots.append(DEFAULT_WORKSPACE_DIR)

        for root in search_roots:
            matches = list(root.rglob(fname))
            if matches:
                return matches[0].resolve()
    except Exception:
        pass

    return None


def open_in_explorer(path: str) -> dict[str, Any]:
    """
    Open a file or folder in the system file explorer and highlight it.
    """
    clean_path = (path or "").strip()
    resolved = _resolve_file_or_dir(clean_path)

    if not resolved:
        proj = get_active_project_dir()
        if proj and proj.exists():
            resolved = proj
        elif DEFAULT_WORKSPACE_DIR.exists():
            resolved = DEFAULT_WORKSPACE_DIR
        else:
            resolved = Path.home()

    try:
        norm_path = os.path.normpath(str(resolved))
        if sys.platform == "win32":
            if resolved.is_file():
                subprocess.Popen(["explorer.exe", f"/select,{norm_path}"])
            else:
                subprocess.Popen(["explorer.exe", norm_path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(resolved)])
        else:
            subprocess.Popen(["xdg-open", str(resolved.parent if resolved.is_file() else resolved)])
        return {"ok": True, "path": norm_path}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def read_file_as_base64(path: str) -> dict[str, Any]:
    """
    Read any file and return its contents as a base64 data URI, suitable for in-app viewing.
    """
    clean_path = (path or "").strip()
    if not clean_path:
        return {"ok": False, "error": "No file path provided"}

    resolved = _resolve_file_or_dir(clean_path)
    if not resolved:
        p = Path(clean_path).expanduser().resolve()
        if p.exists():
            resolved = p
        else:
            return {"ok": False, "error": f"Path not found: {path}"}

    norm_path = os.path.normpath(str(resolved))

    # If it is a directory, return explicit is_directory flag
    if resolved.is_dir():
        return {
            "ok": True,
            "is_directory": True,
            "name": resolved.name,
            "path": norm_path,
            "mime_type": "inode/directory",
            "message": "Folder preview is not supported directly in the code editor.",
        }

    mime_type, _ = mimetypes.guess_type(str(resolved))
    if not mime_type:
        ext = resolved.suffix.lower()
        mime_map = {
            ".py": "text/x-python",
            ".ts": "text/typescript",
            ".tsx": "text/typescript",
            ".js": "text/javascript",
            ".jsx": "text/javascript",
            ".json": "application/json",
            ".md": "text/markdown",
            ".html": "text/html",
            ".css": "text/css",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".xml": "text/xml",
            ".sh": "text/x-shellscript",
            ".bat": "text/x-batch",
            ".sql": "text/x-sql",
            ".yml": "text/yaml",
            ".yaml": "text/yaml",
            ".pdf": "application/pdf",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

    try:
        raw = resolved.read_bytes()
        b64 = base64.b64encode(raw).decode("utf-8")
        result: dict[str, Any] = {
            "ok": True,
            "name": resolved.name,
            "path": str(resolved),
            "mime_type": mime_type,
            "base64": f"data:{mime_type};base64,{b64}",
            "size_bytes": len(raw),
        }

        # For text files, also include raw text for code/markdown viewers
        if (
            mime_type.startswith("text/")
            or mime_type in (
                "application/json",
                "application/xml",
                "application/javascript",
                "application/x-sh",
                "application/sql",
            )
            or resolved.suffix.lower() in [
                ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json",
                ".html", ".css", ".txt", ".sh", ".bat"
            ]
        ):
            try:
                result["text"] = raw.decode("utf-8", errors="replace")
            except Exception:
                pass

        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
