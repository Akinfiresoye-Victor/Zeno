"""
Chat lifecycle and retention manager for Zeno.
- Generates concise 3-5 word topics based on initial user prompts.
- Flags inactive chats for deletion after 3 days of inactivity.
- Permanently purges flagged chats after 4 days (24 hours after flagging) if untouched.
- Allows user to unflag and keep chats.
- Persists chat sessions and metadata in chats.json.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Optional

from zeno.settings import (
    CHAT_RETENTION_FLAG_DAYS,
    CHAT_RETENTION_PURGE_DAYS,
    CHATS_METADATA_PATH,
)

# 1 day in seconds
SECONDS_PER_DAY = 86400


def generate_chat_topic(initial_message: str) -> str:
    """
    Generate an intelligent, concise topic (3-5 words) from the user's first prompt.
    Extracts core task intent instead of raw string copying.
    """
    clean = initial_message.strip()
    lower = clean.lower()

    if any(k in lower for k in ["battery", "system info", "cpu", "ram", "uptime", "specs"]):
        return "System Diagnostic & Specs"
    if "screenshot" in lower or ("capture" in lower and ("screen" in lower or "tab" in lower or "display" in lower)):
        return "Screen & Tab Capture"
    if any(k in lower for k in ["summary.docx", "word document", "create document", "docx"]):
        return "Document Synthesis & Export"
    if any(k in lower for k in ["downloads", "documents", "list directory", "search files"]):
        return "Workspace File Inspection"
    if any(k in lower for k in ["run python", "execute python", "script", "benchmark"]):
        return "Python Code Runner Task"
    if any(k in lower for k in ["organize", "clean folder", "sort files"]):
        return "File Organization Task"
    if any(k in lower for k in ["web search", "google", "search online", "research"]):
        return "Online Information Retrieval"
    if any(k in lower for k in ["plan", "agentic", "build project", "workspace"]):
        return "Agentic Multi-Step Project"

    # Fallback heuristic: extract primary action verbs and subject
    words = [w for w in re.sub(r"[^\w\s]", "", clean).split() if len(w) > 2]
    stop_words = {"what", "how", "can", "you", "please", "the", "and", "for", "with", "from", "about"}
    meaningful = [w.capitalize() for w in words if w.lower() not in stop_words]

    if meaningful:
        return " ".join(meaningful[:4])
    return "New Conversation"


def process_chat_retention(
    chats: list[dict[str, Any]],
    current_time_epoch: Optional[float] = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Audit chats against retention policy:
    - Inactive >= 3 days: flag for deletion.
    - Flagged and inactive >= 4 days (after 24 hours flagged): permanently delete.
    Returns (retained_chats, purged_chat_ids).
    """
    now = current_time_epoch if current_time_epoch is not None else time.time()
    flag_threshold_seconds = CHAT_RETENTION_FLAG_DAYS * SECONDS_PER_DAY
    purge_threshold_seconds = CHAT_RETENTION_PURGE_DAYS * SECONDS_PER_DAY

    retained: list[dict[str, Any]] = []
    purged_ids: list[str] = []

    for chat in chats:
        last_active = chat.get("last_activity", chat.get("created_at", now))
        inactive_seconds = now - last_active

        # Check if chat exceeded 4 days and is flagged -> purge
        if chat.get("flagged_for_deletion", False) and inactive_seconds >= purge_threshold_seconds:
            purged_ids.append(chat["id"])
            continue

        # Check if inactive >= 3 days -> flag
        if inactive_seconds >= flag_threshold_seconds:
            chat["flagged_for_deletion"] = True
            if "flagged_at" not in chat:
                chat["flagged_at"] = now
            # Time remaining until deletion (hours)
            seconds_left = max(0, purge_threshold_seconds - inactive_seconds)
            chat["hours_until_purge"] = int(seconds_left // 3600)
        else:
            chat["flagged_for_deletion"] = False
            chat["hours_until_purge"] = None

        retained.append(chat)

    return retained, purged_ids


def unflag_chat(chat: dict[str, Any]) -> dict[str, Any]:
    """Remove deletion flag and renew chat activity timestamp."""
    chat["flagged_for_deletion"] = False
    chat["last_activity"] = time.time()
    chat.pop("flagged_at", None)
    chat.pop("hours_until_purge", None)
    return chat


def save_chats_metadata(chats: list[dict[str, Any]]) -> None:
    """Persist chats metadata to disk."""
    try:
        with open(CHATS_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(chats, f, indent=2)
    except Exception:
        pass


def load_chats_metadata() -> list[dict[str, Any]]:
    """Load chats metadata from disk."""
    if CHATS_METADATA_PATH.exists():
        try:
            with open(CHATS_METADATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []
