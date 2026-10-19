"""
Audit logging for Zeno tool executions.
Appends clean, sanitized single-line log entries to actions.log.
Secrets, environment keys, and sensitive tokens are strictly scrubbed.
"""

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any

from zeno.settings import ACTIONS_LOG_PATH

# Sensitive patterns to redact
_SENSITIVE_PATTERNS = [
    re.compile(r"GEMINI_API_KEY\s*=\s*[^\s]+", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"key-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"(api[_-]?key|secret|token|password)[\"']?\s*[:=]\s*[\"']?[^,\s\"']+", re.IGNORECASE),
]


def sanitize_text(text: str) -> str:
    """Scrub potential API keys and secrets from string."""
    if not isinstance(text, str):
        text = str(text)
    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def sanitize_value(val: Any) -> Any:
    """Recursively sanitize objects, dictionaries, or lists."""
    if isinstance(val, str):
        return sanitize_text(val)
    if isinstance(val, dict):
        cleaned: dict[str, Any] = {}
        for k, v in val.items():
            lower_k = str(k).lower()
            if any(s in lower_k for s in ["key", "secret", "token", "password", "auth"]):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = sanitize_value(v)
        return cleaned
    if isinstance(val, (list, tuple)):
        return [sanitize_value(item) for item in val]
    return val


def log_tool_action(tool_name: str, args: dict[str, Any] | None, result_summary: str) -> None:
    """
    Write a single-line audit record to actions.log.
    Format: YYYY-MM-DD HH:MM:SS | tool_name | arguments | summary
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sanitized_args = sanitize_value(args or {})

    # Shorten arguments representation to under 200 chars
    try:
        args_str = json.dumps(sanitized_args, ensure_ascii=True, separators=(",", ":"))
    except Exception:
        args_str = str(sanitized_args)

    if len(args_str) > 200:
        args_str = args_str[:197] + "..."

    # Shorten result summary
    clean_summary = sanitize_text(result_summary.replace("\n", " ").strip())
    if len(clean_summary) > 200:
        clean_summary = clean_summary[:197] + "..."

    line = f"{timestamp} | {tool_name} | {args_str} | {clean_summary}\n"

    try:
        with open(ACTIONS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # Logging failure should not crash the desktop assistant
        pass
