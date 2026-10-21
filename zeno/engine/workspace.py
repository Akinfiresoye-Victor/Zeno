"""
Workspace and Project Folder Rule Manager for Zeno Desktop AI Assistant.
Enforces Rule B:
- Creates one dedicated project folder inside workspace root (default ~/Documents/ZenoWorkspace).
- Creative, descriptive folder names: 2-4 words, max 32 chars, lowercase with hyphens.
- Python sanitization, collision detection, and short hex suffixes.
- Renaming support.
- Python-enforced containment: Zero file writes outside the project folder.
- Dedicated project virtual environment (.venv) initialization and binary resolution.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from typing import Any, Optional

from zeno.settings import DEFAULT_WORKSPACE_DIR, HOME_DIR

logger = logging.getLogger("zeno.workspace")


def sanitize_folder_name(raw_name: str) -> str:
    """
    Sanitize folder name according to Rule B:
    - 2 to 4 words
    - Max 32 characters
    - Lowercase with hyphens
    - No unsafe path characters or task-sentence slugs
    """
    cleaned = (raw_name or "").strip().lower()
    # Replace spaces, underscores, and special characters with hyphens
    cleaned = re.sub(r"[^a-z0-9\-]+", "-", cleaned)
    # Collapse consecutive hyphens
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")

    # If empty, fallback
    if not cleaned:
        cleaned = "project-core"

    # Enforce 2-4 words if more are present
    words = [w for w in cleaned.split("-") if w]
    if len(words) > 4:
        words = words[:4]
        cleaned = "-".join(words)
    elif len(words) < 2:
        words.append("app")
        cleaned = "-".join(words)

    # Enforce max 32 chars without breaking mid-word if possible
    if len(cleaned) > 32:
        cleaned = cleaned[:32].rstrip("-")
        if not cleaned:
            cleaned = "app-project"

    return cleaned


def generate_creative_folder_name(task_description: str) -> str:
    """
    Heuristic generator for creative, concise 2-4 word project names
    used when offline or before model enhancement.
    """
    clean = task_description.lower().strip()

    # Pre-mapped domain heuristics
    if "django" in clean and "server" in clean:
        return "django-core-api"
    if "car" in clean and ("game" in clean or "dash" in clean or "tkinter" in clean):
        return "car-dash-tkinter"
    if "math" in clean and ("util" in clean or "module" in clean):
        return "mathlab-core"
    if "pulse" in clean or "shop" in clean:
        return "pulse-shop-api"
    if "bookkeeper" in clean or "ledger" in clean:
        return "ledger-agent"
    if "chat" in clean or "rag" in clean:
        return "rag-nexus-core"
    if "scraper" in clean or "crawl" in clean:
        return "web-pulse-spider"

    # Extract keywords
    stop_words = {
        "build", "create", "make", "write", "develop", "generate", "implement",
        "please", "using", "with", "from", "that", "this", "some", "a", "an",
        "the", "and", "for", "in", "of", "to", "simple", "full", "complete",
    }
    tokens = [w for w in re.sub(r"[^a-z0-9\s]", " ", clean).split() if len(w) > 1 and w not in stop_words]

    if len(tokens) >= 2:
        chosen = tokens[:3]
    elif len(tokens) == 1:
        chosen = [tokens[0], "tool"]
    else:
        chosen = ["zeno", "project"]

    return sanitize_folder_name("-".join(chosen))


class ProjectWorkspace:
    """
    Encapsulates an isolated project workspace for an agent run.
    Guarantees that all writes stay within the project folder.
    """

    def __init__(
        self,
        workspace_root: Optional[Path | str] = None,
        project_name: Optional[str] = None,
        task_hint: str = "",
    ):
        self.root_dir = Path(workspace_root or DEFAULT_WORKSPACE_DIR).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

        # Generate or sanitize project folder name
        base_name = project_name or generate_creative_folder_name(task_hint)
        sanitized = sanitize_folder_name(base_name)

        # Collision detection: append suffix if directory already exists
        target_dir = self.root_dir / sanitized
        if target_dir.exists():
            suffix = uuid.uuid4().hex[:4]
            # Ensure name with suffix still fits within 32 chars
            prefix_len = 32 - len(suffix) - 1
            trimmed_base = sanitized[:prefix_len].rstrip("-")
            sanitized = f"{trimmed_base}-{suffix}"
            target_dir = self.root_dir / sanitized

        self.project_dir = target_dir
        self.project_name = sanitized
        self.project_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_existing_dir(cls, existing_dir: Path | str) -> "ProjectWorkspace":
        """Instantiate workspace from an existing project directory."""
        pdir = Path(existing_dir).resolve()
        if not pdir.exists():
            pdir.mkdir(parents=True, exist_ok=True)
        instance = cls.__new__(cls)
        instance.root_dir = pdir.parent
        instance.project_dir = pdir
        instance.project_name = pdir.name
        return instance

    def rename_project(self, new_name: str) -> tuple[bool, str]:
        """Allow user to rename the project folder cleanly."""
        sanitized = sanitize_folder_name(new_name)
        if sanitized == self.project_name:
            return True, self.project_name

        target = self.root_dir / sanitized
        if target.exists():
            return False, f"Directory '{sanitized}' already exists in workspace."

        try:
            self.project_dir.rename(target)
            self.project_dir = target
            self.project_name = sanitized
            return True, sanitized
        except Exception as exc:
            return False, f"Rename failed: {exc}"

    def is_path_inside(self, path_input: Path | str) -> bool:
        """Enforces Rule B: Check whether target path is strictly inside this project folder."""
        try:
            target = Path(path_input).resolve()
            return target == self.project_dir or self.project_dir in target.parents
        except Exception:
            return False

    def resolve_project_path(self, relative_or_absolute: str | Path) -> Path:
        """
        Safely resolve a path relative to the project directory.
        Raises PermissionError if path resolves outside the project folder.
        """
        p = Path(relative_or_absolute)
        if not p.is_absolute():
            resolved = (self.project_dir / p).resolve()
        else:
            resolved = p.resolve()

        if not self.is_path_inside(resolved):
            raise PermissionError(
                f"Rule B Violation: Path '{resolved}' lies outside the project folder '{self.project_dir}'."
            )
        return resolved

    def get_venv_python(self) -> Path:
        """
        Return the absolute path to the project's virtualenv Python binary.
        """
        if sys.platform == "win32":
            return self.project_dir / ".venv" / "Scripts" / "python.exe"
        return self.project_dir / ".venv" / "bin" / "python"

    def ensure_virtualenv(self) -> tuple[bool, str]:
        """
        Create a virtual environment inside <project>/.venv if it does not already exist.
        Rule E Requirement: Do not depend on 'activate' scripts.
        """
        venv_dir = self.project_dir / ".venv"
        python_bin = self.get_venv_python()

        if python_bin.exists():
            return True, f"Virtual environment already exists at {python_dir(python_bin)}"

        try:
            logger.info("Initializing .venv in %s...", self.project_dir)
            cmd = [sys.executable, "-m", "venv", str(venv_dir)]
            res = subprocess.run(cmd, cwd=str(self.project_dir), capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and python_bin.exists():
                return True, f"Virtual environment initialized at {venv_dir}"
            return False, f"Failed to create virtual environment: {res.stderr or res.stdout}"
        except Exception as exc:
            return False, f"Virtual environment creation error: {exc}"

    def list_files(self) -> list[dict[str, Any]]:
        """
        Return tree of all files inside the project folder with rich metadata.
        """
        import mimetypes

        files_list = []
        if not self.project_dir.exists():
            return []

        for p in self.project_dir.rglob("*"):
            # Exclude .venv and internal git/cache trees from main file tree display
            if any(part in p.parts for part in [".venv", ".git", "__pycache__"]):
                continue

            rel_path = str(p.relative_to(self.project_dir))
            is_dir = p.is_dir()
            size_bytes = p.stat().st_size if not is_dir else 0

            mime_type = "directory" if is_dir else (mimetypes.guess_type(str(p))[0] or "application/octet-stream")
            if not is_dir and p.suffix:
                ext_map = {
                    ".py": "text/x-python",
                    ".ts": "text/typescript",
                    ".tsx": "text/typescript",
                    ".js": "text/javascript",
                    ".json": "application/json",
                    ".md": "text/markdown",
                    ".html": "text/html",
                    ".css": "text/css",
                    ".pdf": "application/pdf",
                }
                if p.suffix.lower() in ext_map:
                    mime_type = ext_map[p.suffix.lower()]

            files_list.append({
                "name": p.name,
                "relative_path": rel_path,
                "absolute_path": str(p),
                "is_directory": is_dir,
                "size_bytes": size_bytes,
                "size_formatted": f"{round(size_bytes / 1024, 1)} KB" if not is_dir else "dir",
                "mime_type": mime_type,
                "modified_at": p.stat().st_mtime,
            })

        # Sort: directories first, then alphabetically
        files_list.sort(key=lambda x: (not x["is_directory"], x["relative_path"].lower()))
        return files_list


def python_dir(p: Path) -> str:
    return str(p.parent.parent)
