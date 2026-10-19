"""
Project workspace management and automatic document organization tools.
Category: file_write
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil

from zeno.settings import DEFAULT_WORKSPACE_DIR
from zeno.tools.file_tools import validate_and_resolve_path

_CATEGORY_MAPPING = {
    "docs": [".docx", ".doc", ".pdf", ".txt", ".md", ".rtf", ".odt"],
    "code": [".py", ".ts", ".js", ".html", ".css", ".json", ".sh", ".sql", ".rs", ".go"],
    "data": [".csv", ".tsv", ".xlsx", ".parquet", ".sqlite", ".db"],
    "images": [".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".bmp"],
    "archives": [".zip", ".tar", ".gz", ".7z", ".rar"],
}


def create_project_workspace(
    project_name: str,
    folder_type: str = "project",
) -> dict:
    """
    Create a structured project workspace in the default AI workspace directory
    (or inside Documents/ZenoWorkspace).
    Automatically establishes organized subdirectories: src/, docs/, output/, and data/.

    Args:
        project_name: Name of the project or task.
        folder_type: 'code', 'document', or 'general'.

    Returns:
        dict: Path to the created project root and its subfolders.
    """
    clean_name = re.sub(r'[\\/*?:"<>|]', "", project_name).strip().replace(" ", "_")
    if not clean_name:
        clean_name = "zeno_project"

    project_root = DEFAULT_WORKSPACE_DIR / clean_name
    project_root.mkdir(parents=True, exist_ok=True)

    subdirs = ["docs", "output"]
    if folder_type in ("code", "project"):
        subdirs.extend(["src", "data"])

    created_paths = {}
    for sub in subdirs:
        sub_path = project_root / sub
        sub_path.mkdir(parents=True, exist_ok=True)
        created_paths[sub] = str(sub_path.resolve())

    return {
        "project_name": clean_name,
        "project_root": str(project_root.resolve()),
        "subfolders": created_paths,
        "status": "Workspace ready for agentic execution.",
    }


def organize_documents(source_folder: str = "Documents") -> dict:
    """
    Scan a folder in allowed user directories and organize loose files into
    categorized subfolders (docs/, code/, data/, images/, archives/).

    Args:
        source_folder: Target folder path inside allowed folders.

    Returns:
        dict: Summary of moved files and created categories.
    """
    target = validate_and_resolve_path(source_folder)
    if not target.is_dir():
        raise NotADirectoryError(f"Target is not a directory: {source_folder}")

    moved_counts: dict[str, int] = {}
    total_moved = 0

    for item in list(target.iterdir()):
        if not item.is_file():
            continue

        ext = item.suffix.lower()
        matched_cat = "other"
        for cat, extensions in _CATEGORY_MAPPING.items():
            if ext in extensions:
                matched_cat = cat
                break

        dest_dir = target / matched_cat
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_file = dest_dir / item.name
        if not dest_file.exists():
            try:
                shutil.move(str(item), str(dest_file))
                moved_counts[matched_cat] = moved_counts.get(matched_cat, 0) + 1
                total_moved += 1
            except Exception:
                pass

    return {
        "organized_folder": str(target),
        "total_files_organized": total_moved,
        "breakdown": moved_counts,
        "message": f"Organized {total_moved} files into categorized subfolders.",
    }
